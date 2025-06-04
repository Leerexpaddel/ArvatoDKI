# llm_analyzer.py
import os
import json
import streamlit as st
import pandas as pd
from openai import OpenAI

from services.utils import extract_json_from_string, get_basic_dataframe_summary 
from services.db import save_insight, get_similar_insights 

def get_openai_client_internal():
    """
    Initialisiert und gibt einen OpenAI-Client zurück, sofern der API-Key gesetzt ist.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        client = OpenAI(api_key=api_key)
        return client
    except Exception:
        return None

def perform_llm_analysis(
    dataframe: pd.DataFrame,
    openai_client: OpenAI,
    mongo_client,
    additional_context_text: str = "",
    filename: str = "",
    follow_up_question: str = None,
    previous_analysis_results: dict = None
):
    """
    Führt eine LLM-Analyse (Initial- oder Folgeanalyse) auf Basis eines DataFrames durch.
    Nutzt OpenAI und optional MongoDB für historischen Kontext.
    """
    if openai_client is None:
        return {"error": "OpenAI Client ist nicht initialisiert. Bitte API-Schlüssel prüfen."}

    data_as_csv_string = dataframe.to_csv(index=False)
    detailed_data_summary_dict = get_basic_dataframe_summary(dataframe)

    # Datenzusammenfassung für das LLM
    formatted_summary_for_llm = "**Detaillierte Datenübersicht (vorab generiert für Ihre Information):**\n"
    formatted_summary_for_llm += f"- Anzahl Zeilen: {detailed_data_summary_dict['num_rows']}\n"
    formatted_summary_for_llm += f"- Anzahl Spalten: {detailed_data_summary_dict['num_cols']}\n"
    formatted_summary_for_llm += "- Spaltennamen und erkannte Datentypen:\n"
    if isinstance(detailed_data_summary_dict.get('column_dtypes'), dict):
        for col, dtype in detailed_data_summary_dict['column_dtypes'].items():
            formatted_summary_for_llm += f"  - '{col}': {dtype}\n"

    if detailed_data_summary_dict.get('numerical_summary'):
        formatted_summary_for_llm += "\n- Statistische Zusammenfassung für numerische Spalten:\n"
        if isinstance(detailed_data_summary_dict['numerical_summary'], dict):
            for col, stats in detailed_data_summary_dict['numerical_summary'].items():
                formatted_summary_for_llm += f"  - Spalte '{col}':\n"
                if isinstance(stats, dict):
                    for stat_name, stat_value in stats.items():
                        formatted_summary_for_llm += f"    - {stat_name}: {stat_value}\n"

    if detailed_data_summary_dict.get('categorical_summary'):
        formatted_summary_for_llm += "\n- Zusammenfassung für kategorische/textuelle Spalten:\n"
        if isinstance(detailed_data_summary_dict['categorical_summary'], dict):
            for col, stats in detailed_data_summary_dict['categorical_summary'].items():
                formatted_summary_for_llm += f"  - Spalte '{col}':\n"
                if isinstance(stats, dict):
                    formatted_summary_for_llm += f"    - Anzahl einzigartiger Werte: {stats.get('unique_values')}\n"
                    top_values_for_json = {} 
                    if isinstance(stats.get('top_values'), dict):
                        for k, v in stats['top_values'].items(): 
                            if isinstance(k, pd.Timestamp):
                                top_values_for_json[k.isoformat()] = v 
                            else:
                                top_values_for_json[str(k)] = v 
                        if top_values_for_json:
                            formatted_summary_for_llm += f"    - Häufigste Werte (Top 5): {json.dumps(top_values_for_json)}\n" 
                        else:
                            formatted_summary_for_llm += f"    - Häufigste Werte (Top 5): Keine oder konnten nicht serialisiert werden.\n"
                    else:
                        formatted_summary_for_llm += f"    - Häufigste Werte (Top 5): Keine oder ungültiges Format.\n"
    formatted_summary_for_llm += "---\n"

    # Historische Insights aus MongoDB
    retrieved_historical_insights = []
    historical_insights_context = ""
    if mongo_client:
        st.info("Suche nach ähnlichen historischen Erkenntnissen (falls MongoDB verbunden)...")
        query_for_similar_insights = ""
        if isinstance(detailed_data_summary_dict.get('column_names'), list) and isinstance(detailed_data_summary_dict.get('numerical_summary'), dict):
            query_for_similar_insights = f"DataFrame overview: columns {detailed_data_summary_dict['column_names']}, rows {detailed_data_summary_dict['num_rows']}. Focus on numerical data: {detailed_data_summary_dict['numerical_summary']}"
        if query_for_similar_insights:
            retrieved_historical_insights = get_similar_insights(mongo_client, query_for_similar_insights, limit=5)
        if retrieved_historical_insights:
            historical_insights_context = "\n\n**Historische und ähnliche Erkenntnisse (zum Kontext und Vergleich):**\n"
            for insight in retrieved_historical_insights:
                historical_insights_context += (
                    f"- **Insight ID (Historical):** {insight.get('insight_id', 'N/A')}\n"
                    f"  **Titel:** {insight.get('title', 'N/A')}\n"
                    f"  **Typ:** {insight.get('type', 'N/A')}\n"
                    f"  **Beschreibung:** {insight.get('description', 'N/A')}\n"
                    f"  **Betroffener Bereich:** {insight.get('affected_area', 'N/A')}\n"
                    f"  **Zeitraum:** {insight.get('period', 'N/A')}\n"
                    f"  **Quantitativer Impact:** {insight.get('quantitative_impact', 'N/A')}\n"
                    f"  **Confidence Level:** {insight.get('confidence_level', 'N/A')}\n\n"
                )
            st.info(f"Es wurden {len(retrieved_historical_insights)} ähnliche historische Erkenntnisse gefunden und dem Kontext hinzugefügt.")
        elif query_for_similar_insights:
            st.info("Keine ähnlichen historischen Erkenntnisse in MongoDB gefunden oder Abfragefehler.")
    else:
        st.info("MongoDB ist nicht verbunden (oder Nutzung nicht ausgewählt), daher keine Abfrage historischer Erkenntnisse für diese Analyse.")

    # Kontext vorheriger Analysen
    previous_insights_summary_for_prompt = "Keine vorherige Analyse als direkter Kontext übergeben."
    if previous_analysis_results:
        previous_insights_summary_for_prompt = "\n\n**Zusammenfassung der Kernaussagen der direkt vorhergehenden Analyse (zur Beantwortung der Folgefrage):**\n"
        if previous_analysis_results.get("insights") and isinstance(previous_analysis_results["insights"], list) and previous_analysis_results["insights"]:
            for insight in previous_analysis_results["insights"][:3]:
                previous_insights_summary_for_prompt += (
                    f"- **Vorheriger Insight Titel:** {insight.get('title', 'N/A')}\n"
                    f"  **Beschreibung:** {insight.get('description', 'N/A')}\n"
                )
        else:
            previous_insights_summary_for_prompt += "Die vorherige Analyse enthielt keine spezifischen Kernaussagen im erwarteten Format.\n"
        previous_insights_summary_for_prompt += (
            f"**Gesamtzusammenfassung der vorherigen Analyse:** {previous_analysis_results.get('overall_summary', 'N/A')}\n"
        )

    # Prompt-Handling
    if follow_up_question and previous_analysis_results:
        st.info(f"Führe fokussierte Folgeanalyse für die Frage durch: '{follow_up_question}'...")
        with open("prompts/system_prompt_follow_up.txt", "r", encoding="utf-8") as f:
            system_prompt_follow_up = f.read()
        user_prompt_content = (
            "Bitte beantworte die folgende spezifische Frage basierend auf den bereitgestellten Daten und der vorherigen Analyse. "
            "Konzentriere dich voll und ganz auf die Beantwortung der Frage.\n\n"
            f"**Die zu untersuchende Folgefrage lautet:**\n'{follow_up_question}'\n\n"
            "**Hier ist die für die Analyse relevante Datenübersicht (vorab generiert):**\n"
            f"{formatted_summary_for_llm}\n"
            f"{previous_insights_summary_for_prompt}\n"
            "**Hier sind die zu analysierenden Originaldaten im CSV-Format (die erste Zeile ist der Header):**\n"
            f"{data_as_csv_string}"
        )
        if additional_context_text:
            user_prompt_content += f"\n\n**Ursprünglicher zusätzlicher Kontext/Anweisungen vom Benutzer (für den Gesamtkontext relevant):**\n{additional_context_text}"
        user_prompt_content += historical_insights_context
        messages_for_llm = [
            {"role": "system", "content": system_prompt_follow_up},
            {"role": "user", "content": user_prompt_content}
        ]
        st.info("Führe fokussierte LLM-Analyse für die Folgefrage durch...")
    else:
        st.info("Bereite Daten für die Erst-Analyse vor...")
        with open("prompts/system_prompt_initial.txt", "r", encoding="utf-8") as f:
            system_prompt_initial = f.read()
        user_prompt_content_initial = (
            "Bitte analysiere die folgenden Geschäftsdaten gemäß den Anweisungen im System-Prompt. "
            "Konzentriere dich darauf, die *allerwichtigsten* Erkenntnisse zu identifizieren, die einem Business-Anwender helfen, bessere Entscheidungen zu treffen. "
            "Sei proaktiv und denke mit!\n\n"
            f"{formatted_summary_for_llm}"
            "\n\n**Beispiel für eine gute kontextualisierte Erkenntnis (basierend auf fiktiven Daten):**\n"
            "```json\n"
            "    {\n"
            "      \"insight_id\": \"RETURN_SPIKE_CH_001\",\n"
            "      \"title\": \"Starker Anstieg der Retouren für Produkt 'Alpha' in der Schweiz im September 2024\",\n"
            "      \"type\": \"Anomalie\",\n"
            "      \"description\": \"Die Retourenquote für das Produkt 'Alpha' in der Schweiz ist im September 2024 auf 18% gestiegen, was deutlich über der durchschnittlichen Retourenquote von 5% für dieses Produkt in anderen Regionen und Zeiträumen liegt. Dies deutet auf ein spezifisches Problem hin.\",\n"
            "      \"affected_area\": \"Produkt 'Alpha', Region Schweiz\",\n"
            "      \"period\": \"September 2024\",\n"
            "      \"quantitative_impact\": \"Retourenquote von 18% (vs. 5% Durchschnitt); ca. 150 zusätzliche Retouren\",\n"
            "      \"supporting_data_points\": [\n"
            "           {\"row_reference\": \"Filter: Produkt='Alpha', Region='Schweiz', Monat='2024-09'\", \"column_reference\": \"Retourenquote\", \"value\": \"18%\", \"explanation\": \"Dieser Wert ist der höchste gemessene für dieses Produkt in den letzten 12 Monaten.\"},\n"
            "           {\"row_reference\": \"Filter: Produkt='Alpha', Region='Schweiz', Monat='2024-08'\", \"column_reference\": \"Retourenquote\", \"value\": \"6%\", \"explanation\": \"Vormonatswert zum Vergleich.\"}\n"
            "      ],\n"
            "      \"confidence_level\": \"Hoch\"\n"
            "    }\n"
            "```\n\n"
            "**Hier sind die zu analysierenden Daten im CSV-Format (die erste Zeile ist der Header):**\n\n"
            f"{data_as_csv_string}"
        )
        if additional_context_text:
            user_prompt_content_initial += f"\n\n**Zusätzlicher Kontext/Anweisungen vom Benutzer:**\n{additional_context_text}"
        user_prompt_content_initial += historical_insights_context
        messages_for_llm = [
            {"role": "system", "content": system_prompt_initial},
            {"role": "user", "content": user_prompt_content_initial}
        ]
        st.info("Führe erste LLM-Analyse durch...")

    # LLM-Analyse durchführen
    initial_llm_response_content = None
    try:
        completion = openai_client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=messages_for_llm, 
            temperature=0.0,
            seed=123,
            max_tokens=3000
        )
        initial_llm_response_content = completion.choices[0].message.content
        st.success("Analyse vom LLM empfangen." if not follow_up_question else "Folgeanalyse vom LLM empfangen.")
    except Exception as e:
        error_message = f"Fehler bei der API-Anfrage an OpenAI: {e}"
        st.error(error_message)
        return {"error": error_message}

    # Selbstüberprüfung durch das LLM
    st.info("Führe Selbstüberprüfung der Analyse durch...")
    with open("prompts/review_system_prompt.txt", "r", encoding="utf-8") as f:
        review_system_prompt = f.read()
    review_user_prompt_content = (
        "Hier ist die vorab generierte Datenübersicht, die auch der ersten Analyse (oder der aktuellen Stufe der Folgeanalyse) zur Verfügung stand:\n"
        f"{formatted_summary_for_llm}\n"
        "Hier sind die Originaldaten im CSV-Format:\n\n"
        f"{data_as_csv_string}\n\n"
    )
    if follow_up_question:
        review_user_prompt_content += (
            "Die KI hat eine **Folgeanalyse** zu folgender spezifischen Frage durchgeführt:\n"
            f"**Folgefrage:** '{follow_up_question}'\n\n"
            "Kontext der direkt vorhergehenden Analyse (Zusammenfassung):\n"
            f"{previous_insights_summary_for_prompt}\n\n"
        )
    review_user_prompt_content += (
        "Hier ist die Analyse (oder Folgeanalyse), die zuvor generiert wurde und nun überprüft werden soll:\n\n"
        f"{initial_llm_response_content}\n\n"
        "Bitte überprüfe diese Analyse gründlich anhand der oben genannten Kriterien und der bereitgestellten Originaldaten (CSV und Zusammenfassung). "
        "Wenn es eine Folgeanalyse war, stelle besonders sicher, dass die spezifische Frage umfassend und korrekt beantwortet wurde. "
        "Korrigiere die Analyse, falls notwendig, und gib die finale, korrigierte (oder bestätigte) JSON-Antwort aus. "
        "Stelle sicher, dass die Ausgabe dem vorgegebenen JSON-Schema entspricht und alle Details wie 'supporting_data_points' korrekt und nachvollziehbar auf die CSV-Daten bezogen sind."
    )
    if additional_context_text:
        review_user_prompt_content += f"\n\n**Ursprünglicher zusätzlicher Kontext/Anweisungen vom Benutzer (relevant für den Gesamtkontext):**\n{additional_context_text}"
    review_user_prompt_content += historical_insights_context

    messages_review = [
        {"role": "system", "content": review_system_prompt},
        {"role": "user", "content": review_user_prompt_content}
    ]

    final_llm_response_content = None
    try:
        completion_review = openai_client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=messages_review,
            temperature=0.0,
            seed=123,
            max_tokens=3000
        )
        final_llm_response_content = completion_review.choices[0].message.content
        st.success("Selbstüberprüfung abgeschlossen. Finale Analyse empfangen.")
    except Exception as e:
        st.error(f"Fehler bei der zweiten API-Anfrage (Selbstüberprüfung) an OpenAI: {e}")
        st.warning("Fehler bei der Selbstüberprüfung. Versuche, die vorherige Analyse (vor Review) zu verwenden.")
        final_llm_response_content = initial_llm_response_content

    # Parsing der LLM-Antwort
    if final_llm_response_content is None:
        st.error("Keine Antwort vom LLM erhalten (final_llm_response_content is None).")
        return {"error": "Keine Antwort vom LLM erhalten.", "raw_response": "None"}

    try:
        json_string_extracted = extract_json_from_string(final_llm_response_content)
        if json_string_extracted is None:
            st.error("Konnte keinen JSON-Block in der LLM-Antwort finden.")
            st.write("Rohantwort der LLM-Anfrage (zur Fehlerbehebung):")
            st.code(final_llm_response_content)
            return {"error": "Kein JSON-Block in LLM-Antwort gefunden.", "raw_response": final_llm_response_content}
        parsed_results = json.loads(json_string_extracted)
    except json.JSONDecodeError as e:
        st.error(f"Fehler beim Parsen des JSON-Blocks aus der LLM-Antwort: {e}")
        st.write("Extrahierter JSON-String (Versuch):")
        st.code(json_string_extracted if 'json_string_extracted' in locals() else "Konnte keinen String extrahieren")
        st.write("Rohantwort der LLM-Anfrage (zur Fehlerbehebung):")
        st.code(final_llm_response_content)
        return {"error": "LLM-Antwort konnte nicht als JSON geparst werden.", "raw_response": final_llm_response_content}
    except Exception as e:
        st.error(f"Unerwarteter Fehler beim Verarbeiten der LLM-Antwort: {e}")
        return {"error": f"Unerwarteter Fehler: {e}", "raw_response": final_llm_response_content}

    if parsed_results:
        if follow_up_question:
            parsed_results["is_follow_up"] = True
            parsed_results["answered_question"] = follow_up_question
        else:
            parsed_results["is_follow_up"] = False
        return parsed_results
    else:
        st.error("Es wurden keine gültigen Analyseergebnisse vom LLM zurückgegeben, obwohl kein expliziter Fehler aufgetreten ist.")
        return {"error": "Keine gültigen Analyseergebnisse erhalten (parsed_results is None).", "raw_response": final_llm_response_content}
# llm_analyzer.py
import os
import json
import streamlit as st
import pandas as pd
from openai import OpenAI


from services.utils import extract_json_from_string, get_basic_dataframe_summary, \
                           add_calculated_kpis_to_df, get_higher_level_aggregations, get_top_n_anomalies
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

    # Datenzusammenfassung für das LLM
    # 1. Berechne KPIs und füge sie als neue Spalten zum DataFrame hinzu
    st.info("Schritt 1/4: Berechne Performance-Indikatoren (KPIs) pro Zeile...")
    df_with_kpis = add_calculated_kpis_to_df(dataframe.copy())

    # 2. Erzeuge eine Basis-Zusammenfassung des angereicherten DataFrames
    st.info("Schritt 2/4: Erstelle eine detaillierte Datenübersicht...")
    detailed_data_summary_dict = get_basic_dataframe_summary(df_with_kpis)

    # 3. Erzeuge höhere Aggregationen (für globale Vergleiche)
    st.info("Schritt 3/4: Erstelle globale Aggregationen für übergeordnete Trends...")
    higher_level_aggs_dict = get_higher_level_aggregations(df_with_kpis) # Ist jetzt ein Dict
    global_agg_country_pm_csv = higher_level_aggs_dict.get("by_country_payment_method", "Keine Aggregation nach Land & Zahlungsmethode verfügbar.")
    global_agg_country_csv = higher_level_aggs_dict.get("by_country", "Keine Aggregation nach Land verfügbar.") # NEU
    global_agg_pm_csv = higher_level_aggs_dict.get("by_payment_method", "Keine Aggregation nach Zahlungsmethode verfügbar.") # NEU


    # 4. Extrahiere Top N/Auffälligkeiten aus den ursprünglichen Zeilen
    st.info("Schritt 4/4: Extrahiere spezifische Auffälligkeiten und Extremwerte...")
    anomalies_csvs = get_top_n_anomalies(df_with_kpis, n=7) # N kann angepasst werden, um Token zu sparen

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
        # KORREKTUR: Pfad zur system_prompt_follow_up.txt angepasst
        system_prompt_follow_up_path = os.path.join(os.path.dirname(__file__), '../prompts/system_prompt_follow_up.txt')
        with open(system_prompt_follow_up_path, "r", encoding="utf-8") as f:
            system_prompt = f.read() # system_prompt holds the content of system_prompt_follow_up.txt

        user_content_path = os.path.join(os.path.dirname(__file__), '../prompts/user_content.txt')
        with open(user_content_path, "r", encoding="utf-8") as f:
            user_content = f.read()

        template_ctx = {
            "data_summary_json": json.dumps(detailed_data_summary_dict, indent=2, ensure_ascii=False),
            "agg_country_payment_csv": global_agg_country_pm_csv,
            "top_n": anomalies_csvs.get("n", 5),
            "top_gross_sales_csv": anomalies_csvs.get("top_gross_sales", "Nicht verfügbar."),
            "top_return_rate_csv": anomalies_csvs.get("top_return_rate_eur", "Nicht verfügbar."),
            "all_write_offs_csv": anomalies_csvs.get("all_write_offs_gt_0", "Nicht verfügbar."),
            "top_chargeback_rate_csv": anomalies_csvs.get("top_chargeback_rate_eur", "Nicht verfügbar."),
            "top_dunning_level2_csv": anomalies_csvs.get("top_dunning_level2_eur", "Nicht verfügbar."),
            "prev_insights_summary": previous_insights_summary_for_prompt,
            "follow_up_question": follow_up_question,
        }

        user_content = user_content.format(**template_ctx)
        if additional_context_text:
            user_content += f"\n\n**Ursprünglicher zusätzlicher Kontext/Anweisungen vom Benutzer (für den Gesamtkontext relevant):**\n{additional_context_text}"
        user_content += historical_insights_context

        messages_for_llm = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]

    else: # Initial analysis
        st.info("Bereite Daten für die Erst-Analyse vor...")
        system_prompt_initial_path = os.path.join(os.path.dirname(__file__), '../prompts/system_prompt_initial.txt')
        with open(system_prompt_initial_path, 'r', encoding='utf-8') as f:
            system_prompt = f.read()
        
        user_content_path = os.path.join(os.path.dirname(__file__), '../prompts/user_content_init.txt')
        with open(user_content_path, "r", encoding="utf-8") as f:
            user_content = f.read()

        template_ctx = {
            "detailed_data_summary_dict": json.dumps(detailed_data_summary_dict, indent=2, ensure_ascii=False),
            "global_agg_country_pm_csv": global_agg_country_pm_csv,
            "global_agg_country_csv": global_agg_country_csv,
            "top_gross_sales": anomalies_csvs.get('top_gross_sales', 'Nicht verfügbar.'),
            "global_agg_pm_csv": global_agg_pm_csv,
        }

        user_content = user_content.format(**template_ctx)

        if additional_context_text:
            user_content += f"\n\n**Zusätzlicher Kontext/Anweisungen vom Benutzer:**\n{additional_context_text}"
        user_content += historical_insights_context
        messages_for_llm = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]
        st.info("Führe erste LLM-Analyse durch...")

    # LLM-Analyse durchführen
    initial_llm_response_content = None
    try:
        completion = openai_client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o"),
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

    review_user_prompt_content_path = os.path.join(os.path.dirname(__file__), '../prompts/review_user_prompt_content.txt')
    with open(review_user_prompt_content_path, "r", encoding="utf-8") as f:
            review_user_prompt_content = f.read()

    template_ctx = {
        "detailed_data_summary_dict": json.dumps(detailed_data_summary_dict, indent=2, ensure_ascii=False),
        "global_agg_country_pm_csv": global_agg_country_pm_csv,
        "global_agg_country_csv": global_agg_country_csv,
        "global_agg_pm_csv": global_agg_pm_csv,
        "n": anomalies_csvs.get('n', 5),
        "top_gross_sales": anomalies_csvs.get('top_gross_sales', 'Nicht verfügbar.'),
        "top_return_rate_eur": anomalies_csvs.get('top_return_rate_eur', 'Nicht verfügbar.'),
        "all_write_offs_gt_0": anomalies_csvs.get('all_write_offs_gt_0', 'Nicht verfügbar.'),
        "top_chargeback_rate_eur": anomalies_csvs.get('top_chargeback_rate_eur', 'Nicht verfügbar.'),
        "top_dunning_level2_eur": anomalies_csvs.get('top_dunning_level2_eur', 'Nicht verfügbar.'),
    }

    review_user_prompt_content = review_user_prompt_content.format(**template_ctx)
    
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
        "Bitte überprüfe diese Analyse gründlich anhand der oben genannten Kriterien und der bereitgestellten Daten. "
        "Wenn es eine Folgeanalyse war, stelle besonders sicher, dass die spezifische Frage umfassend und korrekt beantwortet wurde. "
        "Korrigiere die Analyse, falls notwendig, und gib die finale, korrigierte (oder bestätigte) JSON-Antwort aus. "
        "Stelle sicher, dass die Ausgabe dem vorgegebenen JSON-Schema entspricht und alle Details wie 'supporting_data_points' korrekt und nachvollziehbar auf die bereitgestellten Datenabschnitte bezogen sind."
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
            model=os.getenv("OPENAI_MODEL", "gpt-4o"),
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
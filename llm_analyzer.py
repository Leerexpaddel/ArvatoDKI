# llm_analyzer.py
import os
from openai import OpenAI
import json
import streamlit as st
import pandas as pd

from utils import extract_json_from_string, get_basic_dataframe_summary 
from db_manager import save_insight, get_similar_insights 

# Diese Funktion wird jetzt in app.py aufgerufen und gecached.
def get_openai_client_internal(): 
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        client = OpenAI(api_key=api_key)
        return client
    except Exception as e:
        # st.error(f"Fehler beim Initialisieren des OpenAI Clients: {e}") # Feedback in app.py
        return None

# perform_llm_analysis erhält jetzt die Clients als Argumente
# NEUE PARAMETER: follow_up_question und previous_analysis_results
def perform_llm_analysis(
    dataframe: pd.DataFrame,
    openai_client: OpenAI,
    mongo_client, # Wird von app.py übergeben, basierend auf der Checkbox
    additional_context_text:str ="",
    filename:str ="",
    follow_up_question: str = None,
    previous_analysis_results: dict = None
):
    if openai_client is None:
        return {"error": "OpenAI Client ist nicht initialisiert. Bitte API-Schlüssel prüfen."}

    data_as_csv_string = dataframe.to_csv(index=False)
    detailed_data_summary_dict = get_basic_dataframe_summary(dataframe)

    # Formatieren der Zusammenfassung für das LLM (wird immer benötigt)
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
                    
                    # Dieser Block ist für die Konvertierung der Keys zuständig
                    top_values_for_json = {} 
                    if isinstance(stats.get('top_values'), dict):
                        for k, v in stats['top_values'].items(): 
                            if isinstance(k, pd.Timestamp):
                                top_values_for_json[k.isoformat()] = v 
                            else:
                                top_values_for_json[str(k)] = v 
                        
                        # Stelle sicher, dass json.dumps auf das konvertierte Dictionary angewendet wird
                        if top_values_for_json:
            
                            formatted_summary_for_llm += f"    - Häufigste Werte (Top 5): {json.dumps(top_values_for_json)}\n" 
                        else:
                            formatted_summary_for_llm += f"    - Häufigste Werte (Top 5): Keine oder konnten nicht serialisiert werden.\n"
                    else:
                         formatted_summary_for_llm += f"    - Häufigste Werte (Top 5): Keine oder ungültiges Format.\n"
    formatted_summary_for_llm += "---\n"

    # Abruf historischer Daten
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
            for i, insight in enumerate(retrieved_historical_insights):
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

    previous_insights_summary_for_prompt = "Keine vorherige Analyse als direkter Kontext übergeben."
    if previous_analysis_results:
        previous_insights_summary_for_prompt = "\n\n**Zusammenfassung der Kernaussagen der direkt vorhergehenden Analyse (zur Beantwortung der Folgefrage):**\n"
        if previous_analysis_results.get("insights") and isinstance(previous_analysis_results["insights"], list) and previous_analysis_results["insights"]: # Check, ob Liste nicht leer ist
            for i, insight in enumerate(previous_analysis_results["insights"][:3]):
                previous_insights_summary_for_prompt += (
                    f"- **Vorheriger Insight Titel:** {insight.get('title', 'N/A')}\n"
                    f"  **Beschreibung:** {insight.get('description', 'N/A')}\n"
                )
        else: # Fall abdecken, dass "insights" leer ist oder nicht existiert
            previous_insights_summary_for_prompt += "Die vorherige Analyse enthielt keine spezifischen Kernaussagen im erwarteten Format.\n"
        
        previous_insights_summary_for_prompt += (
             f"**Gesamtzusammenfassung der vorherigen Analyse:** {previous_analysis_results.get('overall_summary', 'N/A')}\n"
        )

    if follow_up_question and previous_analysis_results:
        st.info(f"Führe fokussierte Folgeanalyse für die Frage durch: '{follow_up_question}'...")
        system_prompt_follow_up = (
            "Du bist ein erfahrener Business Analyst und Datenwissenschaftler. Deine Aufgabe ist es, eine spezifische Folgefrage zu einer bereits durchgeführten Datenanalyse präzise und datengestützt zu beantworten. "
            "Nutze die Originaldaten (als CSV), die bereitgestellte Datenübersicht, die Zusammenfassung der direkt vorhergehenden Analyse und **den Kontext aus ähnlichen historischen Erkenntnissen (falls vorhanden und relevant)** als Basis für deine Antwort. "
            "Deine Antwort soll sich voll und ganz auf die gestellte Folgefrage konzentrieren."
            "\n\n"
            "**Deine Vorgehensweise (Chain of Thought):**"
            "\n1.  **Verstehe die spezifische Frage:** Was genau soll im Detail untersucht oder beantwortet werden?"
            "\n2.  **Beziehe vorherige Analyseergebnisse direkt ein:** Welche konkreten Erkenntnisse (Titel, Beschreibung, Gesamtzusammenfassung) aus der vorherigen Analyse sind für die Beantwortung der aktuellen Frage relevant? Nutze sie als Ausgangspunkt oder Kontrast."
            "\n3.  **Berücksichtige historische Erkenntnisse:** Prüfe, ob die bereitgestellten historischen Erkenntnisse für die aktuelle Folgefrage relevant sind und beziehe sie ggf. in deine Überlegungen ein."
            "\n4.  **Gezielte Datenuntersuchung (Rohdaten & Übersicht):** Analysiere die bereitgestellten Rohdaten (CSV) und die Datenübersicht erneut, diesmal aber mit dem alleinigen Fokus auf Aspekte, die zur Beantwortung der Folgefrage beitragen."
            "\n5.  **Formuliere die Antwort klar und direkt:** Gib eine präzise Antwort auf die Frage. Erstelle neue 'insights', die sich ausschließlich auf die Erkenntnisse zu dieser spezifischen Frage beziehen."
            "\n6.  **Belege deine Aussagen fundiert:** Liefere konkrete Datenpunkte aus der CSV oder der Zusammenfassung, die deine neuen Erkenntnisse stützen."
            "\n7.  **Neue Insight-IDs:** Generiere für die Erkenntnisse dieser Folgeanalyse neue, eindeutige `insight_id`s (z.B. FOLLOWUP_TREND_SALES_Q3, FOLLOWUP_ANOMALY_RETURNS_CH)."
            "\n8.  **Aktualisiere `overall_summary` und `potential_next_questions`:** Die `overall_summary` soll die Kernantwort auf die Folgefrage und die wichtigsten neuen Erkenntnisse zusammenfassen. Die `potential_next_questions` sollen sich logisch aus der beantworteten Frage und den neuen Ergebnissen ergeben."
            "\n\n"
            "**Wichtige Anweisungen für deine Antwort:**"
            "\n- **Absoluter Fokus auf die Frage:** Deine gesamte Antwort, insbesondere die generierten 'insights', müssen sich primär und direkt auf die Beantwortung der `follow_up_question` beziehen."
            "\n- **Kontextintegration:** Nutze die Informationen aus `previous_analysis_summary_for_prompt`, `formatted_summary_for_llm` und `historical_insights_context` intelligent, um deine Antwort zu stützen oder zu kontextualisieren."
            "\n- **JSON-Format strikt einhalten:** Die Ausgabe muss weiterhin dem bekannten JSON-Format (data_overview, insights, overall_summary, potential_next_questions) entsprechen. `data_overview` kann die ursprüngliche Übersicht wiedergeben oder ggf. Aspekte hervorheben, die für die Folgefrage relevant sind."
        )

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
        system_prompt_initial = (
            "Du bist ein erfahrener Business Analyst und Datenwissenschaftler. Deine Mission ist es, für einen Business-Anwender (z.B. einen Manager ohne tiefgehende Statistikkenntnisse) die absolut wichtigsten, umsetzbarsten und überraschenden Erkenntnisse aus den bereitgestellten Geschäftsdaten zu extrahieren. Konzentriere dich auf das, was wirklich zählt und einen Unterschied macht."
            "\n\n"
            "**Deine Vorgehensweise (Chain of Thought):**"
            "\n1.  **Datenübersicht gewinnen:** Verstehe die Spalten und die Art der Daten (z.B. Zeitreihen, kategorische Daten, numerische Werte). Nutze die bereitgestellte vorab generierte Datenübersicht als Ausgangspunkt."
            "\n2.  **Hypothesen bilden:** Welche typischen geschäftskritischen Fragen könnten diese Daten beantworten? (z.B. Umsatzentwicklung, regionale Unterschiede, Produktperformance, Retourenprobleme, Saisonalität)."
            "\n3.  **Gezielte Analyse:** Suche aktiv nach:"
            "\n    * **Signifikante Trends:** Positive/Negative Entwicklungen über die Zeit oder über Kategorien hinweg."
            "\n    * **Auffällige Saisonalitäten:** Wiederkehrende Muster (z.B. monatlich, quartalsweise)."
            "\n    * **Anomalien/Ausreißer:** Unerwartete Spitzen oder Einbrüche, die von der Norm abweichen."
            "\n    * **Regionale Probleme/Chancen:** Unterschiede in Metriken zwischen verschiedenen Regionen, Standorten, etc."
            "\n    * **Korrelationen/Abhängigkeiten:** Interessante Zusammenhänge zwischen verschiedenen Spalten (z.B. 'Wenn Marketingausgaben für Produkt X steigen, steigt auch der Umsatz')."
            "\n    * **Neue und unerwartete Muster:** Achte auch auf Muster, die nicht in den bisher bekannten Kategorien oder historischen Beispielen auftauchen, aber dennoch signifikant sind."
            "\n    * **Kombinierte & Segment-spezifische Muster:** Suche aktiv nach Mustern, die erst durch die Kombination mehrerer Variablen oder durch Betrachtung spezifischer Datensegmente offensichtlich werden." 
            "\n    * **Kontraintuitive Erkenntnisse:** Identifiziere Erkenntnisse, die etablierten Annahmen widersprechen könnten oder eine neue Perspektive auf die Geschäftsdaten eröffnen." 
            "\n    * **Langsame, stetige Veränderungen:** Analysiere, ob es langsame, aber stetige Veränderungen gibt, die über längere Zeiträume signifikant werden, auch wenn sie kurzfristig unscheinbar wirken." 
            "\n    * **Indirekte Zusammenhänge:** Achte auf Korrelationen zwischen scheinbar unabhängigen Metriken. Gibt es indirekte Zusammenhänge?" 
            "\n4.  **Kontextualisierung und Quantifizierung:** Beschreibe jede Erkenntnis klar und verständlich. Gib immer den betroffenen Bereich (z.B. Produktgruppe, Region), den Zeitraum und, wenn möglich, eine Quantifizierung des Impacts (z.B. 'Umsatzsteigerung um 15%', 'Retourenquote 5% über Durchschnitt')."
            "\n5.  **Belege deine Aussagen:** Für jede Erkenntnis, liefere konkrete Datenbeispiele (z.B. 'Zeile 42: Umsatz Produkt A in Q3 war X, während der Durchschnitt Y war') oder verweise auf die relevanten Zeilen/Spalten der bereitgestellten CSV-Daten."
            "\n6.  **Beziehe historische Erkenntnisse ein:** Wenn historische Erkenntnisse bereitgestellt wurden, kommentiere, ob ähnliche Muster in den aktuellen Daten fortbestehen, sich geändert haben oder ob erwartete Muster ausbleiben. Identifiziere auch vollständig neue Muster, die in den historischen Daten nicht vorkamen."
            "\n\n"
            "**Wichtige Anweisungen für deine Antwort:**"
            "\n- **Fokus auf Relevanz und Überraschungswert:** Nicht jede kleine Schwankung ist eine Erkenntnis. Finde das, was wirklich ins Auge sticht oder eine geschäftliche Entscheidung beeinflussen könnte. Priorisiere Erkenntnisse, die für einen menschlichen Analysten, der die Daten nur oberflächlich sichtet, nicht sofort ersichtlich wären oder als überraschend gelten." 
            "\n- **Präzision:** Sei exakt in deinen Beschreibungen und Datenreferenzen."
            "\n- **Konsistenz:** Achte auf logische Zusammenhänge in deiner Analyse. Beziehe auch bekannte Muster oder historische Erkenntnisse (falls bereitgestellt) in deine Betrachtung ein, um deren Fortbestehen, Abweichungen oder deren Fehlen zu kommentieren."
            "\n- **Erkennung neuer Muster:** Sei explizit angewiesen, auch gänzlich neue oder unerwartete Muster zu identifizieren, die nicht unbedingt bekannten Kategorien entsprechen oder in bereitgestellten historischen Daten auftauchten."
            "\n- **Effizienz:** Nutze die bereitgestellten Datenpunkte effizient. Wenn Du aus der Datenbank geladene Referenzinformationen hast, integriere sie, aber wiederhole nicht redundante Informationen."
            "\n- **Vermeide Allgemeinplätze:** Statt 'Daten zeigen Schwankungen', sage 'Im September 2024 stiegen die Retouren in der Schweiz auffällig um 25% im Vergleich zum Vormonat an, siehe Zeilen 100-115 der CSV-Daten'."
            "\n\n"
            "**Ausgabeformat (strikt einzuhalten):**"
            "**Ausgabeformat (strikt einzuhalten):**"
            "\nGib deine Analyseergebnisse IMMER im folgenden JSON-Format aus:"
            "\n```json\n"
            "{\n"
            "  \"data_overview\": {\n"
            "    \"columns\": [\"Spaltenname1\", \"Spaltenname2\"],\n"
            "    \"potential_data_types\": [\"z.B. Datum\", \"z.B. Numerisch\", \"z.B. Kategorie\"], \n"
            "    \"rows\": 123, \n"
            "    \"key_business_focus\": \"string\" \n"
            "  },\n"
            "  \"insights\": [\n"
            "    {\n"
            "      \"insight_id\": \"string\",\n"
            "      \"title\": \"string\",\n"
            "      \"type\": \"string\",\n"
            "      \"description\": \"string\",\n"
            "      \"affected_area\": \"string\",\n"
            "      \"period\": \"string\",\n"
            "      \"quantitative_impact\": \"string\",\n"
            "      \"supporting_data_points\": [],\n"
            "      \"confidence_level\": \"string\"\n"
            "    }\n"
            "  ],\n"
            "  \"overall_summary\": \"string\",\n"
            "  \"potential_next_questions\": [\"string\"]\n"
            "}\n"
            "```\n"
            "Wenn keine signifikanten Erkenntnisse gefunden werden, gib ein leeres 'insights'-Array zurück und eine entsprechende Zusammenfassung. Sei absolut präzise bei der Angabe von Datenpunkten, die deine Erkenntnisse stützen. **Beziehe dich auf die erste Zeile der CSV als Spaltenüberschriften.**"
        )
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


    # --- Gemeinsame Logik für API Call (Initial- oder Folgeanalyse) ---
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

    # --- Gemeinsame Logik für ZWEITE LLM-ANFRAGE: Selbstüberprüfung und Korrektur ---
    st.info("Führe Selbstüberprüfung der Analyse durch...")
    review_system_prompt = (
        "Du bist ein extrem detailorientierter Qualitätssicherungs-Spezialist für Datenanalysen von Business Analysten. Deine Aufgabe ist es, eine zuvor von einer KI generierte Datenanalyse (im JSON-Format) auf Herz und Nieren zu prüfen. Gehe dabei vor wie ein strenger Gutachter."
        "\n\n"
        "**Deine Prüfkriterien:**"
        "\n1.  **JSON-Schema-Konformität:** Entspricht die Antwort EXAKT dem im ursprünglichen System-Prompt vorgegebenen JSON-Schema? Achte auf Feldnamen, Datentypen und die Gesamtstruktur. Keine zusätzlichen Felder, keine fehlenden Pflichtfelder."
        "\n2.  **Logische Konsistenz und Plausibilität:**"
        "\n    * Sind die identifizierten 'insights' tatsächlich aus den Originaldaten (CSV) und der bereitgestellten Datenübersicht ableitbar? Überprüfe die `supporting_data_points` sorgfältig gegen die Rohdaten."
        "\n    * Ist die `description` jeder Erkenntnis klar, verständlich und tatsächlich eine geschäftskritische Information?"
        "\n    * Ist der `quantitative_impact` korrekt berechnet oder abgeleitet?"
        "\n    * Sind die `affected_area` und `period` präzise und korrekt?"
        "\n    * Wurden die neuen Erkenntnisse sinnvoll in den Kontext der bereitgestellten historischen Erkenntnisse (falls vorhanden) gesetzt? Wird kommentiert, wenn ein erwarteter Trend ausbleibt oder ein neuer auftaucht?"
        "\n    * **Bei Folgeanalysen:** Wurde die spezifische `follow_up_question` adressiert und beantwortet? Spiegeln die 'insights' die Ergebnisse dieser spezifischen Untersuchung wider?"
        "\n3.  **Einhaltung der ursprünglichen Anweisungen:**"
        "\n    * Wurde der Fokus auf *wichtige* und *umsetzbare* Erkenntnisse gelegt, oder sind es triviale Beobachtungen?"
        "\n    * Ist die Kontextualisierung gelungen (z.B. 'Retourenanstieg in der Schweiz')?"
        "\n    * Sind die `supporting_data_points` spezifisch genug, um die Aussage zu belegen (Vermeide vage Referenzen)? Achte darauf, dass Referenzen auf Zeilen und Spalten der CSV-Daten korrekt sind."
        "\n    * Ist das Feld `potential_next_questions` sinnvoll gefüllt und leitet zu tiefergehenden Analysen an?"
        "\n    * Ist der `data_overview` korrekt und hilfreich und spiegelt die Eingabedaten wider?"
        "\n4.  **Qualität der Sprache:** Prägnant, professionell, keine Umgangssprache."
        "\n\n"
        "**Deine Aufgabe:**"
        "\n- Wenn Fehler, Inkonsistenzen oder Verbesserungspotenziale gefunden werden, korrigiere die JSON-Antwort und gib die **optimierte, korrigierte JSON-Antwort** aus."
        "\n- Wenn die Analyse bereits perfekt ist und alle Kriterien erfüllt, gib die **originale JSON-Antwort** unverändert aus."
        "\n- Gib IMMER nur die finale, gültige JSON-Struktur aus, ohne zusätzlichen Text davor oder danach, außer im Markdown-Codeblock ```json ... ```."
        "\n- Stelle sicher, dass alle Felder des JSON-Schemas (wie im ursprünglichen Prompt definiert) vorhanden sind."
    )

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

    # --- Finale Parselogik ---
    parsed_results = None
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
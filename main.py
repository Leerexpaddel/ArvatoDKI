import streamlit as st
import pandas as pd
import os
from dotenv import load_dotenv
import json

from core.analyzer import perform_llm_analysis, get_openai_client_internal
from services.db import get_mongo_client, save_insight

st.set_page_config(layout="wide", page_title="Attention Guiding App", page_icon="📊")

load_dotenv()
mongo_uri = os.getenv("MONGO_URI")
mongo_db_name = os.getenv("MONGO_DB_NAME", "attention_guiding_db")

@st.cache_resource
def _get_openai_client_cached():
    return get_openai_client_internal()
openai_client = _get_openai_client_cached()

@st.cache_resource
def _get_mongo_client_cached():
    return get_mongo_client(mongo_uri, mongo_db_name)
mongo_client = _get_mongo_client_cached()

# Session State Initialisierung
session_defaults = {
    "analysis_results": None,
    "prompt_text_area_content": "",
    "last_analyzed_filename": "",
    "last_analyzed_dataframe": None,
    "use_mongodb_for_analysis": False,
    "use_mongodb_for_follow_up": False,
    "selected_follow_up_question": None,
    "current_follow_up_question_for_saving": None,
    "show_full_table_preview": False
}
for key, value in session_defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

with open("static/style.css", "r") as f:
    style = f.read()
st.markdown(f"<style>{style}</style>", unsafe_allow_html=True)

st.title("📊 Attention Guiding für Excel-Daten")
st.markdown(
    "Laden Sie eine Excel-, CSV- oder (Kontext-)Textdatei hoch, um **automatisch wichtige Trends und besondere Werte** "
    "durch Künstliche Intelligenz identifizieren zu lassen. "
    "Das System konzentriert sich auf die **konsistente** Erkennung von Mustern und ermöglicht iterative Folgeanalysen."
)

if openai_client is None:
    st.warning("⚠️ OpenAI API Key nicht gefunden oder Client-Initialisierung fehlgeschlagen.")
else:
    st.success("✅ OpenAI Client erfolgreich initialisiert.")

if mongo_client is None:
    st.warning("⚠️ MongoDB Verbindung fehlgeschlagen. Speichern und historische Daten sind nicht verfügbar.")
else:
    st.success("✅ MongoDB Client erfolgreich initialisiert.")

st.markdown("---")

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📁 Daten hochladen")
    uploaded_file = st.file_uploader(
        "Wählen Sie eine Excel-, CSV- oder Textdatei aus",
        type=["xlsx", "csv", "txt"],
        key="main_data_uploader",
        help="Laden Sie eine Excel- oder CSV-Datei für die Analyse hoch. Eine Textdatei kann als zusätzlicher Kontext dienen."
    )

    st.subheader("📝 Zusätzlichen Kontext/Prompt eingeben")
    st.session_state.prompt_text_area_content = st.text_area(
        "Geben Sie hier zusätzlichen Text ein:",
        value=st.session_state.prompt_text_area_content,
        height=150,
        help="Zusätzlicher Kontext für die KI-Analyse (z.B. spezifische Fragen, Fokusbereiche).",
        key="text_area_manual_input"
    )
    uploaded_prompt_file = st.file_uploader(
        "Oder laden Sie eine Prompt-Textdatei (.txt) hoch:",
        type=["txt"],
        key="prompt_file_uploader",
        help="Lädt den Inhalt dieser Datei in das obige Textfeld."
    )
    if uploaded_prompt_file is not None:
        try:
            prompt_file_content = uploaded_prompt_file.read().decode("utf-8")
            if prompt_file_content != st.session_state.prompt_text_area_content:
                st.session_state.prompt_text_area_content = prompt_file_content
                st.success("Prompt-Datei erfolgreich geladen und Textfeld aktualisiert!")
                st.rerun()
        except Exception as e:
            st.error(f"Fehler beim Lesen der Prompt-Datei: {e}")

    df_to_analyze = None
    additional_context_from_txt_main_upload = ""

    if uploaded_file is not None:
        if st.session_state.last_analyzed_filename != uploaded_file.name:
            st.session_state.analysis_results = None
            st.session_state.last_analyzed_dataframe = None
            st.session_state.selected_follow_up_question = None
            st.session_state.current_follow_up_question_for_saving = None
            st.info("Neue Datei erkannt. Analysekontext wurde zurückgesetzt.")
        st.session_state.last_analyzed_filename = uploaded_file.name
        file_extension = uploaded_file.name.split('.')[-1].lower()
        try:
            if file_extension == "xlsx":
                df_to_analyze = pd.read_excel(uploaded_file)
            elif file_extension == "csv":
                df_to_analyze = pd.read_csv(uploaded_file)
            elif file_extension == "txt":
                additional_context_from_txt_main_upload = uploaded_file.read().decode("utf-8")
                st.success("Textdatei (als Hauptdatei) erfolgreich hochgeladen!")
                st.info("Inhalt der Textdatei wird als zusätzlicher Kontext verwendet.")
                with st.expander("Inhalt der Textdatei aus Haupt-Upload anzeigen"):
                    st.code(additional_context_from_txt_main_upload)
            else:
                st.error("Nicht unterstütztes Dateiformat für Analyse. Bitte .xlsx oder .csv wählen.")
                df_to_analyze = None
        except Exception as e:
            st.error(f"Fehler beim Lesen der Datei '{uploaded_file.name}': {e}")
            df_to_analyze = None

        if df_to_analyze is not None:
            st.session_state.last_analyzed_dataframe = df_to_analyze
            st.subheader("Vorschau der hochgeladenen Daten:")
            st.dataframe(df_to_analyze.head())
            with st.expander("Ganze Tabelle anzeigen/ausblenden"):
                st.dataframe(df_to_analyze)
    elif st.session_state.last_analyzed_dataframe is not None:
        st.info("Sie haben eine Textdatei hochgeladen. Diese wird als Kontext für die zuletzt analysierten Daten verwendet.")
        df_to_analyze = st.session_state.last_analyzed_dataframe
        st.subheader("Vorschau der zuletzt analysierten Daten (wird für Analyse verwendet):")
        st.dataframe(df_to_analyze.head())
        with st.expander("Ganze Tabelle anzeigen/ausblenden"):
            st.dataframe(df_to_analyze)

    if st.session_state.last_analyzed_dataframe is not None and openai_client is not None:
        st.markdown("---")
        analysis_button_col, mongodb_checkbox_col_main = st.columns([0.6, 0.4])
        with mongodb_checkbox_col_main:
            st.session_state.use_mongodb_for_analysis = st.checkbox(
                "MongoDB für **neue** Analyse nutzen?",
                value=st.session_state.use_mongodb_for_analysis,
                help="Historische Erkenntnisse aus MongoDB für eine komplett neue Analyse als Kontext nutzen.",
                disabled=(mongo_client is None),
                key="mongodb_main_analysis_checkbox"
            )
            if mongo_client is None and st.session_state.use_mongodb_for_analysis:
                st.caption("MongoDB nicht verbunden, Option hat keine Auswirkung.")
        with analysis_button_col:
            if st.button("🚀 Neue Analyse starten", help="Startet eine komplett neue Analyse der Daten."):
                st.session_state.analysis_results = None
                st.session_state.selected_follow_up_question = None
                st.session_state.current_follow_up_question_for_saving = None
                final_additional_context = st.session_state.prompt_text_area_content
                if additional_context_from_txt_main_upload:
                    final_additional_context += "\n\n--- Kontext aus Haupt-TXT-Upload ---\n" + additional_context_from_txt_main_upload
                client_to_pass_main = mongo_client if st.session_state.use_mongodb_for_analysis else None
                with st.spinner("Führe neue Datenanalyse durch..."):
                    st.session_state.analysis_results = perform_llm_analysis(
                        st.session_state.last_analyzed_dataframe,
                        openai_client,
                        client_to_pass_main,
                        final_additional_context,
                        st.session_state.last_analyzed_filename
                    )
                st.rerun()

with col2:
    st.subheader("✨ Analyse Ergebnisse:")
    if st.session_state.analysis_results is not None:
        results = st.session_state.analysis_results
        filename_for_saving = st.session_state.last_analyzed_filename

        if results.get("is_follow_up"):
            st.info(f"Dies sind die Ergebnisse der Folgeanalyse zur Frage: \"{results.get('answered_question')}\"")
        if "error" in results:
            st.error(results["error"])
            if "raw_response" in results:
                st.expander("Rohantwort des LLM anzeigen").code(results["raw_response"])
        else:
            with st.expander("Komplette JSON-Antwort anzeigen"):
                st.json(results)
            st.markdown("---")
            st.subheader("💡 Kern-Erkenntnisse")
            if "insights" in results and results["insights"]:
                for i, insight in enumerate(results["insights"]):
                    with st.expander(f"**{insight.get('title', 'Kein Titel')}** (Typ: {insight.get('type', 'Unbekannt')})"):
                        st.write(f"**Beschreibung:** {insight.get('description', 'N/A')}")
                        st.write(f"**Betroffener Bereich:** {insight.get('affected_area', 'N/A')}")
                        st.write(f"**Zeitraum:** {insight.get('period', 'N/A')}")
                        st.write(f"**Quantitativer Impact:** {insight.get('quantitative_impact', 'N/A')}")
                        st.write(f"**Confidence Level:** {insight.get('confidence_level', 'N/A')}")
                        if insight.get('supporting_data_points'):
                            st.write("**Stützende Datenpunkte:**")
                            for dp_idx, dp in enumerate(insight['supporting_data_points']):
                                st.markdown(f"- **Referenz {dp_idx+1}:** {dp.get('row_reference', 'N/A')}, **Spalte:** {dp.get('column_reference', 'N/A')}, **Wert:** {dp.get('value', 'N/A')}, **Erklärung:** {dp.get('explanation', 'N/A')}")
                        else:
                            st.info("Keine spezifischen Datenpunkte für diesen Insight angegeben.")
            else:
                st.info("Keine spezifischen Kern-Erkenntnisse gefunden oder vom LLM generiert.")

            st.markdown("---")
            st.subheader("📊 Datenübersicht (vom LLM generiert)")
            st.json(results.get("data_overview", {}))

            st.markdown("---")
            st.subheader("📝 Gesamt-Zusammenfassung")
            st.write(results.get("overall_summary", "N/A"))

            if results.get("potential_next_questions"):
                st.markdown("---")
                st.subheader("🔍 Folgeanalyse starten")
                options_for_selectbox = ["Bitte wählen Sie eine Frage..."] + [str(q) for q in results["potential_next_questions"]]
                current_selection_idx = 0
                if st.session_state.selected_follow_up_question in options_for_selectbox:
                    current_selection_idx = options_for_selectbox.index(st.session_state.selected_follow_up_question)
                st.session_state.selected_follow_up_question = st.selectbox(
                    "Wählen Sie eine Frage für eine detailliertere Untersuchung:",
                    options=options_for_selectbox,
                    index=current_selection_idx,
                    key="follow_up_selectbox_key"
                )

                st.session_state.use_mongodb_for_follow_up = st.checkbox(
                    "MongoDB für **diese Folgeanalyse** nutzen?",
                    value=st.session_state.use_mongodb_for_follow_up,
                    help="Historische Erkenntnisse aus MongoDB spezifisch für die Beantwortung dieser Folgefrage als Kontext nutzen.",
                    disabled=(mongo_client is None),
                    key="mongodb_follow_up_checkbox"
                )
                if mongo_client is None and st.session_state.use_mongodb_for_follow_up: 
                    st.caption("MongoDB nicht verbunden, Option hat keine Auswirkung.")

                if st.button("🚀 Folgeanalyse zu dieser Frage starten",
                             disabled=(st.session_state.selected_follow_up_question == "Bitte wählen Sie eine Frage..." or st.session_state.selected_follow_up_question is None)):
                    if st.session_state.last_analyzed_dataframe is not None and openai_client is not None:
                        st.session_state.current_follow_up_question_for_saving = st.session_state.selected_follow_up_question
                        final_additional_context = st.session_state.prompt_text_area_content
                        if additional_context_from_txt_main_upload:
                            final_additional_context += "\n\n--- Kontext aus Haupt-TXT-Upload ---\n" + additional_context_from_txt_main_upload
                        client_to_pass_ff = mongo_client if st.session_state.use_mongodb_for_follow_up else None
                        with st.spinner(f"Führe Folgeanalyse für '{st.session_state.selected_follow_up_question}' durch..."):
                            st.session_state.analysis_results = perform_llm_analysis(
                                st.session_state.last_analyzed_dataframe,
                                openai_client,
                                client_to_pass_ff, 
                                final_additional_context,
                                st.session_state.last_analyzed_filename,
                                follow_up_question=st.session_state.selected_follow_up_question,
                                previous_analysis_results=results
                            )
                        st.rerun()
                    else:
                        st.error("Voraussetzungen für die Folgeanalyse nicht erfüllt.")

            st.markdown("---")
            save_col, download_col = st.columns(2)
            with save_col:
                if mongo_client is not None:
                    if st.button("💾 Ergebnisse in MongoDB speichern", help="Speichert die angezeigten Analyseergebnisse."):
                        if "insights" in results and isinstance(results["insights"], list) and results["insights"]:
                            saved_count = 0
                            error_count = 0
                            for insight in results["insights"]:
                                insight_to_save = insight.copy()
                                insight_to_save["analysis_timestamp"] = pd.Timestamp.now().isoformat()
                                insight_to_save["source_filename"] = filename_for_saving
                                insight_to_save["is_follow_up_insight"] = results.get("is_follow_up", False)
                                if results.get("is_follow_up"):
                                    answered_question = st.session_state.get("current_follow_up_question_for_saving")
                                    if not answered_question:
                                        answered_question = results.get("answered_question")
                                    if answered_question:
                                        insight_to_save["answered_question_for_insight"] = answered_question
                                inserted_id = save_insight(mongo_client, insight_to_save)
                                if inserted_id:
                                    saved_count += 1
                                else:
                                    error_count += 1
                            if saved_count > 0:
                                st.success(f"{saved_count} Insight(s) erfolgreich in MongoDB gespeichert.")
                            if error_count > 0:
                                st.error(f"{error_count} Insight(s) konnten nicht gespeichert werden.")
                            if saved_count == 0 and error_count == 0:
                                st.info("Keine neuen Insights zum Speichern vorhanden in den aktuellen Ergebnissen.")
                        else:
                            st.warning("Keine Insights in den aktuellen Ergebnissen zum Speichern gefunden.")
                else:
                    st.info("Keine aktive MongoDB-Verbindung. Speichern ist nicht möglich.")
                    st.caption("Bitte stelle sicher, dass MONGO_URI korrekt konfiguriert ist und die Datenbank erreichbar ist.")
            with download_col:
                results_json_string = json.dumps(results, indent=2, ensure_ascii=False)
                download_filename_base = os.path.splitext(filename_for_saving)[0] if filename_for_saving else "analyse"
                timestamp_download = pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')
                download_filename = f"{download_filename_base}_ergebnisse_{timestamp_download}.json"
                st.download_button(
                    label="⬇️ JSON herunterladen",
                    data=results_json_string,
                    file_name=download_filename,
                    mime="application/json",
                    help="Lädt die gesamten aktuellen Analyseergebnisse als JSON-Datei herunter."
                )
    elif st.session_state.last_analyzed_dataframe is None and not uploaded_file:
        st.info("Laden Sie eine Excel- oder CSV-Datei hoch und klicken Sie auf 'Neue Analyse starten', um Ergebnisse zu sehen.")
    elif st.session_state.last_analyzed_dataframe is not None and openai_client is None:
        st.warning("OpenAI Client nicht initialisiert. Analyse nicht möglich.")
# db_manager.py
import os
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure
# import streamlit as st
import pandas as pd

# KEIN @st.cache_resource HIER! Es wird in app.py initialisiert und übergeben.
def get_mongo_client(mongo_uri: str, db_name: str):
    if not mongo_uri:
        # st.error("MONGO_URI nicht in Umgebungsvariablen gefunden. Datenbankverbindung nicht möglich.")
        # Streamlit Fehlermeldungen werden in app.py angezeigt
        return None
    
    try:
        client = MongoClient(mongo_uri)
        client.admin.command('ping')
        # st.success("✅ MongoDB Client erfolgreich initialisiert und verbunden!") # Feedback in app.py
        return client
    except ConnectionFailure as e:
        # st.error(f"❌ MongoDB Verbindungsfehler: {e}. Bitte überprüfe die MONGO_URI und IP-Whitelist.")
        return None
    except OperationFailure as e:
        # st.error(f"❌ MongoDB Authentifizierungs-/Operationsfehler: {e}. Bitte überprüfe Benutzername und Passwort in der MONGO_URI.")
        return None
    except Exception as e:
        # st.error(f"❌ Unerwarteter Fehler beim Initialisieren des MongoDB Clients: {e}")
        return None

# Funktion zum Speichern von Insights
# Jetzt wird der mongo_client als Argument übergeben
def save_insight(mongo_client: MongoClient, insight_data: dict):
    if mongo_client:
        try:
            db_name = os.getenv("MONGO_DB_NAME", "attention_guiding_db")
            collection_name = os.getenv("MONGO_COLLECTION_INSIGHTS", "insights")
            
            db = mongo_client[db_name] # Nutze den übergebenen Client
            insights_collection = db[collection_name]
            
            result = insights_collection.insert_one(insight_data)
            return result.inserted_id
        except Exception as e:
            # st.error(f"Fehler beim Speichern des Insights in MongoDB: {e}") # Feedback in app.py
            return None
    return None

# Funktion zum Abrufen ähnlicher Insights
# Jetzt wird der mongo_client als Argument übergeben
def get_similar_insights(mongo_client: MongoClient, query_text: str, limit: int = 5) -> list:
    if mongo_client:
        try:
            db_name = os.getenv("MONGO_DB_NAME", "attention_guiding_db")
            collection_name = os.getenv("MONGO_COLLECTION_INSIGHTS", "insights")
            
            db = mongo_client[db_name] # Nutze den übergebenen Client
            insights_collection = db[collection_name]
            
            latest_insights = list(insights_collection.find().sort([('analysis_timestamp', -1)]).limit(limit))
            
            for insight in latest_insights:
                if '_id' in insight:
                    insight['_id'] = str(insight['_id'])
            
            return latest_insights
        except Exception as e:
            # st.error(f"Fehler beim Abrufen ähnlicher Insights aus MongoDB: {e}") # Feedback in app.py
            return []
    return []

# Optional: Funktion zum Speichern von Zusammenfassungen der Rohdaten
# Jetzt wird der mongo_client als Argument übergeben
def save_raw_data_summary(mongo_client: MongoClient, filename: str, summary_data: dict):
    if mongo_client:
        try:
            db_name = os.getenv("MONGO_DB_NAME", "attention_guiding_db")
            collection_name = os.getenv("MONGO_COLLECTION_RAW_DATA", "raw_data_summaries")
            
            db = mongo_client[db_name] # Nutze den übergebenen Client
            raw_data_collection = db[collection_name]
            
            doc_to_insert = {
                "filename": filename,
                "timestamp": pd.Timestamp.now().isoformat(),
                "summary": summary_data
            }
            result = raw_data_collection.insert_one(doc_to_insert)
            return result.inserted_id
        except Exception as e:
            # st.error(f"Fehler beim Speichern der Rohdaten-Zusammenfassung in MongoDB: {e}") # Feedback in app.py
            return None
    return None
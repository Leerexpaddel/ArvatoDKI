import os
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure
import pandas as pd
import certifi
import streamlit as st

def get_mongo_client(mongo_uri: str, db_name: str):
    """
    Initialisiert und gibt einen MongoDB-Client zurück.
    """
    if not mongo_uri:
        st.error("MONGO_URI nicht in Umgebungsvariablen gefunden. Datenbankverbindung nicht möglich.")
        return None
    try:
        client = MongoClient(mongo_uri, tlsCAFile=certifi.where())
        client.admin.command('ping')
        st.success("✅ MongoDB Client erfolgreich initialisiert und verbunden!")
        return client
    except ConnectionFailure as e:
        st.error(f"❌ MongoDB Verbindungsfehler: {e}. Bitte überprüfe die MONGO_URI und IP-Whitelist.")
        return None
    except OperationFailure as e:
        st.error(f"❌ MongoDB Authentifizierungs-/Operationsfehler: {e}. Bitte überprüfe Benutzername und Passwort in der MONGO_URI.")
        return None
    except Exception as e:
        return None

def save_insight(mongo_client: MongoClient, insight_data: dict):
    """
    Speichert ein Insight-Dokument in der MongoDB.
    """
    if mongo_client:
        try:
            db_name = os.getenv("MONGO_DB_NAME", "attention_guiding_db")
            collection_name = os.getenv("MONGO_COLLECTION_INSIGHTS", "insights")
            db = mongo_client[db_name]
            insights_collection = db[collection_name]
            result = insights_collection.insert_one(insight_data)
            return result.inserted_id
        except Exception:
            return None
    return None

def get_similar_insights(mongo_client: MongoClient, query_text: str, limit: int = 5) -> list:
    """
    Gibt die neuesten Insights aus der MongoDB zurück.
    """
    if mongo_client:
        try:
            db_name = os.getenv("MONGO_DB_NAME", "attention_guiding_db")
            collection_name = os.getenv("MONGO_COLLECTION_INSIGHTS", "insights")
            db = mongo_client[db_name]
            insights_collection = db[collection_name]
            latest_insights = list(insights_collection.find().sort([('analysis_timestamp', -1)]).limit(limit))
            for insight in latest_insights:
                if '_id' in insight:
                    insight['_id'] = str(insight['_id'])
            return latest_insights
        except Exception:
            return []
    return []

def save_raw_data_summary(mongo_client: MongoClient, filename: str, summary_data: dict):
    """
    Speichert eine Zusammenfassung der Rohdaten in der MongoDB.
    """
    if mongo_client:
        try:
            db_name = os.getenv("MONGO_DB_NAME", "attention_guiding_db")
            collection_name = os.getenv("MONGO_COLLECTION_RAW_DATA", "raw_data_summaries")
            db = mongo_client[db_name]
            raw_data_collection = db[collection_name]
            doc_to_insert = {
                "filename": filename,
                "timestamp": pd.Timestamp.now().isoformat(),
                "summary": summary_data
            }
            result = raw_data_collection.insert_one(doc_to_insert)
            return result.inserted_id
        except Exception:
            return None
    return None
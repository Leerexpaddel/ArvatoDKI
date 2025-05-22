# Attention Guiding App 📊

Willkommen zur Attention Guiding App! Diese Anwendung hilft Ihnen, wichtige Trends und besondere Werte in Ihren Excel- oder CSV-Daten mithilfe von Künstlicher Intelligenz (KI) zu identifizieren. Sie wurde entwickelt, um Muster wie Saisonalität, negative Entwicklungen oder Ausreißer konsistent zu erkennen.

## Funktionen

* **Dateiupload:** Laden Sie Excel- (.xlsx), CSV- (.csv) oder Textdateien (.txt) hoch.
* **Zusätzlicher Kontext:** Geben Sie zusätzlichen Text als Kontext oder spezifische Anweisungen für die KI-Analyse ein oder laden Sie eine Textdatei als Prompt hoch.
* **KI-gestützte Analyse:** Lassen Sie Ihre Daten von einem Großen Sprachmodell (LLM) analysieren, um Kern-Erkenntnisse, Datenübersichten, Zusammenfassungen und potenzielle nächste Fragen zu erhalten.
* **Zweistufiger Analyseprozess:** Eine Initialanalyse mit anschließender Selbstüberprüfung durch die KI sorgt für höhere Qualität und Formatkonsistenz.
* **MongoDB-Integration (optional):** Nutzen Sie MongoDB, um historische Erkenntnisse in die Analyse einzubeziehen.
* **Ergebnisse speichern:** Speichern Sie die generierten Erkenntnisse nach Bestätigung in einer MongoDB-Datenbank.
* **Ergebnisse herunterladen:** Laden Sie die vollständigen Analyseergebnisse als JSON-Datei herunter.
* **Benutzerfreundliche Oberfläche:** Eine klare, schrittweise Führung durch den Analyseprozess.

## Voraussetzungen

Bevor Sie die Anwendung starten können, stellen Sie sicher, dass Sie Folgendes installiert und eingerichtet haben:

1. **Python 3.9 oder höher:** Die Anwendung wurde mit Python 3.13 getestet.
   👉 [Python herunterladen](https://www.python.org/downloads/)

2. **pip:** Der Python-Paketmanager (wird normalerweise mit Python installiert).

3. **OpenAI API Key:** Für die KI-Analyse ist ein API-Schlüssel von OpenAI erforderlich.
   👉 [OpenAI Plattform](https://platform.openai.com/account/api-keys)

4. **MongoDB Atlas Konto (optional, aber empfohlen):** Für Speicherung und Abruf historischer Daten.
   👉 [MongoDB Atlas](https://www.mongodb.com/cloud/atlas)

   **Wichtig für MongoDB:**

   * Notieren Sie sich Ihre **Verbindungs-URI**.
   * Fügen Sie Ihre **aktuelle IP-Adresse zur IP-Whitelist** hinzu.

## Installation und Einrichtung

### 1. Projekt herunterladen

Falls Sie das Projekt noch nicht haben, klonen Sie es per Git oder laden Sie es als ZIP-Datei herunter und entpacken Sie es.

### 2. Virtuelle Umgebung einrichten

Erstellen Sie eine virtuelle Umgebung:

```bash
python -m venv venv
```

Aktivieren Sie die virtuelle Umgebung:

**Unter Windows:**

```bash
.\venv\Scripts\activate
```

**Unter macOS / Linux:**

```bash
source venv/bin/activate
```

### 3. Abhängigkeiten installieren

Installieren Sie die Abhängigkeiten über `requirements.txt`:

```bash
pip install -r requirements.txt
```

Falls Sie die Datei selbst anlegen müssen, sollte sie folgenden Inhalt haben:

```
streamlit
pandas
python-dotenv
openai
pymongo
dnspython
```

### 4. Umgebungsvariablen konfigurieren

Erstellen Sie eine `.env`-Datei im Projektverzeichnis und tragen Sie Folgendes ein:

```dotenv
# OpenAI API Key (erforderlich)
OPENAI_API_KEY="sk-<...IHREN_SCHLÜSSEL_HIER_EINSETZEN...>"

# (Optional) Modellwahl – Standard ist "gpt-4o-mini"
# OPENAI_MODEL="gpt-4o-mini"

# (Optional) MongoDB Atlas URI
MONGO_URI="mongodb+srv://<...IHREN_MONGODB_URI_HIER_EINSETZEN...>"

# Name der MongoDB-Datenbank
MONGO_DB_NAME="attention_guiding_db"

# MongoDB Collections
MONGO_COLLECTION_INSIGHTS="insights"
MONGO_COLLECTION_RAW_DATA="raw_data_summaries"
```

**Hinweis:** Speichern Sie die Datei **ohne** `.txt`-Endung – nur `.env`.

## Projektstruktur

Ihre Projektstruktur sollte folgendermaßen aussehen:

```
.
├── .env                      # Umgebungsvariablen
├── app.py                   # Hauptanwendung (Streamlit)
├── llm_analyzer.py          # Logik für LLM-Analyse
├── db_manager.py            # MongoDB-Verwaltung
├── utils.py                 # Hilfsfunktionen
├── requirements.txt         # Python-Abhängigkeiten
└── README.md                # Anleitung
```

## Anwendung starten

1. Aktivieren Sie die virtuelle Umgebung:

   ```bash
   source venv/bin/activate
   ```

   *(unter Windows: `.\venv\Scripts\activate`)*

2. Starten Sie die App:

   ```bash
   streamlit run app.py
   ```

Die App sollte sich automatisch im Webbrowser unter `http://localhost:8501` öffnen.

## Verwendung der App

1. **Datei hochladen:** Klicken Sie auf "Wählen Sie eine Excel-, CSV- oder Textdatei aus".

2. **Zusätzlicher Kontext:** Geben Sie Anweisungen oder laden Sie eine zusätzliche Textdatei hoch.

3. **MongoDB-Nutzung (optional):**

   * Checkbox aktivieren, um historische Erkenntnisse aus MongoDB zu nutzen.
   * Ist die Verbindung erfolgreich, werden ältere Einträge automatisch beim Prompt ergänzt.

4. **Analyse starten:** Klicken Sie auf "🚀 Analyse starten".

5. **Ergebnisse prüfen:** Die App zeigt:

   * **Kern-Erkenntnisse**
   * **Datenübersicht**
   * **Gesamt-Zusammenfassung**
   * **Nächste Schritte / Fragen**

6. **Ergebnisse speichern oder exportieren:**

   * 💾 **MongoDB speichern**
   * ⬇️ **JSON herunterladen**# attention-guiding-app
# attention-guiding-app
# attention-guiding-app

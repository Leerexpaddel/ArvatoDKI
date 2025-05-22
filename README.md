# Attention Guiding App 📊

Willkommen zur Attention Guiding App! Diese Anwendung hilft Ihnen, wichtige Trends und besondere Werte in Ihren Excel- oder CSV-Daten mithilfe von Künstlicher Intelligenz (KI) zu identifizieren. Sie wurde entwickelt, um Muster wie Saisonalität, negative Entwicklungen oder Ausreißer konsistent zu erkennen.

## Funktionen

* **Dateiupload:** Laden Sie Excel- (.xlsx), CSV- (.csv) oder Textdateien (.txt) hoch.
* **Zusätzlicher Kontext:** Geben Sie zusätzlichen Text als Kontext oder spezifische Anweisungen für die KI-Analyse ein oder laden Sie eine Textdatei als Prompt hoch.
* **KI-gestützte Analyse:** Lassen Sie Ihre Daten von einem Großen Sprachmodell (LLM) analysieren, um Kern-Erkenntnisse, Datenübersichten, Zusammenfassungen und potenzielle nächste Fragen zu erhalten.
* **Zweistufiger Analyseprozess:** Eine Initialanalyse mit anschließender Selbstüberprüfung durch die KI sorgt für höhere Qualität und Formatkonsistenz.
* **MongoDB-Integration (optional):** Nutzen Sie MongoDB, um historische Erkenntnisse in die Analyse einzubeziehen oder Analyseergebnisse zu speichern.
* **Ergebnisse speichern:** Speichern Sie die generierten Erkenntnisse nach Bestätigung in einer MongoDB-Datenbank.
* **Ergebnisse herunterladen:** Laden Sie die vollständigen Analyseergebnisse als JSON-Datei herunter.
* **Benutzerfreundliche Oberfläche:** Eine klare, schrittweise Führung durch den Analyseprozess.

## Voraussetzungen

Bevor Sie die Anwendung starten können, stellen Sie sicher, dass Sie Folgendes installiert und eingerichtet haben:

1. **Python 3.9 oder höher** (getestet mit Python 3.13)  
   👉 [Python herunterladen](https://www.python.org/downloads/)
2. **pip:** Der Python-Paketmanager (normalerweise mit Python installiert)
3. **Git:** Für das Klonen des Repositories  
   👉 [Git herunterladen](https://git-scm.com/downloads)
4. **OpenAI API Key** (erforderlich für die Analyse)  
   👉 [OpenAI Plattform](https://platform.openai.com/account/api-keys)
5. **MongoDB Atlas Konto (optional, aber empfohlen)**  
   👉 [MongoDB Atlas](https://www.mongodb.com/cloud/atlas)

   **Wichtig für MongoDB:**
   * Notieren Sie sich Ihre **Verbindungs-URI**
   * Fügen Sie Ihre **aktuelle IP-Adresse zur IP-Whitelist** in MongoDB Atlas hinzu

## Installation und Einrichtung

### 1. Projekt herunterladen (Klonen)

```bash
git clone https://github.com/Leerexpaddel/attention-guiding-app.git
cd attention-guiding-app
````

### 2. Virtuelle Umgebung einrichten

Erstellen Sie eine virtuelle Umgebung:

```bash
python -m venv venv
```

Aktivieren Sie sie:

**Unter Windows:**

```bash
.\venv\Scripts\activate
```

**Unter macOS / Linux:**

```bash
source venv/bin/activate
```

### 3. Abhängigkeiten installieren

```bash
pip install -r requirements.txt
```

Falls `requirements.txt` fehlt oder leer ist, sollte sie folgenden Inhalt enthalten:

```txt
streamlit
pandas
python-dotenv
openai
pymongo
dnspython
```

### 4. Umgebungsvariablen konfigurieren

Die Anwendung benötigt API-Schlüssel und weitere Konfigurationsdaten in einer `.env`-Datei. Diese ist **nicht im Repository enthalten** (siehe `.gitignore`) – aus Sicherheitsgründen.


Erstellen Sie eine Datei `.env` mit folgendem Inhalt:

```dotenv
# OpenAI API Key (erforderlich)
OPENAI_API_KEY="sk-IHREN_OPENAI_API_SCHLUESSEL_HIER_EINSETZEN"
MONGO_URI="Mongo URL einsetzten"
MONGO_DB_NAME="attention_guiding_db"
MONGO_COLLECTION_INSIGHTS="insights"
MONGO_COLLECTION_RAW_DATA="raw_data_summaries"

```
**Hinweis:**

* Die `.env`-Datei **darf niemals** zu Git hinzugefügt werden. Dies wird durch die `.gitignore` verhindert.
* Speichern Sie sie exakt als `.env` (nicht `.env.txt` o. Ä.)

**Projektstruktur (Beispiel)**

```dotenv
.
├── .gitignore
├── app.py
├── llm_analyzer.py
├── db_manager.py
├── utils.py
├── requirements.txt
└──  README.md 
```

*(Die lokale `.env` und der `venv`-Ordner sind nicht versioniert und erscheinen hier nicht.)*

## Anwendung starten

Aktivieren Sie Ihre virtuelle Umgebung und starten Sie die Streamlit-App:

```bash
streamlit run app.py
```

Die App öffnet sich im Browser unter: [http://localhost:8501](http://localhost:8501)

## Verwendung der App

1. **Datei hochladen:** Excel-, CSV- oder Textdatei auswählen.
2. **Kontext hinzufügen:** Text eingeben oder Textdatei hochladen.
3. **(Optional) MongoDB verwenden:**

   * Aktivieren Sie die Checkboxen:

     * "MongoDB für neue Analyse nutzen?"
     * "MongoDB für diese Folgeanalyse nutzen?"
   * Die Ergebnisse werden verwendet oder gespeichert, je nach Verfügbarkeit der Verbindung.
4. **Analyse starten:**

   * 🚀 Neue Analyse starten
   * 🚀 Folgeanalyse zu dieser Frage starten
5. **Ergebnisse anzeigen lassen:**

   * Kern-Erkenntnisse
   * Datenübersicht
   * Gesamt-Zusammenfassung
   * Nächste Schritte / Fragen
6. **Ergebnisse speichern oder exportieren:**

   * 💾 In MongoDB speichern (sofern verbunden)
   * ⬇️ JSON herunterladen

# ArvatoDKI

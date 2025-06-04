# ArvatoDKI

Dieses Projekt analysiert Inhalte mithilfe von LLM-Technologien und kombiniert diese mit Datenbank- und Dienstlogik.

## Projektstruktur

```plaintext
ArvatoDKI/
├── core/              # Zentrale Geschäftslogik, z. B. LLM-Analyse
│   └── analyzer.py
├── services/          # Externe Dienste wie Datenbank, Hilfsfunktionen
│   ├── db.py
│   └── utils.py
├── prompts/           # Prompt-Vorlagen für LLMs
│   └── default_prompt.txt
├── static/            # CSS- oder andere statische Dateien
│   └── style.css
├── templates/         # Ausgabe- oder Prompt-Templates
│   └── result_template.md
├── main.py            # Einstiegspunkt in die Anwendung
├── requirements.txt   # Projektabhängigkeiten
├── .env               # Umgebungsvariablen
├── .gitignore         # Git-Konfigurationsdateien
└── tests/             # Unit-Tests
```

## Setup

1. Virtuelle Umgebung erstellen:

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

2. Abhängigkeiten installieren:

```bash
pip install -r requirements.txt
```

3. `.env`-Datei anpassen und starten mit:

```bash
python main.py
```

## Hinweise

- Prompts können in `prompts/` verwaltet und versioniert werden.
- Styling und Templates sind modular ausgelagert.

import re
import pandas as pd

def extract_json_from_string(text):
    """
    Extrahiert einen JSON-Block aus einem gegebenen String.
    Nützlich, wenn das LLM zusätzlichen Text um das JSON herum ausgibt.
    Gibt den JSON-String zurück oder None, falls kein JSON gefunden wurde.
    """
    match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        return match.group(1)
    match = re.search(r"(\{.*?\})", text, re.DOTALL)
    if match:
        return match.group(1)
    return None

def get_basic_dataframe_summary(df):
    """
    Erstellt eine Zusammenfassung eines DataFrames mit Infos zu Zeilen, Spalten,
    Datentypen, numerischen und kategorischen Spalten.
    Gibt ein Dictionary mit den wichtigsten Kennzahlen zurück.
    """
    summary = {
        "num_rows": len(df),
        "num_cols": len(df.columns),
        "column_names": df.columns.tolist(),
        "column_dtypes": {col: str(df[col].dtype) for col in df.columns},
        "numerical_summary": {},
        "categorical_summary": {}
    }
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            desc = df[col].describe().to_dict()
            for k, v in desc.items():
                if pd.isna(v):
                    desc[k] = None
                elif isinstance(v, (float, int)):
                    desc[k] = round(v, 2) if isinstance(v, float) else v
            summary["numerical_summary"][col] = desc
        else:
            summary["categorical_summary"][col] = {
                "unique_values": df[col].nunique(),
                "top_values": df[col].value_counts().nlargest(5).to_dict()
            }
    return summary
import re
import pandas as pd
import numpy as np

def extract_json_from_string(text):
    """
    Extrahiert einen JSON-Block aus einem gegebenen String.
    Nützlich, wenn das LLM zusätzlichen Text um das JSON herum ausgibt.
    Gibt den JSON-String zurück oder None, falls kein JSON gefunden wurde.
    """
    match = re.search(r"```json\s*(\{.*?})\s*```", text, re.DOTALL)
    if match:
        return match.group(1)
    match = re.search(r"(\{.*?})", text, re.DOTALL)
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
            # Ensure all values in desc are JSON serializable
            for k, v in desc.items():
                if pd.isna(v):
                    desc[k] = None
                elif isinstance(v, (np.integer, np.int64)): # Handle numpy integers
                    desc[k] = int(v)
                elif isinstance(v, (np.floating, np.float64)): # Handle numpy floats
                    desc[k] = float(v)
                elif isinstance(v, (float, int)): # Standard types
                    desc[k] = round(v, 2) if isinstance(v, float) else v
                # Add other type checks if necessary
            summary["numerical_summary"][col] = desc
        elif pd.api.types.is_object_dtype(df[col]) or pd.api.types.is_categorical_dtype(df[col]):
            unique_values_list = []
            # Check for Timestamps or other non-serializable types in unique values
            for val in df[col].unique():
                if isinstance(val, pd.Timestamp):
                    unique_values_list.append(val.isoformat())
                else:
                    unique_values_list.append(str(val)) # Convert all to string as a fallback

            if len(unique_values_list) > 10:
                unique_values_list = unique_values_list[:10] + ['...']
            
            top_vals_dict = {}
            # Ensure keys and values in top_values are JSON serializable
            for k, v in df[col].value_counts().nlargest(5).to_dict().items():
                key_str = str(k.isoformat() if isinstance(k, pd.Timestamp) else k)
                val_item = int(v) if isinstance(v, np.integer) else (float(v) if isinstance(v, np.floating) else v)
                top_vals_dict[key_str] = val_item

            summary["categorical_summary"][col] = {
                "unique_count": df[col].nunique(),
                "top_values": top_vals_dict,
                "unique_sample": unique_values_list
            }
    return summary

# --- NEUE FUNKTION: KPIs zum DataFrame hinzufügen ---
def add_calculated_kpis_to_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Berechnet wichtige KPIs pro Zeile des DataFrames und fügt sie als neue Spalten hinzu.
    """
    # Defensive Kopie, um SettingWithCopyWarning zu vermeiden
    df_copy = df.copy()

    # Stellen sicher, dass relevante Spalten numerisch sind
    numeric_cols = [
        'No Orders', 'EUR Gross Sales', 'No Returns', 'EUR Returns',
        'EUR Write-Offs', 'EUR Chargebacks', 'EUR Chargebacks.1',
        'EUR Net Dunning Level 1', 'EUR Net Dunning Level 2'
    ]
    for col in numeric_cols:
        df_copy[col] = pd.to_numeric(df_copy[col], errors='coerce').fillna(0) # Standard 0 bei Konvertierungsfehler

    # Berechne Quoten/Durchschnitte, Vermeidung von Division durch Null
    # Verwende temporäre Spalten für saubere Division
    df_copy['EUR Gross Sales_clean'] = df_copy['EUR Gross Sales'].replace(0, pd.NA)
    df_copy['No Orders_clean'] = df_copy['No Orders'].replace(0, pd.NA)

    # KPIs pro Zeile berechnen
    df_copy['calculated_return_rate_eur'] = (df_copy['EUR Returns'] / df_copy['EUR Gross Sales_clean']).fillna(0).round(4)
    df_copy['calculated_avg_order_value'] = (df_copy['EUR Gross Sales_clean'] / df_copy['No Orders_clean']).fillna(0).round(2)
    df_copy['calculated_chargeback_rate_eur'] = (df_copy['EUR Chargebacks.1'] / df_copy['EUR Gross Sales_clean']).fillna(0).round(4)
    df_copy['calculated_dunning_level1_ratio'] = (df_copy['EUR Net Dunning Level 1'] / df_copy['EUR Gross Sales_clean']).fillna(0).round(4)
    df_copy['calculated_dunning_level2_ratio'] = (df_copy['EUR Net Dunning Level 2'] / df_copy['EUR Gross Sales_clean']).fillna(0).round(4)
    df_copy['calculated_write_off_ratio'] = (df_copy['EUR Write-Offs'] / df_copy['EUR Gross Sales_clean']).fillna(0).round(4)

    # Zeitliche Normalisierung für Aggregation/Analyse
    df_copy['Date'] = pd.to_datetime(df_copy['Date'], errors='coerce')
    df_copy['Normalized_Month_For_Analysis'] = df_copy['Date'].dt.to_period('M').astype(str)

    # Entferne temporäre Hilfsspalten
    df_copy = df_copy.drop(columns=['EUR Gross Sales_clean', 'No Orders_clean'], errors='ignore')

    return df_copy

# --- NEUE FUNKTION: Höher aggregierte KPIs (z.B. über alle Monate) ---
def get_higher_level_aggregations(df_with_kpis: pd.DataFrame) -> dict:
    """
    Erstellt höher aggregierte KPIs (z.B. über alle Monate hinweg)
    für globale Vergleiche nach Land, Zahlungsmethode und deren Kombinationen.
    """
    kpi_cols = [
        'EUR Gross Sales', 'EUR Returns', 'No Orders', 'EUR Chargebacks.1',
        'EUR Write-Offs', 'EUR Net Dunning Level 1', 'EUR Net Dunning Level 2'
    ]
    for col in kpi_cols:
        if col not in df_with_kpis.columns:
            print(f"Warnung: Spalte {col} fehlt für höhere Aggregation.")
            # Im Fehlerfall leere Dicts zurückgeben, damit der Hauptprozess weiterlaufen kann
            return {
                "by_country_payment_method": "Keine Aggregation nach Land & Zahlungsmethode verfügbar.",
                "by_country": "Keine Aggregation nach Land verfügbar.",
                "by_payment_method": "Keine Aggregation nach Zahlungsmethode verfügbar."
            }

    aggregations = {}

    # Aggregation nach Land UND Zahlungsmethode (bestehend)
    global_agg_country_pm = df_with_kpis.groupby(['Country', 'Payment Method']).agg(
        total_gross_sales=('EUR Gross Sales', 'sum'),
        total_returns_eur=('EUR Returns', 'sum'),
        total_orders=('No Orders', 'sum'),
        total_chargebacks_eur=('EUR Chargebacks.1', 'sum'),
        total_write_offs_eur=('EUR Write-Offs', 'sum'),
        total_dunning_level1_eur=('EUR Net Dunning Level 1', 'sum'),
        total_dunning_level2_eur=('EUR Net Dunning Level 2', 'sum')
    ).reset_index()

    global_agg_country_pm['global_return_rate_eur'] = (global_agg_country_pm['total_returns_eur'] / global_agg_country_pm['total_gross_sales'].replace(0, pd.NA)).fillna(0).round(4)
    global_agg_country_pm['global_avg_order_value'] = (global_agg_country_pm['total_gross_sales'] / global_agg_country_pm['total_orders'].replace(0, pd.NA)).fillna(0).round(2)
    global_agg_country_pm['global_chargeback_rate_eur'] = (global_agg_country_pm['total_chargebacks_eur'] / global_agg_country_pm['total_gross_sales'].replace(0, pd.NA)).fillna(0).round(4)
    # ... (weitere globale Quoten für Country/PM)
    global_agg_country_pm['global_dunning_level1_ratio'] = (global_agg_country_pm['total_dunning_level1_eur'] / global_agg_country_pm['total_gross_sales'].replace(0, pd.NA)).fillna(0).round(4)
    global_agg_country_pm['global_dunning_level2_ratio'] = (global_agg_country_pm['total_dunning_level2_eur'] / global_agg_country_pm['total_gross_sales'].replace(0, pd.NA)).fillna(0).round(4)
    global_agg_country_pm['global_write_off_ratio'] = (global_agg_country_pm['total_write_offs_eur'] / global_agg_country_pm['total_gross_sales'].replace(0, pd.NA)).fillna(0).round(4)
    aggregations["by_country_payment_method"] = global_agg_country_pm.to_csv(index=False)

    # NEU: Aggregation nur nach Land
    global_agg_country = df_with_kpis.groupby(['Country']).agg(
        total_gross_sales=('EUR Gross Sales', 'sum'),
        total_returns_eur=('EUR Returns', 'sum'),
        total_orders=('No Orders', 'sum'),
        total_chargebacks_eur=('EUR Chargebacks.1', 'sum'),
        total_write_offs_eur=('EUR Write-Offs', 'sum'),
        total_dunning_level1_eur=('EUR Net Dunning Level 1', 'sum'),
        total_dunning_level2_eur=('EUR Net Dunning Level 2', 'sum')
    ).reset_index()
    global_agg_country['global_return_rate_eur'] = (global_agg_country['total_returns_eur'] / global_agg_country['total_gross_sales'].replace(0, pd.NA)).fillna(0).round(4)
    global_agg_country['global_avg_order_value'] = (global_agg_country['total_gross_sales'] / global_agg_country['total_orders'].replace(0, pd.NA)).fillna(0).round(2)
    global_agg_country['global_chargeback_rate_eur'] = (global_agg_country['total_chargebacks_eur'] / global_agg_country['total_gross_sales'].replace(0, pd.NA)).fillna(0).round(4)
    # ... (weitere globale Quoten für Country)
    global_agg_country['global_dunning_level1_ratio'] = (global_agg_country['total_dunning_level1_eur'] / global_agg_country['total_gross_sales'].replace(0, pd.NA)).fillna(0).round(4)
    global_agg_country['global_dunning_level2_ratio'] = (global_agg_country['total_dunning_level2_eur'] / global_agg_country['total_gross_sales'].replace(0, pd.NA)).fillna(0).round(4)
    global_agg_country['global_write_off_ratio'] = (global_agg_country['total_write_offs_eur'] / global_agg_country['total_gross_sales'].replace(0, pd.NA)).fillna(0).round(4)
    aggregations["by_country"] = global_agg_country.to_csv(index=False)

    # NEU: Aggregation nur nach Zahlungsmethode
    global_agg_pm = df_with_kpis.groupby(['Payment Method']).agg(
        total_gross_sales=('EUR Gross Sales', 'sum'),
        total_returns_eur=('EUR Returns', 'sum'),
        total_orders=('No Orders', 'sum'),
        total_chargebacks_eur=('EUR Chargebacks.1', 'sum'),
        total_write_offs_eur=('EUR Write-Offs', 'sum'),
        total_dunning_level1_eur=('EUR Net Dunning Level 1', 'sum'),
        total_dunning_level2_eur=('EUR Net Dunning Level 2', 'sum')
    ).reset_index()
    global_agg_pm['global_return_rate_eur'] = (global_agg_pm['total_returns_eur'] / global_agg_pm['total_gross_sales'].replace(0, pd.NA)).fillna(0).round(4)
    global_agg_pm['global_avg_order_value'] = (global_agg_pm['total_gross_sales'] / global_agg_pm['total_orders'].replace(0, pd.NA)).fillna(0).round(2)
    global_agg_pm['global_chargeback_rate_eur'] = (global_agg_pm['total_chargebacks_eur'] / global_agg_pm['total_gross_sales'].replace(0, pd.NA)).fillna(0).round(4)
    # ... (weitere globale Quoten für PM)
    global_agg_pm['global_dunning_level1_ratio'] = (global_agg_pm['total_dunning_level1_eur'] / global_agg_pm['total_gross_sales'].replace(0, pd.NA)).fillna(0).round(4)
    global_agg_pm['global_dunning_level2_ratio'] = (global_agg_pm['total_dunning_level2_eur'] / global_agg_pm['total_gross_sales'].replace(0, pd.NA)).fillna(0).round(4)
    global_agg_pm['global_write_off_ratio'] = (global_agg_pm['total_write_offs_eur'] / global_agg_pm['total_gross_sales'].replace(0, pd.NA)).fillna(0).round(4)
    aggregations["by_payment_method"] = global_agg_pm.to_csv(index=False)

    return aggregations


# --- NEUE FUNKTION: Top N Anomalien extrahieren ---
def get_top_n_anomalies(df_with_kpis: pd.DataFrame, n: int = 5) -> dict:
    """
    Identifiziert und extrahiert die Top N auffälligsten Zeilen
    basierend auf verschiedenen KPIs aus dem angereicherten DataFrame.
    Stellt sicher, dass die benötigten KPI-Spalten existieren.
    """
    anomalies = {"n": n} # Speichert n für den Prompt

    # Liste der KPI-Spalten, die für die nlargest/nsmallest Operationen verwendet werden
    # Füge hier nur Spalten hinzu, die direkt im DataFrame existieren und numerisch sind
    sort_cols = {
        'EUR Gross Sales': True, # True for nlargest
        'calculated_return_rate_eur': True,
        'calculated_chargeback_rate_eur': True,
        'EUR Net Dunning Level 2': True,
        'calculated_avg_order_value': False # False for nsmallest (lowest avg order value)
    }

    # Filter für Write-Offs > 0 (nicht Top N, sondern alle relevanten)
    write_offs_df = df_with_kpis[df_with_kpis['EUR Write-Offs'] > 0]
    anomalies['all_write_offs_gt_0'] = write_offs_df.to_csv(index=False) if not write_offs_df.empty else "Keine spezifischen Write-Offs gefunden."

    for col, is_largest in sort_cols.items():
        if col in df_with_kpis.columns and pd.api.types.is_numeric_dtype(df_with_kpis[col]):
            # Filtern NaN-Werte für Sortierung, falls vorhanden
            temp_df = df_with_kpis.dropna(subset=[col])
            if not temp_df.empty:
                if is_largest:
                    anomalies[f'top_{col.lower().replace(" ", "_")}'] = temp_df.nlargest(n, col).to_csv(index=False)
                else:
                    anomalies[f'lowest_{col.lower().replace(" ", "_")}'] = temp_df.nsmallest(n, col).to_csv(index=False)
            else:
                anomalies[f'top_{col.lower().replace(" ", "_")}'] = "Nicht genügend Daten für diese Anomalie."
        else:
            anomalies[f'top_{col.lower().replace(" ", "_")}'] = f"Spalte '{col}' nicht verfügbar oder nicht numerisch."


    # Spezifische Handhabung für `EUR Chargebacks` (die 0-1 Spalte)
    # Könnte hier analysiert werden, wenn sie konsistent Werte > 0 hat, die nicht in Chargebacks.1 sind
    # For now, it's covered by the general "Umgang mit unbekannten/irrelevanten Spalten" in the prompt.

    return anomalies
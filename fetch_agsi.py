"""
Scarica il livello di riempimento (%) degli stoccaggi di gas per i paesi Ue
dall'API AGSI (https://agsi.gie.eu) e genera un CSV pronto per Datawrapper,
ordinato in modo decrescente come nel grafico originale.

Richiede la variabile d'ambiente AGSI_API_KEY (la tua chiave personale,
gratuita, ottenibile su https://agsi.gie.eu/account).
"""

import csv
import os
import sys
import time
from datetime import date, timedelta

import requests

API_KEY = os.environ.get("AGSI_API_KEY")
if not API_KEY:
    sys.exit("Errore: variabile d'ambiente AGSI_API_KEY non impostata.")

# Nome da mostrare in italiano -> codice paese usato dall'API AGSI
# "EU" e' un caso speciale: usa il parametro type=eu invece di country=
PAESI = {
    "Portogallo": "PT",
    "Spagna": "ES",
    "Italia": "IT",
    "Polonia": "PL",
    "Danimarca": "DK",
    "Austria": "AT",
    "Ungheria": "HU",
    "Unione europea": "EU",
    "Bulgaria": "BG",
    "Repubblica Ceca": "CZ",
    "Francia": "FR",
    "Lettonia": "LV",
    "Belgio": "BE",
    "Romania": "RO",
    "Germania": "DE",
    "Slovacchia": "SK",
    "Croazia": "HR",
    "Svezia": "SE",
    "Paesi Bassi": "NL",
}

HEADERS = {"x-key": API_KEY}
BASE_URL = "https://agsi.gie.eu/api"

oggi = date.today()
da_data = (oggi - timedelta(days=10)).isoformat()
a_data = oggi.isoformat()

righe = []
gas_day_piu_recente = None

for nome_it, codice in PAESI.items():
    params = {
        "from": da_data,
        "to": a_data,
        "size": 30,
    }
    if codice == "EU":
        params["type"] = "eu"
    else:
        params["country"] = codice

    resp = requests.get(BASE_URL, headers=HEADERS, params=params, timeout=30)
    resp.raise_for_status()
    payload = resp.json()

    entries = payload.get("data", [])
    if not entries:
        print(f"Attenzione: nessun dato per {nome_it} ({codice})", file=sys.stderr)
        time.sleep(0.3)
        continue

    # Prendi il record con la data (gasDayStart) piu' recente
    record = max(entries, key=lambda e: e["gasDayStart"])

    valore_full = record.get("full")
    if valore_full is None:
        print(f"Attenzione: campo 'full' mancante per {nome_it}", file=sys.stderr)
        time.sleep(0.3)
        continue

    if gas_day_piu_recente is None or record["gasDayStart"] > gas_day_piu_recente:
        gas_day_piu_recente = record["gasDayStart"]

    # Colore: azzurro per l'Italia, verde per l'Unione europea, verde acqua per gli altri
    if nome_it == "Italia":
        colore = "#66c2ff"
    elif nome_it == "Unione europea":
        colore = "#93c464"
    else:
        colore = "#4d9494"

    righe.append({
        "paese": nome_it,
        "riempimento_%": round(float(valore_full), 1),
        "colore": colore,
    })
    time.sleep(0.3)  # cortesia verso l'API (limite 60 chiamate/minuto)

if not righe:
    sys.exit("Errore: nessun dato scaricato per nessun paese, controlla la API key.")

# Ordina come nel grafico originale: dal valore piu' alto al piu' basso
righe.sort(key=lambda r: r["riempimento_%"], reverse=True)

out_path = os.path.join(os.path.dirname(__file__), "data.csv")
with open(out_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["paese", "riempimento_%", "colore"])
    writer.writeheader()
    writer.writerows(righe)

print(f"CSV generato con {len(righe)} righe. Ultimo gas day: {gas_day_piu_recente}")

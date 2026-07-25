"""
Scarica il livello di riempimento (%) degli stoccaggi di gas per i paesi Ue
dall'API AGSI (https://agsi.gie.eu) e genera un CSV pronto per Datawrapper,
ordinato in modo decrescente come nel grafico originale.

Richiede la variabile d'ambiente AGSI_API_KEY (la tua chiave personale,
gratuita, ottenibile su https://agsi.gie.eu/account).
"""

import csv
import json
import os
import sys
import time
from datetime import date, timedelta

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

MESI_ITALIANI = {
    1: "gennaio", 2: "febbraio", 3: "marzo", 4: "aprile",
    5: "maggio", 6: "giugno", 7: "luglio", 8: "agosto",
    9: "settembre", 10: "ottobre", 11: "novembre", 12: "dicembre",
}

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

# Sessione con retry automatici: se il server risponde lentamente o con
# errori temporanei (5xx, 429), ritenta fino a 5 volte con attesa crescente
session = requests.Session()
retry_strategy = Retry(
    total=5,
    backoff_factor=2,  # attende 2s, 4s, 8s, 16s, 32s tra i tentativi
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"],
)
session.mount("https://", HTTPAdapter(max_retries=retry_strategy))

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

    resp = session.get(BASE_URL, headers=HEADERS, params=params, timeout=60)
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

# Genera il sottotitolo in italiano, es: "Riempimento al 24 luglio"
anno, mese, giorno = (int(x) for x in gas_day_piu_recente.split("-"))
sottotitolo = f"Riempimento al {giorno} {MESI_ITALIANI[mese]}"

metadata = {
    "describe": {
        "intro": sottotitolo
    }
}

metadata_path = os.path.join(os.path.dirname(__file__), "metadata.json")
with open(metadata_path, "w", encoding="utf-8") as f:
    json.dump(metadata, f, ensure_ascii=False, indent=2)

print(f"metadata.json generato con sottotitolo: '{sottotitolo}'")

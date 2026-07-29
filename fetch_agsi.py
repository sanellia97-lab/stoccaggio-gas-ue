"""
Scarica il livello di riempimento (%) degli stoccaggi di gas per i paesi Ue
dall'API AGSI (https://agsi.gie.eu) e genera due CSV pronti per Datawrapper
(uno in italiano, uno in inglese), ordinati in modo decrescente come nel
grafico originale, oltre ai relativi file di metadati con il sottotitolo
automatico.

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

MESI_INGLESI = {
    1: "January", 2: "February", 3: "March", 4: "April",
    5: "May", 6: "June", 7: "July", 8: "August",
    9: "September", 10: "October", 11: "November", 12: "December",
}

API_KEY = os.environ.get("AGSI_API_KEY")
if not API_KEY:
    sys.exit("Errore: variabile d'ambiente AGSI_API_KEY non impostata.")

# Codice paese usato dall'API AGSI -> (nome italiano, nome inglese)
# "EU" e' un caso speciale: usa il parametro type=eu invece di country=
PAESI = {
    "PT": ("Portogallo", "Portugal"),
    "ES": ("Spagna", "Spain"),
    "IT": ("Italia", "Italy"),
    "PL": ("Polonia", "Poland"),
    "DK": ("Danimarca", "Denmark"),
    "AT": ("Austria", "Austria"),
    "HU": ("Ungheria", "Hungary"),
    "EU": ("Unione europea", "European Union"),
    "BG": ("Bulgaria", "Bulgaria"),
    "CZ": ("Repubblica Ceca", "Czech Republic"),
    "FR": ("Francia", "France"),
    "LV": ("Lettonia", "Latvia"),
    "BE": ("Belgio", "Belgium"),
    "RO": ("Romania", "Romania"),
    "DE": ("Germania", "Germany"),
    "SK": ("Slovacchia", "Slovakia"),
    "HR": ("Croazia", "Croatia"),
    "SE": ("Svezia", "Sweden"),
    "NL": ("Paesi Bassi", "Netherlands"),
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

righe_it = []
righe_en = []
gas_day_piu_recente = None

for codice, (nome_it, nome_en) in PAESI.items():
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
    if codice == "IT":
        colore = "#66c2ff"
    elif codice == "EU":
        colore = "#93c464"
    else:
        colore = "#4d9494"

    valore = round(float(valore_full), 1)
    righe_it.append({"paese": nome_it, "riempimento_%": valore, "colore": colore})
    righe_en.append({"country": nome_en, "filling_%": valore, "color": colore})
    time.sleep(0.3)  # cortesia verso l'API (limite 60 chiamate/minuto)

if not righe_it:
    sys.exit("Errore: nessun dato scaricato per nessun paese, controlla la API key.")

# Ordina come nel grafico originale: dal valore piu' alto al piu' basso
righe_it.sort(key=lambda r: r["riempimento_%"], reverse=True)
righe_en.sort(key=lambda r: r["filling_%"], reverse=True)

cartella = os.path.dirname(__file__)

# --- CSV italiano ---
with open(os.path.join(cartella, "data.csv"), "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["paese", "riempimento_%", "colore"])
    writer.writeheader()
    writer.writerows(righe_it)

# --- CSV inglese ---
with open(os.path.join(cartella, "data_en.csv"), "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["country", "filling_%", "color"])
    writer.writeheader()
    writer.writerows(righe_en)

print(f"CSV generati ({len(righe_it)} righe). Ultimo gas day: {gas_day_piu_recente}")

# --- Metadati (sottotitolo automatico) ---
anno, mese, giorno = (int(x) for x in gas_day_piu_recente.split("-"))

sottotitolo_it = f"Riempimento al {giorno} {MESI_ITALIANI[mese]}"
sottotitolo_en = f"Filled as of {giorno} {MESI_INGLESI[mese]}"

with open(os.path.join(cartella, "metadata.json"), "w", encoding="utf-8") as f:
    json.dump({"describe": {"intro": sottotitolo_it}}, f, ensure_ascii=False, indent=2)

with open(os.path.join(cartella, "metadata_en.json"), "w", encoding="utf-8") as f:
    json.dump({"describe": {"intro": sottotitolo_en}}, f, ensure_ascii=False, indent=2)

print(f"Sottotitoli generati: IT='{sottotitolo_it}' | EN='{sottotitolo_en}'")

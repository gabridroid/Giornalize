"""Archivio delle notizie raccolte (file data/notizie.json).

Ogni aggiornamento aggiunge le notizie nuove a quelle già raccolte, toglie i
doppioni e cancella quelle più vecchie di `giorni_archivio`.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .testo import chiave_link, normalizza_titolo

log = logging.getLogger("giornalize.archivio")

# Due titoli della stessa fonte che condividono almeno questa quota di
# parole sono considerati la stessa notizia (es. ripubblicata in due sezioni).
SOGLIA_TITOLO_QUASI_UGUALE = 0.85
# ...ma solo se pubblicati a meno di queste ore di distanza.
ORE_DOPPIONE = 48


def data(notizia: dict, campo: str = "pubblicato") -> datetime:
    return datetime.fromisoformat(notizia[campo].replace("Z", "+00:00"))


def leggi(percorso: Path) -> list[dict]:
    if not percorso.exists():
        return []
    try:
        with open(percorso, encoding="utf-8") as f:
            dati = json.load(f)
        return dati.get("notizie", []) if isinstance(dati, dict) else dati
    except (json.JSONDecodeError, OSError) as e:
        log.error("Archivio %s illeggibile (%s): riparto da zero", percorso, e)
        return []


def scrivi(percorso: Path, notizie: list[dict], ora: datetime) -> None:
    percorso.parent.mkdir(parents=True, exist_ok=True)
    temporaneo = percorso.with_suffix(".tmp")
    with open(temporaneo, "w", encoding="utf-8") as f:
        json.dump(
            {"aggiornato": ora.strftime("%Y-%m-%dT%H:%M:%SZ"), "notizie": notizie},
            f, ensure_ascii=False, indent=1,
        )
    temporaneo.replace(percorso)


def _parole_titolo(titolo: str) -> frozenset[str]:
    return frozenset(normalizza_titolo(titolo).split())


def _quasi_uguali(a: frozenset[str], b: frozenset[str]) -> bool:
    if a == b:
        return True
    if min(len(a), len(b)) < 4:
        return False
    return len(a & b) / len(a | b) >= SOGLIA_TITOLO_QUASI_UGUALE


def unisci(esistenti: list[dict], nuove: list[dict], ora: datetime, giorni_archivio: int) -> tuple[list[dict], int]:
    """Unisce le notizie nuove all'archivio. Restituisce (archivio, quante
    notizie nuove sono state aggiunte). In caso di doppioni si tiene sempre
    la notizia vista per prima."""
    limite = ora - timedelta(days=giorni_archivio)
    risultato: list[dict] = []
    link_visti: set[str] = set()
    titoli_per_fonte: dict[str, list[tuple[frozenset[str], datetime]]] = {}
    aggiunte = 0
    ids_esistenti = {n["id"] for n in esistenti}

    for notizia in esistenti + nuove:
        quando = data(notizia)
        if quando < limite:
            continue
        chiave = chiave_link(notizia["link"])
        if chiave in link_visti:
            continue
        parole = _parole_titolo(notizia["titolo"])
        precedenti = titoli_per_fonte.setdefault(notizia["fonte"], [])
        if any(
            abs((quando - q).total_seconds()) < ORE_DOPPIONE * 3600 and _quasi_uguali(parole, p)
            for p, q in precedenti
        ):
            continue
        link_visti.add(chiave)
        precedenti.append((parole, quando))
        risultato.append(notizia)
        if notizia["id"] not in ids_esistenti:
            aggiunte += 1

    risultato.sort(key=lambda n: n["pubblicato"], reverse=True)
    return risultato, aggiunte


def scrivi_stato(percorso: Path, stati: dict[str, dict]) -> None:
    """Salva lo stato dell'ultima raccolta di ogni fonte (funziona / errore)."""
    precedente = {}
    if percorso.exists():
        try:
            precedente = json.loads(percorso.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            precedente = {}
    for id_fonte, stato in stati.items():
        vecchio = precedente.get(id_fonte, {})
        # Ricordiamo l'ultima volta in cui la fonte ha funzionato.
        stato["ultimo_successo"] = (
            stato["ora"] if stato["canali_ok"] else vecchio.get("ultimo_successo")
        )
    percorso.parent.mkdir(parents=True, exist_ok=True)
    percorso.write_text(json.dumps(stati, ensure_ascii=False, indent=1), encoding="utf-8")


def leggi_stato(percorso: Path) -> dict[str, dict]:
    try:
        return json.loads(percorso.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def ora_utc() -> datetime:
    return datetime.now(timezone.utc)

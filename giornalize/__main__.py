"""Comandi di Giornalize.

    python -m giornalize aggiorna      raccoglie le notizie e ricostruisce il sito
    python -m giornalize raccogli      solo raccolta (aggiorna data/)
    python -m giornalize costruisci    solo costruzione del sito (cartella site/)
    python -m giornalize prova-fonti   prova tutti i feed e stampa un rapporto
    python -m giornalize prova-fonti ansa ilpost   prova solo alcune fonti
    python -m giornalize aggiungi-post   aggiunge un post dal modulo di GitHub
                                         (testo del modulo nella variabile TESTO_MODULO)
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from . import archivio, instagram
from .config import RADICE, ErroreConfigurazione, carica
from .raccolta import raccogli_fonte, raccogli_tutto
from .sito import Costruttore

CARTELLA_DATI = RADICE / "data"
CARTELLA_SITO = RADICE / "site"
REGISTRO = CARTELLA_DATI / "registro.log"
RIGHE_REGISTRO = 3000  # il registro tiene solo le righe più recenti

log = logging.getLogger("giornalize")


def prepara_registro(verboso: bool) -> None:
    CARTELLA_DATI.mkdir(exist_ok=True)
    formato = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S")
    schermo = logging.StreamHandler()
    schermo.setFormatter(formato)
    schermo.setLevel(logging.DEBUG if verboso else logging.INFO)
    file = logging.FileHandler(REGISTRO, encoding="utf-8")
    file.setFormatter(formato)
    file.setLevel(logging.WARNING)  # nel file finiscono avvisi ed errori
    radice = logging.getLogger()
    radice.setLevel(logging.DEBUG)
    radice.addHandler(schermo)
    radice.addHandler(file)
    for rumoroso in ("urllib3", "charset_normalizer"):
        logging.getLogger(rumoroso).setLevel(logging.WARNING)


def accorcia_registro() -> None:
    try:
        righe = REGISTRO.read_text(encoding="utf-8").splitlines(keepends=True)
        if len(righe) > RIGHE_REGISTRO:
            REGISTRO.write_text("".join(righe[-RIGHE_REGISTRO:]), encoding="utf-8")
    except OSError:
        pass


def comando_raccogli(config) -> None:
    ora = archivio.ora_utc()
    nuove, stati = raccogli_tutto(config, ora)
    esistenti = archivio.leggi(CARTELLA_DATI / "notizie.json")
    tutte, aggiunte = archivio.unisci(esistenti, nuove, ora, config["raccolta"]["giorni_archivio"])
    archivio.scrivi(CARTELLA_DATI / "notizie.json", tutte, ora)
    archivio.scrivi_stato(CARTELLA_DATI / "stato_fonti.json", stati)

    funzionanti = sum(1 for s in stati.values() if s["canali_ok"])
    in_errore = [i for i, s in stati.items() if s["esito"] == "errore"]
    log.info(
        "Raccolta finita: %d fonti funzionanti su %d, %d notizie nuove, %d in archivio",
        funzionanti, len(stati), aggiunte, len(tutte),
    )
    if in_errore:
        log.warning("Fonti non raggiungibili in questo giro: %s", ", ".join(in_errore))
    if stati and not funzionanti:
        log.error("Nessuna fonte ha risposto: problema di rete? Il sito userà le notizie già raccolte.")


def comando_costruisci(config) -> None:
    Costruttore(config, CARTELLA_DATI, CARTELLA_SITO).costruisci(archivio.ora_utc())


def comando_prova_fonti(config, ids: list[str]) -> int:
    fonti = [f for f in config.fonti if not ids or f.id in ids]
    sconosciuti = set(ids) - {f.id for f in config.fonti}
    if sconosciuti:
        print(f"Fonti sconosciute: {', '.join(sorted(sconosciuti))}")
        return 1
    righe = ["| Fonte | Esito | Notizie | Dettagli |", "|---|---|---|---|"]
    simboli = {"ok": "✅ funziona", "parziale": "⚠️ in parte", "errore": "❌ non funziona",
               "nessun_canale": "➖ nessun feed"}
    for fonte in fonti:
        notizie, stato = raccogli_fonte(fonte, config)
        dettagli = []
        if stato["trovato_in_automatico"]:
            dettagli.append(f"trovato in automatico: {stato['trovato_in_automatico']} (copialo in sources.yaml)")
        dettagli += stato["errori"]
        senza_data = sum(1 for n in notizie if n["pubblicato"] == n["raccolto"])
        if senza_data:
            dettagli.append(f"{senza_data} notizie senza data leggibile: si usa l'ora della raccolta")
        if notizie:
            dettagli.append(f"esempio: «{notizie[0]['titolo'][:70]}»")
        righe.append(
            f"| {fonte.nome} | {simboli[stato['esito']]} | {len(notizie)} | {'<br>'.join(dettagli).replace('|', '/')} |"
        )
    rapporto = "## Rapporto sulle fonti\n\n" + "\n".join(righe) + "\n"
    print(rapporto)
    # Su GitHub il rapporto compare anche nella pagina dell'esecuzione.
    riepilogo = os.environ.get("GITHUB_STEP_SUMMARY")
    if riepilogo:
        with open(riepilogo, "a", encoding="utf-8") as f:
            f.write(rapporto)
    return 0


def comando_aggiungi_post(config) -> int:
    """Usato dal modulo "Aggiungi un post" su GitHub. Scrive l'esito nel file
    indicato da ESITO_MODULO, che GitHub pubblica come commento."""
    esito = Path(os.environ.get("ESITO_MODULO", CARTELLA_DATI / "esito_modulo.md"))
    try:
        notizia = instagram.aggiungi_da_modulo(os.environ.get("TESTO_MODULO", ""), config, archivio.ora_utc())
    except instagram.ErrorePost as e:
        esito.write_text(f"❌ Il post non è stato aggiunto: {e}.\n\nCorreggi il modulo (modifica "
                         "questa issue) e verrà controllato di nuovo.", encoding="utf-8")
        log.error("Post non aggiunto: %s", e)
        return 1
    fonte = config.fonti_per_id[notizia["fonte"]]
    esito.write_text(f"✅ Aggiunto: **{notizia['titolo']}** ({fonte.nome}).\n\nIl sito si aggiorna "
                     "tra un paio di minuti.", encoding="utf-8")
    log.info("Post aggiunto: %s (%s)", notizia["titolo"], fonte.id)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="giornalize", description="Comandi di Giornalize")
    parser.add_argument("comando", choices=["aggiorna", "raccogli", "costruisci", "prova-fonti", "aggiungi-post"])
    parser.add_argument("fonti", nargs="*", help="(solo per prova-fonti) id delle fonti da provare")
    parser.add_argument("-v", "--verboso", action="store_true", help="mostra più dettagli")
    argomenti = parser.parse_args(argv)

    prepara_registro(argomenti.verboso)
    try:
        config = carica()
    except ErroreConfigurazione as e:
        log.error("%s", e)
        return 2

    try:
        if argomenti.comando == "prova-fonti":
            return comando_prova_fonti(config, argomenti.fonti)
        if argomenti.comando == "aggiungi-post":
            return comando_aggiungi_post(config)
        if argomenti.comando in ("aggiorna", "raccogli"):
            comando_raccogli(config)
        if argomenti.comando in ("aggiorna", "costruisci"):
            comando_costruisci(config)
    finally:
        accorcia_registro()
    return 0


if __name__ == "__main__":
    sys.exit(main())

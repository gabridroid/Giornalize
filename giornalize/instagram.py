"""Raccolta da Instagram: un modulo separato, che si può sostituire senza
toccare il resto del programma.

Due modi, indipendenti tra loro:

1. **Post aggiunti a mano** nel file contenuti/post_instagram.yaml (anche
   tramite il modulo "Aggiungi un post" su GitHub). Funziona sempre.
2. **API ufficiale di Instagram** (funzione "Business Discovery"): legge gli
   ultimi post pubblici degli account professionali. Si attiva solo se su
   GitHub sono impostati i segreti INSTAGRAM_TOKEN e INSTAGRAM_ACCOUNT_ID,
   e solo per le fonti con `instagram_api: true` in sources.yaml.

Niente scraping: si usano solo il link al post e il testo della didascalia
(accorciato), mai le immagini.
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
import yaml

from .config import RADICE, Configurazione, Fonte
from .testo import pulisci_link, taglia

log = logging.getLogger("giornalize.instagram")

FILE_MANUALI = RADICE / "contenuti" / "post_instagram.yaml"
FUSO = ZoneInfo("Europe/Rome")

INTESTAZIONE_MANUALI = """\
# ============================================================================
#  POST AGGIUNTI A MANO
# ============================================================================
#  Qui si aggiungono i post (di Instagram o di qualsiasi altro sito) che il
#  programma non riesce a raccogliere da solo.
#
#  Il modo più comodo, anche dal telefono, è il modulo su GitHub:
#  scheda "Issues" -> "New issue" -> "Aggiungi un post". Il post viene
#  scritto qui in automatico.
#
#  Si può anche scrivere a mano, copiando questo esempio:
#
#  - fonte: factanza                  # id, nome o @account della fonte
#    link: https://www.instagram.com/p/CODICE/
#    titolo: Il titolo che vuoi mostrare
#    riassunto: Due righe scritte da te (al massimo 200 caratteri).
#    data: 2026-10-18 09:30           # giorno e ora (ora italiana)
#
#  Il post compare sul sito per le ore indicate in config.yaml (oggi:
#  finestra_ore), a partire dalla sua data.
# ============================================================================

"""


class ErrorePost(Exception):
    """Un post scritto male: il messaggio spiega cosa correggere."""


# --- Post aggiunti a mano ------------------------------------------------------


def trova_fonte(config: Configurazione, testo: str) -> Fonte:
    """Trova una fonte a partire dal suo id, dal nome o dall'account Instagram."""
    cercato = str(testo or "").strip().lower().lstrip("@")
    for f in config.fonti:
        if cercato in (f.id.lower(), f.nome.lower(), f.instagram.lower().lstrip("@")):
            return f
    raise ErrorePost(
        f"non trovo la fonte «{testo}». Scrivi l'id, il nome o l'account Instagram di una fonte "
        "presente in sources.yaml (se è nuova, aggiungila prima lì)"
    )


def leggi_data(testo) -> datetime:
    """'2026-10-18 09:30' o '2026-10-18' (ora italiana) -> data in UTC."""
    if isinstance(testo, datetime):
        momento = testo
    else:
        testo = str(testo or "").strip().replace("T", " ")
        for formato in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y %H:%M", "%d/%m/%Y"):
            try:
                momento = datetime.strptime(testo, formato)
                break
            except ValueError:
                continue
        else:
            raise ErrorePost(f"la data «{testo}» non è scritta bene: usa per esempio 2026-10-18 09:30")
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=FUSO)
    return momento.astimezone(timezone.utc)


def post_in_notizia(voce: dict, config: Configurazione) -> dict:
    """Controlla un post scritto a mano e lo trasforma in una notizia."""
    from .raccolta import id_notizia, iso  # import qui per evitare cicli

    if not isinstance(voce, dict):
        raise ErrorePost("ogni post deve iniziare con «- fonte:»")
    fonte = trova_fonte(config, voce.get("fonte"))
    link = pulisci_link(str(voce.get("link") or ""))
    if not link.startswith(("http://", "https://")):
        raise ErrorePost("manca il link al post, o non inizia con https://")
    titolo = str(voce.get("titolo") or "").strip()
    if not titolo:
        raise ErrorePost("manca il titolo")
    if not voce.get("data"):
        raise ErrorePost("manca la data del post")
    pubblicato = leggi_data(voce["data"])
    massimo = config["estratto"]["max_caratteri"]
    return {
        "id": id_notizia(link),
        "fonte": fonte.id,
        "titolo": taglia(titolo, 160),
        "estratto": taglia(str(voce.get("riassunto") or "").strip(), massimo),
        "link": link,
        "pubblicato": iso(pubblicato),
        "raccolto": iso(pubblicato),
        "canale": "manuale",
    }


def leggi_voci_manuali(percorso: Path | None = None) -> list:
    percorso = percorso or FILE_MANUALI
    if not percorso.exists():
        return []
    try:
        dati = yaml.safe_load(percorso.read_text(encoding="utf-8")) or []
    except yaml.YAMLError as e:
        log.error("%s contiene un errore di scrittura, i post a mano sono ignorati: %s", percorso.name, e)
        return []
    if isinstance(dati, dict):  # tollera "post:" come chiave principale
        dati = dati.get("post") or []
    return dati if isinstance(dati, list) else []


def leggi_post_manuali(config: Configurazione, percorso: Path | None = None) -> list[dict]:
    """Legge i post aggiunti a mano. I post scritti male vengono saltati e
    segnalati nel registro, senza fermare l'aggiornamento."""
    percorso = percorso or FILE_MANUALI
    notizie = []
    for i, voce in enumerate(leggi_voci_manuali(percorso), start=1):
        try:
            notizie.append(post_in_notizia(voce, config))
        except ErrorePost as e:
            log.warning("%s, post n. %d: %s", percorso.name, i, e)
    return notizie


def scrivi_voci_manuali(voci: list, percorso: Path | None = None) -> None:
    percorso = percorso or FILE_MANUALI
    corpo = yaml.safe_dump(voci, allow_unicode=True, sort_keys=False, width=1000) if voci else "[]\n"
    percorso.parent.mkdir(parents=True, exist_ok=True)
    percorso.write_text(INTESTAZIONE_MANUALI + corpo, encoding="utf-8")


# --- Modulo "Aggiungi un post" (issue di GitHub) -------------------------------

# Etichette dei campi nel modulo .github/ISSUE_TEMPLATE/aggiungi-post.yml
CAMPI_MODULO = {
    "Link al post": "link",
    "Fonte": "fonte",
    "Titolo": "titolo",
    "Riassunto": "riassunto",
    "Data e ora del post": "data",
}


def leggi_modulo(testo: str) -> dict:
    """Legge il testo di una issue creata con il modulo di GitHub, fatto di
    blocchi '### Etichetta' seguiti dal valore."""
    voce: dict[str, str] = {}
    for blocco in re.split(r"^###\s+", testo or "", flags=re.M)[1:]:
        etichetta, _, valore = blocco.partition("\n")
        chiave = CAMPI_MODULO.get(etichetta.strip())
        valore = valore.strip()
        if chiave and valore and valore != "_No response_":
            voce[chiave] = valore
    return voce


def aggiungi_da_modulo(testo: str, config: Configurazione, ora: datetime, percorso: Path | None = None) -> dict:
    """Controlla il modulo e aggiunge il post al file. Restituisce la notizia.
    Solleva ErrorePost con un messaggio in italiano se qualcosa non va."""
    percorso = percorso or FILE_MANUALI
    voce = leggi_modulo(testo)
    if not voce.get("data"):
        voce["data"] = ora.astimezone(FUSO).strftime("%Y-%m-%d %H:%M")
    if voce.get("fonte"):
        voce["fonte"] = trova_fonte(config, voce["fonte"]).id
    notizia = post_in_notizia(voce, config)
    voci = leggi_voci_manuali(percorso)
    from .testo import chiave_link
    if any(chiave_link(str(v.get("link", ""))) == chiave_link(notizia["link"]) for v in voci if isinstance(v, dict)):
        raise ErrorePost("questo link è già stato aggiunto")
    voci.append({k: voce[k] for k in ("fonte", "link", "titolo", "riassunto", "data") if voce.get(k)})
    scrivi_voci_manuali(voci, percorso)
    return notizia


# --- API ufficiale (Business Discovery) ------------------------------------------


def api_configurata() -> bool:
    return bool(os.environ.get("INSTAGRAM_TOKEN") and os.environ.get("INSTAGRAM_ACCOUNT_ID"))


_HASHTAG = re.compile(r"(^|\s)[#@][\w.]+")


def _pulisci_didascalia(didascalia: str) -> str:
    testo = _HASHTAG.sub(" ", didascalia or "")
    return re.sub(r"\s+", " ", testo).strip()


def titolo_da_didascalia(didascalia: str) -> tuple[str, str]:
    """Divide la didascalia in (titolo, resto): il titolo è la prima riga o
    la prima frase."""
    righe = [r.strip() for r in (didascalia or "").splitlines() if _pulisci_didascalia(r)]
    if not righe:
        return "", ""
    prima = _pulisci_didascalia(righe[0])
    resto = _pulisci_didascalia(" ".join(righe[1:]))
    if len(prima) > 160:
        frase = re.match(r"(.{30,160}?[.!?])\s", prima + " ")
        if frase:
            resto = (prima[frase.end():] + " " + resto).strip()
            prima = frase.group(1)
    return taglia(prima, 160), resto


def leggi_api(fonte: Fonte, config: Configurazione, ora: datetime) -> list[dict]:
    """Ultimi post pubblici di un account professionale tramite Business
    Discovery. Solleva un'eccezione con un messaggio chiaro in caso di errore."""
    from .raccolta import id_notizia, iso

    impostazioni = config.impostazioni.get("instagram", {})
    versione = impostazioni.get("versione_api", "v24.0")
    quanti = int(impostazioni.get("post_per_account", 10))
    account = fonte.instagram.strip().lstrip("@")
    campi = (
        f"business_discovery.username({account})"
        f"{{username,media.limit({quanti}){{caption,permalink,timestamp,media_type}}}}"
    )
    risposta = requests.get(
        f"https://graph.facebook.com/{versione}/{os.environ['INSTAGRAM_ACCOUNT_ID']}",
        params={"fields": campi, "access_token": os.environ["INSTAGRAM_TOKEN"]},
        timeout=config["raccolta"]["timeout_secondi"],
    )
    dati = risposta.json() if risposta.content else {}
    if "error" in dati:
        raise ValueError(f"Instagram API: {dati['error'].get('message', 'errore sconosciuto')}")
    risposta.raise_for_status()

    notizie = []
    massimo = config["estratto"]["max_caratteri"]
    for post in dati.get("business_discovery", {}).get("media", {}).get("data", []):
        titolo, resto = titolo_da_didascalia(post.get("caption", ""))
        link = pulisci_link(post.get("permalink", ""))
        if not titolo or not link:
            continue
        try:
            pubblicato = datetime.strptime(post["timestamp"], "%Y-%m-%dT%H:%M:%S%z").astimezone(timezone.utc)
        except (KeyError, ValueError):
            pubblicato = ora
        notizie.append({
            "id": id_notizia(link),
            "fonte": fonte.id,
            "titolo": titolo,
            "estratto": taglia(resto, massimo) if fonte.mostra_estratto else "",
            "link": link,
            "pubblicato": iso(min(pubblicato, ora)),
            "raccolto": iso(ora),
            "canale": "instagram",
        })
    return notizie

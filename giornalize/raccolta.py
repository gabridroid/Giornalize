"""Raccolta delle notizie dai feed RSS/Atom e dalle news sitemap.

Ogni fonte viene letta in modo indipendente: se una fonte non risponde o
cambia formato, l'errore viene registrato e le altre fonti proseguono.
"""

from __future__ import annotations

import calendar
import gzip
import hashlib
import logging
import re
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import urljoin

import feedparser
import requests

from .config import Configurazione, Fonte
from .testo import chiave_link, prepara_estratto, pulisci_link, pulisci_titolo

log = logging.getLogger("giornalize.raccolta")

USER_AGENT = "Mozilla/5.0 (compatible; GiornalizeBot/1.0; lettore di feed RSS)"

# Percorsi dove spesso si trova il feed di un sito, provati se non ne
# troviamo uno indicato nella pagina principale.
PERCORSI_FEED_COMUNI = ["/feed/", "/rss", "/rss.xml", "/feed.xml", "/feed", "/rss/", "/index.xml"]


def adesso() -> datetime:
    return datetime.now(timezone.utc)


def iso(momento: datetime) -> str:
    return momento.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def id_notizia(link: str) -> str:
    return hashlib.sha1(chiave_link(link).encode("utf-8")).hexdigest()[:16]


def scarica(url: str, timeout: float) -> bytes:
    risposta = requests.get(
        url,
        timeout=timeout,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
        },
    )
    risposta.raise_for_status()
    contenuto = risposta.content
    if contenuto[:2] == b"\x1f\x8b":  # file .gz
        contenuto = gzip.decompress(contenuto)
    return contenuto


def _crea_notizia(
    fonte: Fonte, titolo: str, link: str, sommario: str, pubblicato: datetime | None,
    canale: str, config: Configurazione, ora: datetime,
) -> dict | None:
    titolo = pulisci_titolo(titolo, fonte.nome)
    link = pulisci_link(link)
    if not titolo or not link.startswith(("http://", "https://")) or fonte.esclusa(link):
        return None
    # Date mancanti o "nel futuro" (fusi orari sbagliati nel feed): si usa
    # il momento in cui la notizia è stata raccolta.
    if pubblicato is None or pubblicato > ora + timedelta(hours=1):
        pubblicato = ora
    return {
        "id": id_notizia(link),
        "fonte": fonte.id,
        "titolo": titolo,
        "estratto": (
            prepara_estratto(sommario, titolo, config["estratto"]["max_caratteri"])
            if fonte.mostra_estratto else ""
        ),
        "link": link,
        "pubblicato": iso(pubblicato),
        "raccolto": iso(ora),
        "canale": canale,
    }


def _data_da_struct(voce, *chiavi) -> datetime | None:
    for chiave in chiavi:
        valore = voce.get(chiave)
        if valore:
            try:
                return datetime.fromtimestamp(calendar.timegm(valore), tz=timezone.utc)
            except (TypeError, ValueError, OverflowError):
                continue
    return None


# Abbreviazioni italiane di giorni e mesi -> inglesi, per le date scritte
# in italiano (es. "Sab, 17 Ott 2026 21:30:00 +0200").
_ITALIANO_INGLESE = {
    "lun": "Mon", "mar": "Tue", "mer": "Wed", "gio": "Thu", "ven": "Fri", "sab": "Sat", "dom": "Sun",
    "gen": "Jan", "feb": "Feb", "apr": "Apr", "mag": "May", "giu": "Jun",
    "lug": "Jul", "ago": "Aug", "set": "Sep", "ott": "Oct", "nov": "Nov", "dic": "Dec",
}


def data_da_testo(testo: str) -> datetime | None:
    """Interpreta una data scritta come testo quando feedparser non ci riesce."""
    testo = (testo or "").strip()
    if not testo:
        return None
    momento = _data_iso(testo)
    if momento:
        return momento
    # "mar" è sia martedì sia marzo: in posizione di mese diventa "Mar".
    parole = re.split(r"(\W+)", testo)
    tradotto = []
    for i, p in enumerate(parole):
        chiave = p[:3].lower()
        if chiave == "mar" and i > 0 and any(c.isdigit() for c in "".join(parole[max(0, i - 2):i])):
            tradotto.append("Mar")
        elif chiave in _ITALIANO_INGLESE and p.isalpha():
            tradotto.append(_ITALIANO_INGLESE[chiave])
        else:
            tradotto.append(p)
    try:
        momento = parsedate_to_datetime("".join(tradotto))
    except (TypeError, ValueError, IndexError):
        return None
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=timezone.utc)
    return momento.astimezone(timezone.utc)


def leggi_feed(fonte: Fonte, contenuto: bytes, config: Configurazione, ora: datetime) -> list[dict]:
    """Interpreta un feed RSS o Atom. Solleva ValueError se non è un feed."""
    analisi = feedparser.parse(contenuto)
    voci = analisi.entries
    if not voci:
        if not analisi.get("version"):
            if analisi.get("bozo"):
                raise ValueError(f"non è un feed leggibile ({analisi.get('bozo_exception')})")
            raise ValueError("non è un feed RSS/Atom (forse una pagina web)")
        return []  # feed valido ma vuoto
    notizie = []
    for voce in voci[: config["raccolta"]["max_notizie_per_feed"]]:
        sommario = voce.get("summary") or voce.get("description") or ""
        if not sommario and voce.get("media_description"):
            sommario = voce["media_description"]
        notizia = _crea_notizia(
            fonte,
            voce.get("title", ""),
            voce.get("link", ""),
            sommario,
            _data_da_struct(voce, "published_parsed", "updated_parsed", "created_parsed")
            or next(filter(None, (data_da_testo(voce.get(k, "")) for k in ("published", "updated", "date"))), None),
            "rss",
            config,
            ora,
        )
        if notizia:
            notizie.append(notizia)
    return notizie


def _nome_locale(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _data_iso(testo: str) -> datetime | None:
    testo = (testo or "").strip()
    if not testo:
        return None
    testo = testo.replace("Z", "+00:00")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", testo):
        testo += "T00:00:00+00:00"
    try:
        momento = datetime.fromisoformat(testo)
    except ValueError:
        return None
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=timezone.utc)
    return momento.astimezone(timezone.utc)


def leggi_sitemap(
    fonte: Fonte, contenuto: bytes, config: Configurazione, ora: datetime, timeout: float,
    profondita: int = 0,
) -> list[dict]:
    """Interpreta una "news sitemap" di Google News (titolo, data, link).
    Se è un indice di sitemap, legge al massimo 3 sitemap "news" collegate."""
    try:
        radice = ET.fromstring(contenuto)
    except ET.ParseError as e:
        raise ValueError(f"sitemap non leggibile ({e})")
    tipo = _nome_locale(radice.tag)
    if tipo == "sitemapindex":
        if profondita > 0:
            return []
        indirizzi = [
            el.text.strip()
            for el in radice.iter()
            if _nome_locale(el.tag) == "loc" and el.text
        ]
        news = [u for u in indirizzi if "news" in u.lower()] or indirizzi[:1]
        notizie: list[dict] = []
        for url in news[:3]:
            notizie += leggi_sitemap(
                fonte, scarica(url, timeout), config, ora, timeout, profondita + 1
            )
        return notizie
    if tipo != "urlset":
        raise ValueError("non è una sitemap")
    limite = ora - timedelta(days=config["raccolta"]["giorni_archivio"])
    notizie = []
    for url_el in radice:
        if _nome_locale(url_el.tag) != "url":
            continue
        campi = {}
        for el in url_el.iter():
            nome = _nome_locale(el.tag)
            if el.text and nome not in campi:
                campi[nome] = el.text.strip()
        if "title" not in campi:  # non è una news sitemap
            continue
        pubblicato = _data_iso(campi.get("publication_date", ""))
        if pubblicato and pubblicato < limite:
            continue
        notizia = _crea_notizia(
            fonte, campi["title"], campi.get("loc", ""), "", pubblicato, "sitemap", config, ora
        )
        if notizia:
            notizie.append(notizia)
    notizie.sort(key=lambda n: n["pubblicato"], reverse=True)
    return notizie[: config["raccolta"]["max_notizie_per_feed"]]


class _CercaLinkFeed(HTMLParser):
    def __init__(self):
        super().__init__()
        self.trovati: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag != "link":
            return
        a = dict(attrs)
        tipo = (a.get("type") or "").lower()
        if "alternate" in (a.get("rel") or "").lower() and ("rss" in tipo or "atom" in tipo):
            if a.get("href"):
                self.trovati.append(a["href"])


def scopri_feed(sito: str, fonte: Fonte, config: Configurazione, ora: datetime) -> tuple[str, str, list[dict]]:
    """Prova a trovare da solo un feed partendo dalla pagina principale del
    sito. Restituisce (tipo, indirizzo, notizie). Solleva ValueError se non
    trova niente."""
    timeout = config["raccolta"]["timeout_secondi"]
    candidati: list[tuple[str, str]] = []
    try:
        pagina = scarica(sito, timeout).decode("utf-8", errors="replace")
        lettore = _CercaLinkFeed()
        lettore.feed(pagina)
        candidati += [("rss", urljoin(sito, h)) for h in lettore.trovati]
    except (requests.ConnectionError, requests.Timeout):
        # Sito irraggiungibile: inutile provare altri indirizzi dello stesso sito.
        raise ValueError("sito irraggiungibile")
    except Exception as e:
        log.debug("%s: pagina principale non leggibile (%s)", fonte.id, e)
    candidati += [("rss", urljoin(sito, p)) for p in PERCORSI_FEED_COMUNI]
    try:
        robots = scarica(urljoin(sito, "/robots.txt"), timeout).decode("utf-8", errors="replace")
        for riga in robots.splitlines():
            if riga.lower().startswith("sitemap:") and "news" in riga.lower():
                candidati.append(("sitemap", riga.split(":", 1)[1].strip()))
    except Exception:
        pass

    visti = set()
    for tipo, url in candidati:
        if url in visti:
            continue
        visti.add(url)
        try:
            contenuto = scarica(url, timeout)
            if tipo == "rss":
                notizie = leggi_feed(fonte, contenuto, config, ora)
            else:
                notizie = leggi_sitemap(fonte, contenuto, config, ora, timeout)
        except Exception:
            continue
        if notizie:
            return tipo, url, notizie
    raise ValueError("nessun feed trovato in automatico")


def raccogli_fonte(fonte: Fonte, config: Configurazione, ora: datetime | None = None) -> tuple[list[dict], dict]:
    """Legge tutti i canali di una fonte. Non solleva mai eccezioni:
    gli errori finiscono nello "stato" restituito."""
    ora = ora or adesso()
    timeout = config["raccolta"]["timeout_secondi"]
    stato = {
        "fonte": fonte.id,
        "ora": iso(ora),
        "esito": "ok",
        "notizie": 0,
        "canali_ok": [],
        "errori": [],
        "trovato_in_automatico": None,
    }
    notizie: list[dict] = []
    canali = [("rss", u) for u in fonte.feed] + [("sitemap", u) for u in fonte.sitemap]

    for tipo, url in canali:
        try:
            contenuto = scarica(url, timeout)
            if tipo == "rss":
                trovate = leggi_feed(fonte, contenuto, config, ora)
            else:
                trovate = leggi_sitemap(fonte, contenuto, config, ora, timeout)
            notizie += trovate
            stato["canali_ok"].append(url)
            log.info("%s: %d notizie da %s", fonte.id, len(trovate), url)
        except Exception as e:
            messaggio = f"{url}: {_descrivi_errore(e)}"
            stato["errori"].append(messaggio)
            log.warning("%s: errore con %s", fonte.id, messaggio)

    if not stato["canali_ok"] and fonte.sito and config["raccolta"].get("scoperta_automatica", True):
        try:
            tipo, url, trovate = scopri_feed(fonte.sito, fonte, config, ora)
            notizie += trovate
            stato["canali_ok"].append(url)
            stato["trovato_in_automatico"] = url
            log.warning(
                "%s: trovato in automatico il %s %s (conviene scriverlo in sources.yaml)",
                fonte.id, "feed" if tipo == "rss" else "sitemap", url,
            )
        except Exception as e:
            stato["errori"].append(f"ricerca automatica: {_descrivi_errore(e)}")
            log.info("%s: ricerca automatica del feed non riuscita (%s)", fonte.id, e)

    if not canali and not stato["canali_ok"]:
        stato["esito"] = "nessun_canale"
    elif not stato["canali_ok"]:
        stato["esito"] = "errore"
    elif stato["errori"]:
        stato["esito"] = "parziale"
    stato["notizie"] = len(notizie)
    return notizie, stato


def _descrivi_errore(e: Exception) -> str:
    if isinstance(e, requests.Timeout):
        return "non risponde (tempo scaduto)"
    if isinstance(e, requests.ConnectionError):
        return "irraggiungibile"
    if isinstance(e, requests.HTTPError) and e.response is not None:
        return f"errore HTTP {e.response.status_code}"
    return str(e) or e.__class__.__name__


def raccogli_tutto(config: Configurazione, ora: datetime | None = None) -> tuple[list[dict], dict[str, dict]]:
    ora = ora or adesso()
    fonti = [f for f in config.fonti if f.attiva]
    notizie: list[dict] = []
    stati: dict[str, dict] = {}

    def raccogli_al_sicuro(fonte: Fonte) -> tuple[list[dict], dict]:
        try:
            return raccogli_fonte(fonte, config, ora)
        except Exception as e:  # rete di sicurezza: un errore imprevisto non ferma le altre fonti
            log.exception("%s: errore imprevisto", fonte.id)
            return [], {"fonte": fonte.id, "ora": iso(ora), "esito": "errore", "notizie": 0,
                        "canali_ok": [], "errori": [f"errore imprevisto: {e}"],
                        "trovato_in_automatico": None}

    with ThreadPoolExecutor(max_workers=8) as esecutore:
        for fonte, (trovate, stato) in zip(fonti, esecutore.map(raccogli_al_sicuro, fonti)):
            notizie += trovate
            stati[fonte.id] = stato
    return notizie, stati

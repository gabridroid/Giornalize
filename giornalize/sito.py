"""Costruzione del sito statico (cartella site/) a partire dai dati raccolti."""

from __future__ import annotations

import logging
import re
import shutil
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import markdown
from jinja2 import Environment, FileSystemLoader, select_autoescape

from .archivio import data, leggi, leggi_stato
from .config import RADICE, Configurazione
from .raggruppa import Gruppo, raggruppa

log = logging.getLogger("giornalize.sito")

FUSO = ZoneInfo("Europe/Rome")
MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
        "agosto", "settembre", "ottobre", "novembre", "dicembre"]


def data_breve(iso: str) -> str:
    """'2026-10-17T19:30:00Z' -> '17 ott, 21:30' (ora italiana)."""
    m = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(FUSO)
    return f"{m.day} {MESI[m.month - 1][:3]}, {m:%H:%M}"


def data_lunga(momento: datetime) -> str:
    m = momento.astimezone(FUSO)
    return f"{m.day} {MESI[m.month - 1]} {m.year} alle {m:%H:%M}"


def _plurale(n: int, singolare: str, plurale: str) -> str:
    return f"{n} {singolare if n == 1 else plurale}"


class Costruttore:
    def __init__(self, config: Configurazione, cartella_dati: Path, cartella_sito: Path):
        self.config = config
        self.cartella_dati = cartella_dati
        self.cartella_sito = cartella_sito
        self.ordine_categorie = {c.nome: i for i, c in enumerate(config.categorie)}
        self.env = Environment(
            loader=FileSystemLoader(RADICE / "templates"),
            autoescape=select_autoescape(["html"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self.env.filters["data_breve"] = data_breve
        self.env.filters["iniziale_maiuscola"] = lambda t: t[:1].upper() + t[1:]

    # -- dati per le pagine ------------------------------------------------

    def riepilogo(self, gruppo: Gruppo) -> str:
        """Es. '5 fonti · 2 quotidiani · 2 testate online · 1 inchiesta/fact-checking'."""
        per_categoria = Counter(self.config.fonti_per_id[f].categoria for f in gruppo.fonti)
        pezzi = [_plurale(len(gruppo.fonti), "fonte", "fonti")]
        for cat in self.config.categorie:
            if per_categoria[cat.nome]:
                pezzi.append(_plurale(per_categoria[cat.nome], cat.singolare, cat.plurale))
        return " · ".join(pezzi)

    def conta(self, gruppo: Gruppo, categorie: list[str]) -> int:
        return sum(1 for f in gruppo.fonti if self.config.fonti_per_id[f].categoria in categorie)

    def ordina_notizie(self, notizie: list[dict]) -> list[dict]:
        """Nelle card di un gruppo: prima per categoria (agenzie, quotidiani, ...),
        poi per fonte, poi dalla più recente."""
        def chiave(n):
            fonte = self.config.fonti_per_id[n["fonte"]]
            return (self.ordine_categorie.get(fonte.categoria, 99), fonte.nome.lower(), n["pubblicato"])
        ordinate = sorted(notizie, key=lambda n: n["pubblicato"], reverse=True)
        return sorted(ordinate, key=lambda n: chiave(n)[:2])

    def prepara(self, ora: datetime) -> dict:
        cfg = self.config
        notizie = [
            n for n in leggi(self.cartella_dati / "notizie.json")
            if n["fonte"] in cfg.fonti_per_id and cfg.fonti_per_id[n["fonte"]].attiva
        ]
        inizio = ora - timedelta(hours=cfg["oggi"]["finestra_ore"])
        recenti = [n for n in notizie if data(n) >= inizio]

        r = cfg["raggruppamento"]
        gruppi = raggruppa(recenti, r["soglia_somiglianza"], r["peso_titolo"], r["parole_chiave"])

        minimo = cfg["oggi"]["min_fonti_per_gruppo"]
        multipli = [g for g in gruppi if len(g.fonti) >= minimo]
        multipli.sort(key=lambda g: (len(g.fonti), g.ultimo), reverse=True)
        singole = sorted(
            (n for g in gruppi if len(g.fonti) < minimo for n in g.notizie),
            key=lambda n: n["pubblicato"], reverse=True,
        )[: cfg["oggi"]["max_notizie_singole"]]

        pc = cfg["poco_coperte"]
        poco_coperte = [
            g for g in gruppi
            if self.conta(g, pc["categorie_alternative"]) >= pc["min_fonti_alternative"]
            and self.conta(g, pc["categorie_grandi"]) <= pc["max_fonti_grandi"]
        ]
        poco_coperte.sort(key=lambda g: (self.conta(g, pc["categorie_alternative"]), g.ultimo), reverse=True)

        return {
            "notizie": notizie,
            "recenti": recenti,
            "gruppi": multipli,
            "singole": singole,
            "poco_coperte": poco_coperte,
            "stato": leggi_stato(self.cartella_dati / "stato_fonti.json"),
        }

    # -- scrittura -----------------------------------------------------------

    def costruisci(self, ora: datetime) -> dict:
        cfg = self.config
        dati = self.prepara(ora)

        if self.cartella_sito.exists():
            shutil.rmtree(self.cartella_sito)
        self.cartella_sito.mkdir(parents=True)
        shutil.copytree(RADICE / "static", self.cartella_sito / "static")

        orientamenti = sorted({f.badge for f in cfg.fonti if f.badge}, key=str.lower)
        fonti_attive = [f for f in cfg.fonti if f.attiva]
        notizie_per_fonte = Counter(n["fonte"] for n in dati["recenti"])
        comuni = {
            "sito": cfg["sito"],
            "cfg": cfg.impostazioni,
            "categorie": cfg.categorie,
            "colori": {c.nome: c.colore for c in cfg.categorie},
            "fonti": cfg.fonti_per_id,
            "fonti_attive": sorted(fonti_attive, key=lambda f: f.nome.lower()),
            "orientamenti": orientamenti,
            "aggiornato": data_lunga(ora),
            "aggiornato_iso": ora.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "riepilogo": self.riepilogo,
            "ordina": self.ordina_notizie,
        }

        pagine = {
            "index.html": ("oggi.html", {"pagina": "oggi", "gruppi": dati["gruppi"], "singole": dati["singole"],
                                          "totale_recenti": len(dati["recenti"])}),
            "poco-coperte.html": ("poco_coperte.html", {"pagina": "poco", "gruppi": dati["poco_coperte"]}),
            "fonti.html": ("fonti.html", {"pagina": "fonti", "stato": dati["stato"],
                                          "notizie_per_fonte": notizie_per_fonte}),
            "come-funziona.html": ("come_funziona.html", {"pagina": "come"}),
            "perche.html": ("perche.html", {"pagina": "perche", "testo": self._testo_perche()}),
            "404.html": ("404.html", {"pagina": "404"}),
        }
        for nome_file, (modello, contesto) in pagine.items():
            html = self.env.get_template(modello).render(**comuni, **contesto)
            (self.cartella_sito / nome_file).write_text(html, encoding="utf-8")

        riassunto = {
            "notizie_archivio": len(dati["notizie"]),
            "notizie_finestra": len(dati["recenti"]),
            "gruppi": len(dati["gruppi"]),
            "poco_coperte": len(dati["poco_coperte"]),
            "singole": len(dati["singole"]),
        }
        log.info("Sito costruito in %s: %s", self.cartella_sito, riassunto)
        return riassunto

    def _testo_perche(self) -> str:
        percorso = RADICE / "contenuti" / "perche-esiste.md"
        testo = percorso.read_text(encoding="utf-8") if percorso.exists() else ""
        testo = re.sub(r"<!--.*?-->", "", testo, flags=re.S)  # i commenti restano privati
        html = markdown.markdown(testo, extensions=["extra", "sane_lists"])
        # I segnaposto [SEGNAPOSTO: ...] vengono evidenziati, così si vede
        # subito cosa manca da scrivere.
        return re.sub(r"\[SEGNAPOSTO:\s*(.*?)\]", r'<mark class="segnaposto">\1</mark>', html, flags=re.S)

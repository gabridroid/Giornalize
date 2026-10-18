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

from . import instagram
from .archivio import data, leggi, leggi_stato
from .config import RADICE, Configurazione
from .raggruppa import Gruppo, raggruppa, somiglianza_gruppi
from .testo import chiave_link, solo_data

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

    def per_fonte(self, notizie: list[dict]) -> list[tuple[dict, list[dict]]]:
        """Una card per fonte: restituisce (notizia più recente, altre notizie
        della stessa fonte), in ordine di categoria (agenzie, quotidiani, ...)
        e poi di nome della fonte."""
        gruppi: dict[str, list[dict]] = {}
        for n in sorted(notizie, key=lambda n: n["pubblicato"], reverse=True):
            gruppi.setdefault(n["fonte"], []).append(n)

        def chiave(id_fonte):
            fonte = self.config.fonti_per_id[id_fonte]
            return (self.ordine_categorie.get(fonte.categoria, 99), fonte.nome.lower())

        return [(gruppi[f][0], gruppi[f][1:]) for f in sorted(gruppi, key=chiave)]

    def prepara(self, ora: datetime) -> dict:
        cfg = self.config
        # Notizie raccolte in automatico + post aggiunti a mano (senza doppioni).
        archivio = leggi(self.cartella_dati / "notizie.json")
        link_noti = {chiave_link(n["link"]) for n in archivio}
        manuali = [n for n in instagram.leggi_post_manuali(cfg) if chiave_link(n["link"]) not in link_noti]
        notizie = [
            n for n in archivio + manuali
            if n["fonte"] in cfg.fonti_per_id
            and cfg.fonti_per_id[n["fonte"]].attiva
            and not cfg.fonti_per_id[n["fonte"]].esclusa(n["link"])
            and not solo_data(n["titolo"])
        ]
        inizio = ora - timedelta(hours=cfg["oggi"]["finestra_ore"])
        recenti = [n for n in notizie if inizio <= data(n) <= ora + timedelta(hours=1)]

        r = cfg["raggruppamento"]
        gruppi = raggruppa(recenti, r["soglia_somiglianza"], r["peso_titolo"], r["parole_chiave"])

        minimo = cfg["oggi"]["min_fonti_per_gruppo"]
        multipli = [g for g in gruppi if len(g.fonti) >= minimo]
        multipli.sort(key=lambda g: (len(g.fonti), g.ultimo), reverse=True)
        # Notizie di una sola fonte: le più recenti di ogni fonte, così
        # filtrando per fonte si trova sempre qualcosa.
        massimo = cfg["oggi"]["max_notizie_singole_per_fonte"]
        conteggio: Counter = Counter()
        singole = []
        for n in sorted(
            (n for g in gruppi if len(g.fonti) < minimo for n in g.notizie),
            key=lambda n: n["pubblicato"], reverse=True,
        ):
            if conteggio[n["fonte"]] < massimo:
                conteggio[n["fonte"]] += 1
                singole.append(n)

        poco_piu_fonti, poco_una_fonte = self.poco_coperte(gruppi)

        return {
            "notizie": notizie,
            "recenti": recenti,
            "gruppi": multipli,
            "singole": singole,
            "poco_coperte": poco_piu_fonti + poco_una_fonte,
            "poco_piu_fonti": poco_piu_fonti,
            "poco_una_fonte": poco_una_fonte,
            "stato": leggi_stato(self.cartella_dati / "stato_fonti.json"),
        }

    def poco_coperte(self, gruppi: list[Gruppo]) -> tuple[list[Gruppo], list[Gruppo]]:
        """Sezione "Quello che i grandi giornali non raccontano".
        Restituisce due elenchi: argomenti raccontati da più fonti
        alternative, e argomenti segnalati da una sola fonte alternativa."""
        pc = self.config["poco_coperte"]
        alternative = lambda g: self.conta(g, pc["categorie_alternative"])  # noqa: E731
        coperti = [g for g in gruppi if self.conta(g, pc["categorie_grandi"]) > pc["max_fonti_grandi"]]
        limite = pc.get("somiglianza_con_argomenti_coperti", 0)
        scelti = [
            g for g in gruppi
            if alternative(g) >= pc["min_fonti_alternative"]
            and self.conta(g, pc["categorie_grandi"]) <= pc["max_fonti_grandi"]
            # Scarta i "pezzi" di argomenti che i grandi giornali hanno coperto
            # ma che il raggruppamento ha separato (es. un dettaglio di una
            # storia molto raccontata).
            and not (limite and any(somiglianza_gruppi(g, c) >= limite for c in coperti))
        ]
        piu_fonti = sorted((g for g in scelti if alternative(g) >= 2),
                           key=lambda g: (alternative(g), g.ultimo), reverse=True)

        # Argomenti di una sola fonte alternativa: al massimo N per fonte, così
        # nessuna fonte (magari molto prolifica) riempie da sola la sezione.
        massimo = pc.get("max_argomenti_per_fonte", 4)
        priorita = {c: i for i, c in enumerate(pc.get("priorita_categorie", []))}

        def fonte_alternativa(g):
            return next(f for f in g.fonti if self.config.fonti_per_id[f].categoria in pc["categorie_alternative"])

        per_fonte: Counter = Counter()
        una_fonte = []
        for g in sorted((g for g in scelti if alternative(g) < 2), key=lambda g: g.ultimo, reverse=True):
            fonte = fonte_alternativa(g)
            if per_fonte[fonte] < massimo:
                per_fonte[fonte] += 1
                una_fonte.append(g)
        una_fonte.sort(key=lambda g: priorita.get(self.config.fonti_per_id[fonte_alternativa(g)].categoria, 99))
        return piu_fonti, una_fonte

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
            "per_fonte": self.per_fonte,
        }

        pagine = {
            "index.html": ("oggi.html", {"pagina": "oggi", "gruppi": dati["gruppi"], "singole": dati["singole"],
                                          "totale_recenti": len(dati["recenti"])}),
            "poco-coperte.html": ("poco_coperte.html", {"pagina": "poco", "piu_fonti": dati["poco_piu_fonti"],
                                                        "una_fonte": dati["poco_una_fonte"]}),
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
            "post_manuali": sum(1 for n in dati["recenti"] if n.get("canale") == "manuale"),
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

"""Costruzione del sito statico (cartella site/) a partire dai dati raccolti."""

from __future__ import annotations

import logging
import re
import shutil
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote_plus, urlsplit
from zoneinfo import ZoneInfo

import markdown
from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import instagram
from .archivio import data, leggi, leggi_stato
from .config import RADICE, Configurazione
from .raggruppa import Gruppo, raggruppa, raggruppa_storie, somiglianza_gruppi
from .testo import chiave_link, maiuscole_in_minuscole, solo_data

log = logging.getLogger("giornalize.sito")

FUSO = ZoneInfo("Europe/Rome")
MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
        "agosto", "settembre", "ottobre", "novembre", "dicembre"]
NON_COLLOCABILE = "non collocabile"

# Etichette da togliere dai titoli usati come titolo di una storia.
_ETICHETTE_TITOLO = re.compile(
    r"^\s*(video|foto|live|diretta|ultim'ora|ultima ora|esclusiva)\s*[|:–-]\s*"
    r"|\s*(?:[|–-]\s*((guarda )?(il |le )?(video|foto)|live|diretta)|\(\s*(video|foto|live|diretta)\s*\))\s*$",
    re.IGNORECASE,
)
# Etichette in maiuscolo in fondo al titolo, anche senza trattino ("... LIVE").
_ETICHETTE_MAIUSCOLE = re.compile(r"\s+(LIVE|VIDEO|FOTO|DIRETTA|HIGHLIGHTS)\s*$")
# Titoli poco adatti a fare da titolo di una storia (dirette, riepiloghi).
_TITOLO_GENERICO = re.compile(r"\b(live|diretta|news di oggi|le notizie di oggi)\b", re.IGNORECASE)


def data_breve(iso: str) -> str:
    """'2026-10-17T19:30:00Z' -> '17 ott, 21:30' (ora italiana)."""
    m = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(FUSO)
    return f"{m.day} {MESI[m.month - 1][:3]}, {m:%H:%M}"


def data_lunga(momento: datetime) -> str:
    m = momento.astimezone(FUSO)
    return f"{m.day} {MESI[m.month - 1]} {m.year} alle {m:%H:%M}"


def titolo_pulito(titolo: str) -> str:
    """Titolo adatto a fare da titolo di una storia: senza etichette tipo
    "VIDEO" o "LIVE" e senza parole tutte in maiuscolo."""
    t = _ETICHETTE_TITOLO.sub("", _ETICHETTE_MAIUSCOLE.sub("", titolo)).strip(" -–|:")
    return maiuscole_in_minuscole(t) or titolo


@dataclass
class Storia:
    """Una storia pronta per le pagine: il gruppo di notizie più tutto ciò
    che serve per mostrarla (titolo, copertura per area, titoli a confronto)."""
    gruppo: Gruppo
    titolo: str
    fonte_titolo: str
    copertura: list[tuple[object, int]]
    confronto: list[dict]
    tutte: list[tuple[dict, list[dict]]]
    verifica: str = ""

    @property
    def id(self) -> str:
        return self.gruppo.id

    @property
    def fonti(self) -> list[str]:
        return self.gruppo.fonti

    @property
    def ultimo(self) -> str:
        return self.gruppo.ultimo


class Costruttore:
    def __init__(self, config: Configurazione, cartella_dati: Path, cartella_sito: Path):
        self.config = config
        self.cartella_dati = cartella_dati
        self.cartella_sito = cartella_sito
        self.ordine_categorie = {c.nome: i for i, c in enumerate(config.categorie)}
        self.ordine_aree = {a.nome: i for i, a in enumerate(config.aree)}
        self.aree_per_nome = {a.nome: a for a in config.aree}
        asse = [a.nome for a in config.aree if a.nome != NON_COLLOCABILE]
        # Ordine in cui scegliere i titoli a confronto: dagli estremi verso il
        # centro (sinistra, destra, centro-sinistra, centro-destra, centro),
        # poi le fonti non collocabili. Così si vede la massima varietà.
        dall_esterno = []
        while asse:
            dall_esterno.append(asse.pop(0))
            if asse:
                dall_esterno.append(asse.pop())
        self.priorita_aree = dall_esterno + [NON_COLLOCABILE]
        self.env = Environment(
            loader=FileSystemLoader(RADICE / "templates"),
            autoescape=select_autoescape(["html"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self.env.filters["data_breve"] = data_breve

    # -- notizie ---------------------------------------------------------------

    def notizie_valide(self) -> list[dict]:
        """Notizie raccolte in automatico + post aggiunti a mano (senza
        doppioni), tolte quelle escluse dai filtri."""
        cfg = self.config
        archivio = leggi(self.cartella_dati / "notizie.json")
        link_noti = {chiave_link(n["link"]) for n in archivio}
        manuali = [n for n in instagram.leggi_post_manuali(cfg) if chiave_link(n["link"]) not in link_noti]
        valide = []
        for n in archivio + manuali:
            fonte = cfg.fonti_per_id.get(n["fonte"])
            if not fonte or not fonte.attiva or solo_data(n["titolo"]):
                continue
            if n.get("canale") == "instagram":
                # I titoli delle didascalie vengono ripuliti anche se salvati prima.
                n = dict(n, titolo=instagram.titolo_social(n["titolo"]) or n["titolo"],
                         estratto=instagram.pulisci_social(n["estratto"]))
            if cfg.scartata(fonte, n["link"], n["titolo"]):
                continue
            valide.append(n)
        return valide

    def storie(self, notizie: list[dict]) -> list[Gruppo]:
        r = self.config["raggruppamento"]
        gruppi = raggruppa(notizie, r["soglia_somiglianza"], r["peso_titolo"], r["parole_chiave"])
        return raggruppa_storie(gruppi, r["soglia_storie"], r["soglia_aggancio"])

    # -- presentazione di una storia ----------------------------------------------

    def fonte(self, id_fonte: str):
        return self.config.fonti_per_id[id_fonte]

    def _agenzia(self, n: dict) -> bool:
        return self.fonte(n["fonte"]).categoria in (self.config["oggi"].get("titolo_preferito_da") or [])

    def scegli_titolo(self, g: Gruppo) -> dict:
        """Il titolo della storia è quello di un articolo vero, il più
        rappresentativo: prima si cerca tra le agenzie (di solito più
        neutre), poi tra le fonti non collocabili, infine tra tutte."""
        def candidati(filtro):
            return [n for n in g.notizie if filtro(n) and n.get("canale") != "instagram"
                    and len(n["titolo"]) >= 25 and not _TITOLO_GENERICO.search(n["titolo"])]

        for filtro in (
            self._agenzia,
            lambda n: self.fonte(n["fonte"]).area == NON_COLLOCABILE,
            lambda n: True,
        ):
            scelti = candidati(filtro)
            if scelti:
                return max(scelti, key=g.centralita)
        return max(g.notizie, key=g.centralita)

    def scegli_confronto(self, g: Gruppo, quanti: int, escludi: set[str]) -> list[dict]:
        """Titoli da mettere uno sotto l'altro: una fonte per volta, scelte in
        modo da coprire aree politiche diverse (prima gli estremi, poi il
        centro, poi le fonti non collocabili), preferendo chi non è un'agenzia."""
        migliori: dict[str, dict] = {}
        for n in g.notizie:
            if n["fonte"] in escludi:
                continue
            attuale = migliori.get(n["fonte"])
            if attuale is None or g.centralita(n) > g.centralita(attuale):
                migliori[n["fonte"]] = n
        per_area: dict[str, list[dict]] = {}
        for n in sorted(migliori.values(), key=lambda n: (self._agenzia(n), -g.centralita(n))):
            per_area.setdefault(self.fonte(n["fonte"]).area, []).append(n)
        scelti: list[dict] = []
        while len(scelti) < quanti and any(per_area.values()):
            for area in self.priorita_aree:
                if per_area.get(area) and len(scelti) < quanti:
                    scelti.append(per_area[area].pop(0))
        scelti.sort(key=lambda n: (self.ordine_aree.get(self.fonte(n["fonte"]).area, 99), n["fonte"]))
        return scelti

    def copertura(self, g: Gruppo) -> list[tuple[object, int]]:
        """Quante fonti diverse per area politica, nell'ordine dell'asse."""
        conteggio = Counter(self.fonte(f).area for f in g.fonti)
        return [(a, conteggio[a.nome]) for a in self.config.aree if conteggio[a.nome]]

    def per_fonte(self, notizie: list[dict]) -> list[tuple[dict, list[dict]]]:
        """(notizia più recente, altre notizie della stessa fonte) per ogni
        fonte, in ordine di area politica e poi di nome."""
        gruppi: dict[str, list[dict]] = {}
        for n in sorted(notizie, key=lambda n: n["pubblicato"], reverse=True):
            gruppi.setdefault(n["fonte"], []).append(n)

        def chiave(id_fonte):
            fonte = self.fonte(id_fonte)
            return (self.ordine_aree.get(fonte.area, 99), fonte.nome.lower())

        return [(gruppi[f][0], gruppi[f][1:]) for f in sorted(gruppi, key=chiave)]

    def verifica(self, titolo: str) -> str:
        """Link "Verifica tu": cerca il titolo sui siti dei grandi giornali."""
        grandi = self.config["fuori_dai_radar"]["categorie_grandi"]
        domini = sorted({
            urlsplit(f.sito).netloc.removeprefix("www.")
            for f in self.config.fonti if f.categoria in grandi and f.sito and f.attiva
        })
        parole = " ".join(re.findall(r"[^\W_]+", titolo)[:10])
        domanda = f"{parole} ({' OR '.join('site:' + d for d in domini)})"
        return f"https://www.google.com/search?q={quote_plus(domanda)}"

    def vista(self, g: Gruppo, con_verifica: bool = False) -> Storia:
        principale = self.scegli_titolo(g)
        quanti = self.config["oggi"].get("titoli_a_confronto", 4)
        titolo = titolo_pulito(principale["titolo"])
        return Storia(
            gruppo=g,
            titolo=titolo,
            fonte_titolo=self.fonte(principale["fonte"]).nome,
            copertura=self.copertura(g),
            confronto=self.scegli_confronto(g, quanti, escludi=set()),
            tutte=self.per_fonte(g.notizie),
            verifica=self.verifica(titolo) if con_verifica else "",
        )

    def punteggio(self, g: Gruppo, ora: datetime) -> float:
        """Più fonti = più importante; le storie ferme da ore perdono peso."""
        ore = (ora - datetime.fromisoformat(g.ultimo.replace("Z", "+00:00"))).total_seconds() / 3600
        return len(g.fonti) / (1 + max(ore, 0) / 12)

    # -- sezioni ---------------------------------------------------------------

    def conta(self, g: Gruppo, categorie: list[str], notizie: list[dict] | None = None) -> int:
        fonti = {n["fonte"] for n in (notizie if notizie is not None else g.notizie)}
        return sum(1 for f in fonti if self.fonte(f).categoria in categorie)

    def fuori_dai_radar(self, storie: list[Gruppo]) -> tuple[list[Gruppo], list[Gruppo]]:
        """Storie raccontate da più fonti indipendenti e poco presenti nei feed
        dei grandi giornali; e, a parte, le segnalazioni di una sola fonte
        d'inchiesta o fact-checking. Opinioni, riepiloghi, dirette e notizie
        senza data non contano."""
        cfg = self.config
        fdr = cfg["fuori_dai_radar"]
        grandi, alternative = fdr["categorie_grandi"], fdr["categorie_alternative"]
        coperte = [s for s in storie if self.conta(s, grandi) > fdr["max_fonti_grandi"]]
        limite = fdr.get("somiglianza_con_argomenti_coperti", 0)

        piu_fonti, singole = [], []
        for s in storie:
            if self.conta(s, grandi) > fdr["max_fonti_grandi"]:
                continue
            ammesse = [n for n in s.notizie
                       if self.fonte(n["fonte"]).categoria not in alternative or cfg.fuori_dai_radar_ammessa(n)]
            fonti_alt = {n["fonte"] for n in ammesse if self.fonte(n["fonte"]).categoria in alternative}
            if not fonti_alt:
                continue
            if limite and any(somiglianza_gruppi(s, c) >= limite for c in coperte):
                continue
            ridotta = Gruppo(notizie=ammesse, centroide=s.centroide, parole_chiave=s.parole_chiave,
                             vettori=s.vettori, filoni=s.filoni)
            if len(fonti_alt) >= fdr["min_fonti_alternative"]:
                piu_fonti.append(ridotta)
            elif len(fonti_alt) == 1 and self.fonte(next(iter(fonti_alt))).categoria in fdr.get("segnalazioni_singole_da", []):
                singole.append(ridotta)
        piu_fonti.sort(key=lambda g: (self.conta(g, alternative), g.ultimo), reverse=True)
        singole.sort(key=lambda g: g.ultimo, reverse=True)
        return piu_fonti, singole

    def prepara(self, ora: datetime) -> dict:
        cfg = self.config
        notizie = self.notizie_valide()
        futuro = ora + timedelta(hours=1)

        def finestra(ore):
            inizio = ora - timedelta(hours=ore)
            return [n for n in notizie if inizio <= data(n) <= futuro]

        # Oggi: le storie più raccontate delle ultime ore.
        oggi = finestra(cfg["oggi"]["finestra_ore"])
        storie_oggi = [s for s in self.storie(oggi) if len(s.fonti) >= cfg["oggi"]["min_fonti"]]
        storie_oggi.sort(key=lambda s: self.punteggio(s, ora), reverse=True)
        storie_oggi = storie_oggi[: cfg["oggi"]["max_storie"]]

        # Tutte le notizie e Fuori dai radar: una finestra più ampia.
        tutte = finestra(cfg["tutte"]["finestra_ore"])
        storie_tutte = self.storie(tutte)
        multiple = sorted((s for s in storie_tutte if len(s.fonti) >= 2),
                          key=lambda s: self.punteggio(s, ora), reverse=True)
        massimo = cfg["tutte"]["max_notizie_singole_per_fonte"]
        conteggio: Counter = Counter()
        singole = []
        for n in sorted((n for s in storie_tutte if len(s.fonti) < 2 for n in s.notizie),
                        key=lambda n: n["pubblicato"], reverse=True):
            if conteggio[n["fonte"]] < massimo:
                conteggio[n["fonte"]] += 1
                singole.append(n)
        fdr_piu, fdr_singole = self.fuori_dai_radar(storie_tutte)

        return {
            "notizie": notizie,
            "oggi": oggi,
            "tutte": tutte,
            "storie_oggi": [self.vista(s) for s in storie_oggi],
            "storie_tutte": [self.vista(s) for s in multiple],
            "singole": singole,
            "fdr_piu_fonti": [self.vista(s, con_verifica=True) for s in fdr_piu],
            "fdr_singole": [self.vista(s, con_verifica=True) for s in fdr_singole],
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

        fonti_attive = [f for f in cfg.fonti if f.attiva]
        notizie_per_fonte = Counter(n["fonte"] for n in dati["tutte"])
        comuni = {
            "sito": cfg["sito"],
            "cfg": cfg.impostazioni,
            "categorie": cfg.categorie,
            "aree": cfg.aree,
            "colori_aree": {a.nome: a.colore for a in cfg.aree},
            "fonti": cfg.fonti_per_id,
            "fonti_attive": sorted(fonti_attive, key=lambda f: f.nome.lower()),
            "aggiornato": data_lunga(ora),
            "aggiornato_iso": ora.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

        pagine = {
            "index.html": ("oggi.html", {"pagina": "oggi", "storie": dati["storie_oggi"]}),
            "tutte.html": ("tutte.html", {"pagina": "tutte", "storie": dati["storie_tutte"],
                                          "singole": dati["singole"]}),
            "fuori-dai-radar.html": ("fuori_dai_radar.html", {"pagina": "radar", "piu_fonti": dati["fdr_piu_fonti"],
                                                               "singole": dati["fdr_singole"]}),
            "poco-coperte.html": ("rimando.html", {"pagina": "radar", "destinazione": "fuori-dai-radar.html"}),
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
            "notizie_oggi": len(dati["oggi"]),
            "storie_oggi": len(dati["storie_oggi"]),
            "storie_tutte": len(dati["storie_tutte"]),
            "fuori_dai_radar": len(dati["fdr_piu_fonti"]),
            "segnalazioni_singole": len(dati["fdr_singole"]),
            "post_manuali": sum(1 for n in dati["tutte"] if n.get("canale") == "manuale"),
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

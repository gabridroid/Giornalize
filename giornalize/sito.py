"""Costruzione del sito statico (cartella site/) a partire dai dati raccolti."""

from __future__ import annotations

import logging
import re
import shutil
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import quote_plus, urlsplit
from zoneinfo import ZoneInfo

import markdown
from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import instagram
from .archivio import data, giorno, leggi, leggi_stato, leggi_storico
from .config import RADICE, Configurazione
from .raggruppa import Gruppo, coseno, raggruppa, raggruppa_storie, somiglianza_gruppi
from .temi import Tema, carica_temi
from .testo import chiave_link, maiuscole_in_minuscole, solo_data

log = logging.getLogger("giornalize.sito")

FUSO = ZoneInfo("Europe/Rome")
GIORNI_SETTIMANA = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
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


def giorno_lungo(g: date) -> str:
    """date(2026, 10, 23) -> 'giovedì 23 ottobre'"""
    return f"{GIORNI_SETTIMANA[g.weekday()]} {g.day} {MESI[g.month - 1]}"


def giorno_breve(g: date) -> str:
    """date(2026, 10, 23) -> 'gio 23'"""
    return f"{GIORNI_SETTIMANA[g.weekday()][:3]} {g.day}"


def titolo_pulito(titolo: str) -> str:
    """Titolo adatto a fare da titolo di una storia: senza etichette tipo
    "VIDEO" o "LIVE" e senza parole tutte in maiuscolo."""
    t = _ETICHETTE_TITOLO.sub("", _ETICHETTE_MAIUSCOLE.sub("", titolo)).strip(" -–|:")
    return maiuscole_in_minuscole(t) or titolo


@dataclass
class Filone:
    """Un aspetto di una storia (es. "decreto · aiuti · gasolio"): un gruppo
    del primo passaggio, con le sue fonti e la sua barra."""
    id: str
    etichetta: str
    fonti: list[str]
    notizie: list[dict]
    copertura: list[tuple[object, int]]
    tutte: list[tuple[dict, list[dict]]]


@dataclass
class VistaTema:
    """Un tema da seguire pronto per la pagina: chi ne ha scritto, quando, e chi no."""
    tema: Tema
    notizie: list[dict]
    conteggio: Counter                       # articoli per fonte
    assenti: list[str]                       # fonti lette nel periodo che non ne hanno scritto
    copertura: list[tuple[object, int]]
    striscia: list[tuple[date, int]]         # articoli per giorno, tutti i giorni del periodo
    giorni: list[tuple[date, list[tuple[dict, list[dict]]]]]  # giorni con articoli, dal più recente
    tabella_giorni: list[date]
    tabella: list[tuple[str, list[int]]]     # fonte -> articoli per giorno
    verifica: str

    @property
    def fonti(self) -> list[str]:
        return [f for f, _ in self.conteggio.most_common()]


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
    # Filoni mostrati (solo se la storia ne ha almeno due con più fonti),
    # gli articoli che non stanno in nessuno di questi, e per ogni articolo
    # l'etichetta del suo filone.
    filoni: list[Filone] = field(default_factory=list)
    altri_articoli: list[tuple[dict, list[dict]]] = field(default_factory=list)
    filone_di: dict[str, str] = field(default_factory=dict)

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
        self.env.filters["giorno_lungo"] = giorno_lungo
        self.env.filters["giorno_breve"] = giorno_breve

    # -- notizie ---------------------------------------------------------------

    def notizie_valide(self, archivio: list[dict] | None = None) -> list[dict]:
        """Notizie raccolte in automatico + post aggiunti a mano (senza
        doppioni), tolte quelle escluse dai filtri."""
        cfg = self.config
        if archivio is None:
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

    def scegli_confronto(self, g: Gruppo, quanti: int, filoni: list[list[dict]]) -> list[dict]:
        """Titoli da mettere uno sotto l'altro, una fonte per volta.

        Prima conta che siano diversi nel contenuto (aspetti diversi della
        storia), poi che vengano da aree politiche diverse: a ogni passo si
        sceglie il titolo meno simile a quelli già scelti, con un vantaggio
        per le aree non ancora presenti e per chi non è un'agenzia."""
        candidati = [n for notizie in filoni for n in notizie]
        if not candidati:
            return []
        rango = {a: i for i, a in enumerate(self.priorita_aree)}

        # Il primo è il titolo più rappresentativo del filone principale.
        primo = max(filoni[0], key=lambda n: (not self._agenzia(n), g.centralita(n)))
        scelti = [primo]
        while len(scelti) < quanti:
            fonti_scelte = {n["fonte"] for n in scelti}
            aree_scelte = {self.fonte(n["fonte"]).area for n in scelti}
            migliore, punteggio = None, -1.0
            for n in candidati:
                if n["fonte"] in fonti_scelte:
                    continue
                v = g.vettori.get(n["id"], {})
                diversita = 1 - max(coseno(v, g.vettori.get(x["id"], {})) for x in scelti)
                area = self.fonte(n["fonte"]).area
                valore = (diversita
                          + (0.25 if area not in aree_scelte else 0)
                          + 0.02 * (len(rango) - rango.get(area, len(rango))) / len(rango)
                          + (0.05 if not self._agenzia(n) else 0)
                          + 0.01 * g.centralita(n))
                if valore > punteggio:
                    migliore, punteggio = n, valore
            if migliore is None:
                break
            scelti.append(migliore)
        scelti.sort(key=lambda n: (self.ordine_aree.get(self.fonte(n["fonte"]).area, 99), n["fonte"]))
        return scelti

    def copertura(self, fonti: list[str]) -> list[tuple[object, int]]:
        """Quante fonti diverse per area politica, nell'ordine dell'asse."""
        conteggio = Counter(self.fonte(f).area for f in set(fonti))
        return [(a, conteggio[a.nome]) for a in self.config.aree if conteggio[a.nome]]

    def filoni(self, g: Gruppo) -> list[tuple[Gruppo, list[dict]]]:
        """I filoni della storia (gruppi del primo passaggio) con le notizie
        che ne restano, dal più raccontato al meno raccontato."""
        presenti = {n["id"] for n in g.notizie}
        risultato = []
        for f in g.filoni or [g]:
            notizie = [n for n in f.notizie if n["id"] in presenti]
            if notizie:
                risultato.append((f, notizie))
        risultato.sort(key=lambda x: (-len({n["fonte"] for n in x[1]}), -len(x[1]), x[0].id))
        return risultato

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

        filoni = self.filoni(g)
        con_piu_fonti = [(f, ns) for f, ns in filoni if len({n["fonte"] for n in ns}) >= 2]
        # Per il confronto contano gli aspetti raccontati da almeno due fonti
        # (se ci sono): un articolo isolato non rappresenta la storia.
        pool = [ns for _, ns in con_piu_fonti] or [ns for _, ns in filoni]
        mostrati: list[Filone] = []
        altri: list[dict] = []
        filone_di: dict[str, str] = {}
        if len(con_piu_fonti) >= 2:
            massimo = self.config["oggi"].get("max_filoni", 6)
            for f, ns in con_piu_fonti[:massimo]:
                etichetta = " · ".join(f.parole_chiave[:3]) or "altro"
                fonti = list(dict.fromkeys(n["fonte"] for n in ns))
                mostrati.append(Filone(id=f.id, etichetta=etichetta, fonti=fonti, notizie=ns,
                                       copertura=self.copertura(fonti), tutte=self.per_fonte(ns)))
                filone_di.update({n["id"]: etichetta for n in ns})
            altri = [n for n in g.notizie if n["id"] not in filone_di]

        return Storia(
            gruppo=g,
            titolo=titolo,
            fonte_titolo=self.fonte(principale["fonte"]).nome,
            copertura=self.copertura(g.fonti),
            confronto=self.scegli_confronto(g, quanti, pool),
            tutte=self.per_fonte(g.notizie),
            verifica=self.verifica(titolo) if con_verifica else "",
            filoni=mostrati,
            altri_articoli=self.per_fonte(altri),
            filone_di=filone_di,
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

    def temi(self, ora: datetime, temi: list[Tema]) -> tuple[list[VistaTema], list[str], int]:
        """Per ogni tema: chi ne ha scritto e quando, negli ultimi giorni
        (archivio + storico). Restituisce anche le fonti attive che nel
        periodo non hanno dato nessuna notizia e quanti giorni copre lo storico."""
        impostazioni = self.config.impostazioni.get("temi", {})
        oggi = ora.astimezone(FUSO).date()
        dal = oggi - timedelta(days=int(impostazioni.get("giorni", 30)) - 1)
        per_id = {n["id"]: n for n in leggi_storico(self.cartella_dati / "storico", dal)}
        per_id.update({n["id"]: n for n in leggi(self.cartella_dati / "notizie.json")})
        notizie = [n for n in self.notizie_valide(list(per_id.values())) if dal <= giorno(n) <= oggi]
        if notizie:
            dal = max(dal, min(giorno(n) for n in notizie))  # lo storico può essere più corto
        periodo = [dal + timedelta(days=i) for i in range((oggi - dal).days + 1)]
        tabella_giorni = periodo[-int(impostazioni.get("giorni_tabella", 14)):]

        def ordine(id_fonte):
            fonte = self.fonte(id_fonte)
            return (self.ordine_aree.get(fonte.area, 99), fonte.nome.lower())

        lette = sorted({n["fonte"] for n in notizie}, key=ordine)
        non_lette = sorted((f.id for f in self.config.fonti if f.attiva and f.id not in lette), key=ordine)

        viste = []
        for tema in temi:
            trovate = sorted((n for n in notizie if tema.corrisponde(f"{n['titolo']} {n.get('estratto', '')}")),
                             key=lambda n: n["pubblicato"], reverse=True)
            conteggio = Counter(n["fonte"] for n in trovate)
            per_giorno: dict[date, list[dict]] = {}
            for n in trovate:
                per_giorno.setdefault(giorno(n), []).append(n)
            celle = Counter((n["fonte"], giorno(n)) for n in trovate)
            parole = " ".join(gruppo[0].testo.rstrip("*") for gruppo in tema.gruppi)
            viste.append(VistaTema(
                tema=tema,
                notizie=trovate,
                conteggio=conteggio,
                assenti=[f for f in lette if f not in conteggio],
                copertura=self.copertura(list(conteggio)),
                striscia=[(g, len(per_giorno.get(g, []))) for g in periodo],
                giorni=[(g, self.per_fonte(per_giorno[g])) for g in sorted(per_giorno, reverse=True)],
                tabella_giorni=tabella_giorni,
                tabella=[(f, [celle[(f, g)] for g in tabella_giorni]) for f in lette],
                verifica=self.verifica(parole),
            ))
        return viste, non_lette, len(periodo)

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

        viste_temi, non_lette, giorni_periodo = self.temi(ora, carica_temi())
        pagine = {
            "index.html": ("oggi.html", {"pagina": "oggi", "storie": dati["storie_oggi"]}),
            "tutte.html": ("tutte.html", {"pagina": "tutte", "storie": dati["storie_tutte"],
                                          "singole": dati["singole"]}),
            "fuori-dai-radar.html": ("fuori_dai_radar.html", {"pagina": "radar", "piu_fonti": dati["fdr_piu_fonti"],
                                                               "singole": dati["fdr_singole"]}),
            "poco-coperte.html": ("rimando.html", {"pagina": "radar", "destinazione": "fuori-dai-radar.html"}),
            "fonti.html": ("fonti.html", {"pagina": "fonti", "stato": dati["stato"],
                                          "notizie_per_fonte": notizie_per_fonte}),
            "temi.html": ("temi.html", {"pagina": "temi", "temi": viste_temi, "non_lette": non_lette,
                                        "giorni_periodo": giorni_periodo}),
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

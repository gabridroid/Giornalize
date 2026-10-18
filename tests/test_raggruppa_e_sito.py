import json
import re
from collections import defaultdict
from html.parser import HTMLParser

import pytest

from giornalize import archivio, raccolta
from giornalize.raggruppa import raggruppa
from giornalize.sito import Costruttore


@pytest.fixture
def notizie(config, internet_finto, ora):
    trovate, _ = raccolta.raccogli_tutto(config, ora)
    return trovate


def argomento_atteso(n):
    import dati_prova
    for fonte, _, titolo, _, argomento in dati_prova.NOTIZIE:
        if fonte == n["fonte"] and titolo == n["titolo"]:
            return argomento
    raise KeyError(n["titolo"])


def test_raggruppamento_per_argomento(config, notizie):
    r = config["raggruppamento"]
    gruppi = raggruppa(notizie, r["soglia_somiglianza"], r["peso_titolo"], r["parole_chiave"])
    posizione = defaultdict(set)
    for i, g in enumerate(gruppi):
        argomenti = {argomento_atteso(n) for n in g.notizie}
        # nessun gruppo mescola argomenti diversi
        assert len(argomenti) == 1, [n["titolo"] for n in g.notizie]
        if None in argomenti:
            assert len(g.notizie) == 1, [n["titolo"] for n in g.notizie]
        for a in argomenti:
            posizione[a].add(i)
    # ogni argomento finisce in un solo gruppo
    assert all(len(v) == 1 for a, v in posizione.items() if a), dict(posizione)


@pytest.fixture
def sito(config, notizie, ora, tmp_path):
    dati = tmp_path / "data"
    tutte, _ = archivio.unisci([], notizie, ora, 7)
    archivio.scrivi(dati / "notizie.json", tutte, ora)
    costruttore = Costruttore(config, dati, tmp_path / "site")
    riassunto = costruttore.costruisci(ora)
    return tmp_path / "site", costruttore.prepara(ora), riassunto


def test_sezione_poco_coperte(sito, config):
    _, dati, _ = sito
    pc = config["poco_coperte"]
    piu_fonti = {argomento_atteso(g.notizie[0]) for g in dati["poco_piu_fonti"]}
    # asili: 3 alternative + 1 quotidiano; sbarchi: 3 alternative; affitti: 3 + 1;
    # rai: 2 alternative + 1 quotidiano. Gli altri argomenti hanno molti grandi giornali.
    assert piu_fonti == {"asili", "sbarchi", "affitti", "rai"}
    # una sola fonte alternativa, al massimo un grande giornale
    una_fonte = dati["poco_una_fonte"]
    fonti_singole = {f for g in una_fonte for f in g.fonti}
    assert {"nicolaporro", "breakingitaly"} <= fonti_singole
    for g in una_fonte:
        cat = [config.fonti_per_id[f].categoria for f in g.fonti]
        assert sum(c in pc["categorie_alternative"] for c in cat) == 1
        assert sum(c in pc["categorie_grandi"] for c in cat) <= pc["max_fonti_grandi"]


def test_poco_coperte_massimo_per_fonte(config, ora, tmp_path):
    from datetime import timedelta
    notizie = [
        {"id": f"p{i}", "fonte": "nicolaporro", "titolo": titolo,
         "estratto": "", "link": f"https://www.nicolaporro.it/{i}", "pubblicato": raccolta.iso(ora - timedelta(hours=i)),
         "raccolto": raccolta.iso(ora), "canale": "rss"}
        for i, titolo in enumerate([
            "La rassegna stampa del mattino", "Tasse sulla casa, il conto per le famiglie",
            "Energia nucleare, il dibattito torna in Parlamento", "Scuola, i presidi contro le nuove regole",
            "Calcio, il derby finisce in pareggio", "Treni in ritardo sulla linea adriatica",
            "Vaccini antinfluenzali, partita la campagna",
        ])
    ]
    archivio.scrivi(tmp_path / "data" / "notizie.json", notizie, ora)
    dati = Costruttore(config, tmp_path / "data", tmp_path / "site").prepara(ora)
    assert len(dati["poco_una_fonte"]) == config["poco_coperte"]["max_argomenti_per_fonte"]


class _Link(HTMLParser):
    def __init__(self):
        super().__init__()
        self.card_link = []
        self._in_titolo = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "h3" and "card-titolo" in (a.get("class") or ""):
            self._in_titolo = True
        elif tag == "a" and self._in_titolo:
            self.card_link.append(a["href"])
            self._in_titolo = False


def test_pagine_e_link(sito, notizie):
    cartella, dati, riassunto = sito
    for pagina in ("index.html", "poco-coperte.html", "fonti.html", "come-funziona.html", "perche.html"):
        assert (cartella / pagina).exists()
    html = (cartella / "index.html").read_text(encoding="utf-8")
    lettore = _Link()
    lettore.feed(html)
    link_validi = {n["link"] for n in notizie}
    assert lettore.card_link, "nessuna card nella pagina"
    # ogni card porta all'articolo originale
    assert set(lettore.card_link) <= link_validi
    # e ogni articolo compare una sola volta nei gruppi
    assert len(lettore.card_link) == len(set(lettore.card_link))
    assert 'name="viewport"' in html
    assert riassunto["gruppi"] == 8
    # una card per fonte in ogni gruppo, e ogni notizia dei gruppi ha il suo link nella pagina
    assert len(lettore.card_link) == sum(len(g.fonti) for g in dati["gruppi"])
    for g in dati["gruppi"]:
        for n in g.notizie:
            assert f'href="{n["link"]}"' in html


def test_censura_solo_nella_pagina_di_posizione(sito):
    cartella, _, _ = sito
    for pagina in cartella.glob("*.html"):
        if pagina.name == "perche.html":
            continue
        assert not re.search(r"censur", pagina.read_text(encoding="utf-8"), re.I), pagina.name


def test_notizie_di_fonti_tolte_non_compaiono(config, sito, tmp_path, ora):
    cartella, _, _ = sito
    config.fonti_per_id["fanpage"].attiva = False
    Costruttore(config, tmp_path / "data", cartella).costruisci(ora)
    assert "data-fonte=\"fanpage\"" not in (cartella / "index.html").read_text(encoding="utf-8")


def test_stato_fonti(tmp_path, config, internet_finto, ora):
    _, stati = raccolta.raccogli_tutto(config, ora)
    percorso = tmp_path / "stato.json"
    archivio.scrivi_stato(percorso, stati)
    letto = json.loads(percorso.read_text(encoding="utf-8"))
    assert letto["ansa"]["ultimo_successo"] == raccolta.iso(ora)

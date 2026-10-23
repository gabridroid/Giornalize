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


def test_storie_di_oggi(sito, config):
    _, dati, _ = sito
    storie = dati["storie_oggi"]
    assert {argomento_atteso(s.gruppo.notizie[0]) for s in storie} == {
        "manovra", "maltempo", "sciopero", "gaza", "asili", "rai", "affitti", "sbarchi"}
    assert len(storie) <= config["oggi"]["max_storie"]
    manovra = next(s for s in storie if argomento_atteso(s.gruppo.notizie[0]) == "manovra")
    # il titolo è quello dell'agenzia, e si dice di chi è
    assert manovra.fonte_titolo == "ANSA"
    assert manovra.titolo.startswith("Manovra, il governo approva il testo")
    # titoli a confronto: fonti diverse, aree diverse, al massimo quanti previsti
    fonti_confronto = [n["fonte"] for n in manovra.confronto]
    assert len(fonti_confronto) == len(set(fonti_confronto)) == config["oggi"]["titoli_a_confronto"]
    aree = {config.fonti_per_id[f].area for f in fonti_confronto}
    assert {"centro-sinistra", "centro", "centro-destra"} <= aree
    # la barra conta ogni fonte una volta
    assert sum(n for _, n in manovra.copertura) == len(manovra.fonti)
    for s in storie:
        assert len(s.fonti) >= config["oggi"]["min_fonti"]
        assert {n["fonte"] for n, _ in s.tutte} == set(s.fonti)


def test_fuori_dai_radar(sito, config):
    _, dati, _ = sito
    fdr = config["fuori_dai_radar"]
    piu_fonti = {argomento_atteso(s.gruppo.notizie[0]) for s in dati["fdr_piu_fonti"]}
    # asili: 3 alternative + 1 quotidiano; sbarchi: 3 alternative; affitti: 3 + 1;
    # rai: 2 alternative + 1 quotidiano. Gli altri argomenti hanno molti grandi giornali.
    assert piu_fonti == {"asili", "sbarchi", "affitti", "rai"}
    for s in dati["fdr_piu_fonti"]:
        cat = [config.fonti_per_id[f].categoria for f in s.fonti]
        assert sum(c in fdr["categorie_alternative"] for c in cat) >= fdr["min_fonti_alternative"]
        assert sum(c in fdr["categorie_grandi"] for c in cat) <= fdr["max_fonti_grandi"]
        assert s.verifica.startswith("https://www.google.com/search?q=")
    # segnalazioni di una sola fonte: solo inchiesta e fact-checking, niente rassegne stampa
    singole = dati["fdr_singole"]
    assert [s.titolo for s in singole] == ["Il video del ponte crollato in Liguria è del 2018, non di questa settimana"]
    for s in singole:
        assert config.fonti_per_id[s.fonti[0]].categoria in fdr["segnalazioni_singole_da"]


def test_fuori_dai_radar_esclude_opinioni_e_notizie_senza_data(config, ora, tmp_path):
    from datetime import timedelta

    def notizia(i, fonte, titolo, link, ore):
        pubblicato = raccolta.iso(ora - timedelta(hours=ore))
        return {"id": f"x{i}", "fonte": fonte, "titolo": titolo, "estratto": "", "link": link,
                "pubblicato": pubblicato, "raccolto": raccolta.iso(ora), "canale": "rss"}

    titolo = "Rifiuti tossici nella discarica abusiva vicino al fiume Sarno"
    notizie = [
        notizia(1, "irpimedia", titolo, "https://irpimedia.example.it/inchiesta/sarno", 5),
        notizia(2, "valigiablu", titolo + ", il commento", "https://valigiablu.example.it/opinioni/sarno", 4),
        notizia(3, "fanpage", titolo + ": cosa sappiamo", "https://fanpage.example.it/sarno", 0),  # senza data
        notizia(4, "facta", "La rassegna stampa del mattino sui rifiuti", "https://facta.example.it/rassegna", 3),
    ]
    archivio.scrivi(tmp_path / "data" / "notizie.json", notizie, ora)
    dati = Costruttore(config, tmp_path / "data", tmp_path / "site").prepara(ora)
    # resta una sola fonte che conta (IrpiMedia): niente "più fonti", ma una segnalazione
    assert dati["fdr_piu_fonti"] == []
    assert [s.fonti for s in dati["fdr_singole"]] == [["irpimedia"]]


def test_raggruppa_storie_unisce_i_filoni():
    from giornalize.raggruppa import Gruppo, raggruppa_storie

    def gruppo(fonti, centroide, nome):
        notizie = [{"id": f"{nome}{i}", "fonte": f, "titolo": nome, "pubblicato": f"2026-10-17T1{i}:00:00Z"}
                   for i, f in enumerate(fonti)]
        return Gruppo(notizie=notizie, centroide=dict(centroide), parole_chiave=[nome])

    scontri = gruppo(["ansa", "corriere", "libero"], {"scontr": 1, "milan": 1, "corte": 1}, "scontri")
    danni = gruppo(["repubblica", "ilgiornale"], {"scontr": 1, "milan": 1, "piantedos": 1}, "danni")
    papa = gruppo(["ansa", "avvenire"], {"papa": 1, "medic": 1}, "papa")
    vetrine = gruppo(["open"], {"scontr": .5, "milan": .5, "vetrin": 1}, "vetrine")
    isolata = gruppo(["ilpost"], {"tram": 1, "bologn": 1}, "tram")
    storie = raggruppa_storie([scontri, danni, papa, vetrine, isolata], 0.18, 0.25)
    composizione = sorted(sorted(f.parole_chiave[0] for f in s.filoni) for s in storie)
    assert composizione == [["danni", "scontri", "vetrine"], ["papa"], ["tram"]]
    principale = next(s for s in storie if len(s.filoni) == 3)
    assert principale.parole_chiave == ["scontri"]  # dal filone con più fonti
    assert len(principale.fonti) == 6


def test_una_sola_parola_in_comune_non_basta(ora):
    notizie = [
        {"id": "a", "fonte": "libero", "titolo": "Tg Sport", "estratto": "", "pubblicato": "2026-10-17T10:00:00Z"},
        {"id": "b", "fonte": "ilpost", "titolo": "Tony Effe fa sport", "estratto": "", "pubblicato": "2026-10-17T11:00:00Z"},
        {"id": "c", "fonte": "internazionale", "titolo": "Con il raffreddore è meglio non fare sport",
         "estratto": "", "pubblicato": "2026-10-17T12:00:00Z"},
    ]
    assert len(raggruppa(notizie, 0.30)) == 3


def test_titolo_pulito():
    from giornalize.sito import titolo_pulito
    assert titolo_pulito("VIDEO | Crollo a Roma, evacuate tre palazzine") == "Crollo a Roma, evacuate tre palazzine"
    assert titolo_pulito("Squalo libero in Corea del Sud – Il video") == "Squalo libero in Corea del Sud"
    assert titolo_pulito("Ucraina, vertice in vista LIVE") == "Ucraina, vertice in vista"
    assert titolo_pulito("SCIOPERO GENERALE DEI TRASPORTI") == "Sciopero generale dei trasporti"
    # "foto" e "diretta" dentro la frase restano
    assert titolo_pulito("Il ministro mostra la foto") == "Il ministro mostra la foto"


class _Link(HTMLParser):
    """Raccoglie i link dei titoli (classe "titolo-link")."""

    def __init__(self):
        super().__init__()
        self.link = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "a" and "titolo-link" in (a.get("class") or ""):
            self.link.append(a["href"])


def test_pagine_e_link(sito, notizie):
    cartella, dati, riassunto = sito
    for pagina in ("index.html", "tutte.html", "fuori-dai-radar.html", "poco-coperte.html", "fonti.html",
                   "come-funziona.html", "perche.html", "404.html"):
        assert (cartella / pagina).exists(), pagina
    link_validi = {n["link"] for n in notizie}
    html = (cartella / "index.html").read_text(encoding="utf-8")
    lettore = _Link()
    lettore.feed(html)
    assert lettore.link, "nessun titolo nella pagina"
    # ogni titolo porta all'articolo originale
    assert set(lettore.link) <= link_validi
    assert 'name="viewport"' in html
    assert riassunto["storie_oggi"] == 8
    # ogni articolo delle storie di oggi ha il suo link nella pagina
    for s in dati["storie_oggi"]:
        for n in s.gruppo.notizie:
            assert f'href="{n["link"]}"' in html
    # lo sport è escluso da tutte le pagine
    for pagina in cartella.glob("*.html"):
        assert "Napoli vince il derby" not in pagina.read_text(encoding="utf-8"), pagina.name
    # il vecchio indirizzo porta alla nuova pagina
    assert 'url=fuori-dai-radar.html' in (cartella / "poco-coperte.html").read_text(encoding="utf-8")
    # le notizie di una sola fonte sono nella pagina "Tutte"
    tutte = (cartella / "tutte.html").read_text(encoding="utf-8")
    for n in dati["singole"]:
        assert f'href="{n["link"]}"' in tutte


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
    for pagina in ("index.html", "tutte.html", "fuori-dai-radar.html"):
        assert "data-fonte=\"fanpage\"" not in (cartella / pagina).read_text(encoding="utf-8")


def test_stato_fonti(tmp_path, config, internet_finto, ora):
    _, stati = raccolta.raccogli_tutto(config, ora)
    percorso = tmp_path / "stato.json"
    archivio.scrivi_stato(percorso, stati)
    letto = json.loads(percorso.read_text(encoding="utf-8"))
    assert letto["ansa"]["ultimo_successo"] == raccolta.iso(ora)


def test_filoni_e_titoli_diversi(config, tmp_path):
    from giornalize.raggruppa import Gruppo, raggruppa_storie

    def filone(nome, voci, centroide):
        notizie, vettori = [], {}
        for i, (fonte, titolo, vettore) in enumerate(voci):
            n = {"id": f"{nome}{i}", "fonte": fonte, "titolo": titolo, "estratto": "", "canale": "rss",
                 "link": f"https://{fonte}.example.it/{nome}{i}", "pubblicato": f"2026-10-17T1{i}:00:00Z"}
            notizie.append(n)
            vettori[n["id"]] = vettore
        return Gruppo(notizie=notizie, centroide=centroide, parole_chiave=nome.split(), vettori=vettori)

    aiuti = filone("decreto aiuti gasolio", [
        ("ansa", "Tir, il governo approva il decreto aiuti da 105 milioni", {"tir": .5, "decret": .7, "aiut": .5}),
        ("repubblica", "Decreto aiuti, 105 milioni per il gasolio dei tir", {"tir": .5, "decret": .6, "aiut": .6}),
        ("ilgiornale", "Caro gasolio, via libera al decreto aiuti", {"decret": .7, "aiut": .7}),
        ("libero", "Decreto aiuti per i tir, Meloni: ascoltiamo tutti", {"tir": .5, "decret": .6, "aiut": .6}),
    ], {"tir": 1.5, "decret": 2.6, "aiut": 2.4, "gasoli": .5})
    denunce = filone("identificati denunce tir", [
        ("corriere", "Blocchi dei tir, identificati e denunciati 40 camionisti", {"tir": .5, "denunc": .7, "identific": .5}),
        ("manifesto", "Tir, denunce e fogli di via contro chi protesta", {"tir": .5, "denunc": .8}),
    ], {"tir": 1.0, "denunc": 1.5, "identific": .5, "decret": .1, "aiut": .1})
    storia = raggruppa_storie([aiuti, denunce], 0.18, 0.25)
    assert len(storia) == 1

    vista = Costruttore(config, tmp_path, tmp_path / "site").vista(storia[0])
    assert [f.etichetta for f in vista.filoni] == ["decreto · aiuti · gasolio", "identificati · denunce · tir"]
    assert [len(f.fonti) for f in vista.filoni] == [4, 2]
    assert sum(n for _, n in vista.filoni[1].copertura) == 2
    # tra i titoli a confronto c'è almeno un titolo di ogni filone
    assert {vista.filone_di[n["id"]] for n in vista.confronto} == {f.etichetta for f in vista.filoni}
    assert len({n["fonte"] for n in vista.confronto}) == len(vista.confronto) == 4

"""Temi da seguire: regole di ricerca, file temi.yaml e storico giornaliero."""

from datetime import date, timedelta

import pytest

from giornalize import archivio, raccolta
from giornalize.config import ErroreConfigurazione
from giornalize.sito import Costruttore
from giornalize.temi import Tema, carica_temi, interpreta


def tema(cerca):
    return Tema(id="t", nome="t", cerca=cerca, gruppi=interpreta(cerca))


def test_regole_di_ricerca():
    t = tema("denunciati, multe, foglio di via + tir, agricoltori")
    assert t.corrisponde("Blocchi dei Tir, 40 camionisti denunciati a Napoli")
    assert t.corrisponde("Tir, una multa da mille euro")              # singolare e plurale
    assert t.corrisponde("Fogli di via per tre agricoltori")           # espressione di più parole
    assert t.corrisponde("DENUNCIATO UN AUTISTA DI TIR")               # maiuscole
    assert not t.corrisponde("Multe agli automobilisti")               # manca il secondo gruppo
    assert not t.corrisponde("Agricoltori in piazza a Roma")           # manca il primo gruppo
    assert not t.corrisponde("Tiramisù e agricoltori")                 # "tir" non è "tiramisù"
    asterisco = tema("denunc*")
    assert asterisco.corrisponde("Le denunce dei sindacati")
    assert asterisco.corrisponde("Il sindaco denuncia")
    assert not asterisco.corrisponde("Il denaro")
    assert tema("città").corrisponde("Le citta del Sud")               # accenti


def test_file_temi(tmp_path):
    assert carica_temi()  # il vero temi.yaml è valido
    file = tmp_path / "temi.yaml"
    file.write_text("temi:\n  - nome: Prova\n    cerca: \"a, b + c\"\n  - nome: Spento\n    cerca: x\n"
                    "    attivo: false\n", encoding="utf-8")
    temi = carica_temi(file)
    assert [t.nome for t in temi] == ["Prova"]
    assert temi[0].descrizione_gruppi == ["a, b", "c"]
    file.write_text("temi:\n  - nome: Senza parole\n", encoding="utf-8")
    with pytest.raises(ErroreConfigurazione, match="«nome» e «cerca»"):
        carica_temi(file)


def test_storico_giornaliero(tmp_path, ora):
    def notizia(i, ore_fa, link=None):
        return {"id": f"n{i}", "fonte": "ansa", "titolo": f"Titolo {i}", "estratto": "",
                "link": link or f"https://ansa.example.it/{i}", "raccolto": raccolta.iso(ora),
                "pubblicato": raccolta.iso(ora - timedelta(hours=ore_fa)), "canale": "rss"}

    cartella = tmp_path / "storico"
    vecchia = cartella / "2026-09-01.json"
    cartella.mkdir()
    vecchia.write_text('{"notizie": []}', encoding="utf-8")
    notizie = [notizia(1, 1), notizia(2, 30), notizia(3, 2, link="https://ansa.example.it/1?utm_source=x")]
    assert archivio.aggiorna_storico(cartella, notizie, ora, 30) == 2
    assert not vecchia.exists()  # più vecchia di 30 giorni
    # Una seconda volta non cambia nulla e non crea doppioni.
    assert archivio.aggiorna_storico(cartella, notizie, ora, 30) == 0
    oggi = archivio.leggi(cartella / "2026-10-17.json")
    assert [n["id"] for n in oggi] == ["n1"]
    assert "raccolto" not in oggi[0]
    assert {n["id"] for n in archivio.leggi_storico(cartella, date(2026, 10, 1))} == {"n1", "n2"}
    assert [n["id"] for n in archivio.leggi_storico(cartella, date(2026, 10, 17))] == ["n1"]


def test_pagina_temi(config, internet_finto, ora, tmp_path):
    trovate, _ = raccolta.raccogli_tutto(config, ora)
    dati = tmp_path / "data"
    tutte, _ = archivio.unisci([], trovate, ora, 7)
    archivio.scrivi(dati / "notizie.json", tutte, ora)
    # Lo storico contiene anche una notizia di cinque giorni fa.
    vecchia = {"id": "vecchia", "fonte": "libero", "titolo": "Sciopero dei treni, disagi per i pendolari",
               "estratto": "", "link": "https://libero.example.it/sciopero", "canale": "rss",
               "pubblicato": raccolta.iso(ora - timedelta(days=5))}
    archivio.aggiorna_storico(dati / "storico", [vecchia], ora, 30)

    costruttore = Costruttore(config, dati, tmp_path / "site")
    viste, non_lette, giorni = costruttore.temi(ora, [tema("sciopero + treni, bus")])
    v = viste[0]
    assert set(v.conteggio) == {"ansa", "rainews", "fanpage", "open", "libero"}
    assert giorni == 6 and sum(n for _, n in v.striscia) == len(v.notizie) == 5
    # chi non ne ha scritto è tra le fonti lette; chi non è stato letto (feed rotto) è a parte
    assert "corriere" in v.assenti and "skytg24" not in v.assenti and "skytg24" in non_lette
    assert not set(v.assenti) & set(v.conteggio)
    costruttore.costruisci(ora)
    assert (tmp_path / "site" / "temi.html").exists()

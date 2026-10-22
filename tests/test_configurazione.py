"""Controlla che i file modificati a mano (sources.yaml, config.yaml) siano validi."""

import pytest

from giornalize.config import ErroreConfigurazione, carica


def test_file_veri_validi():
    config = carica()  # solleva un errore spiegato se sources.yaml o config.yaml hanno problemi
    assert config.fonti


def test_errori_spiegati(tmp_path):
    from giornalize.config import RADICE
    sbagliato = tmp_path / "fonti.yaml"
    sbagliato.write_text("fonti:\n  - id: prova\n    nome: Prova\n    categoria: Giornali a caso\n", encoding="utf-8")
    with pytest.raises(ErroreConfigurazione, match="categoria «Giornali a caso» non esiste"):
        carica(RADICE / "config.yaml", sbagliato)

    sbagliato.write_text("fonti:\n  - id: Il Post\n    nome: Il Post\n    categoria: Quotidiani nazionali\n", encoding="utf-8")
    with pytest.raises(ErroreConfigurazione, match="solo"):
        carica(RADICE / "config.yaml", sbagliato)

    sbagliato.write_text("fonti:\n  - id: prova\n    nome: Prova\n    categoria: Quotidiani nazionali\n"
                         "    area: estrema sinistra\n", encoding="utf-8")
    with pytest.raises(ErroreConfigurazione, match="area «estrema sinistra» non esiste"):
        carica(RADICE / "config.yaml", sbagliato)

    sbagliato.write_text("fonti:\n  - id: a\n   nome: rientro sbagliato\n", encoding="utf-8")
    with pytest.raises(ErroreConfigurazione, match="errore di scrittura"):
        carica(RADICE / "config.yaml", sbagliato)


def test_filtri_sport_e_spettacolo():
    config = carica()
    fonte = config.fonti_per_id["ilpost"]
    assert config.scartata(fonte, "https://www.ilpost.it/sport/calcio/derby", "Il derby")
    assert config.scartata(fonte, "https://www.ilpost.it/2026/10/22/derby", "Serie A, il derby finisce pari")
    # sezione dichiarata nel feed, quando l'indirizzo non la dice
    assert config.scartata(fonte, "https://www.ilpost.it/2026/10/22/como", "Il Como batte lo United", ["Sport"])
    assert not config.scartata(fonte, "https://www.ilpost.it/2026/10/22/manovra", "La manovra in breve", ["Italia"])


def test_regole_fuori_dai_radar():
    config = carica()
    base = {"fonte": "irpimedia", "titolo": "L'inchiesta sugli appalti", "link": "https://irpi.media/appalti",
            "pubblicato": "2026-10-17T10:00:00Z", "raccolto": "2026-10-17T12:00:00Z", "canale": "rss"}
    assert config.fuori_dai_radar_ammessa(base)
    assert not config.fuori_dai_radar_ammessa(dict(base, raccolto=base["pubblicato"]))  # senza data
    assert config.fuori_dai_radar_ammessa(dict(base, raccolto=base["pubblicato"], canale="manuale"))
    assert not config.fuori_dai_radar_ammessa(dict(base, link="https://irpi.media/opinioni/appalti"))
    assert not config.fuori_dai_radar_ammessa(dict(base, titolo="La rassegna stampa di oggi"))
    assert not config.fuori_dai_radar_ammessa(dict(base, titolo="Tg delle 20 - 21/10/2026"))

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

    sbagliato.write_text("fonti:\n  - id: a\n   nome: rientro sbagliato\n", encoding="utf-8")
    with pytest.raises(ErroreConfigurazione, match="errore di scrittura"):
        carica(RADICE / "config.yaml", sbagliato)

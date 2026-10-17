import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

CARTELLA_TEST = Path(__file__).parent
sys.path.insert(0, str(CARTELLA_TEST))

from giornalize import raccolta  # noqa: E402
from giornalize.config import RADICE, carica  # noqa: E402

import dati_prova  # noqa: E402

ORA = datetime(2026, 10, 17, 18, 0, tzinfo=timezone.utc)


@pytest.fixture
def ora():
    return ORA


@pytest.fixture
def config():
    return carica(RADICE / "config.yaml", CARTELLA_TEST / "fixtures" / "sources_prova.yaml")


@pytest.fixture
def internet_finto(monkeypatch, ora):
    """Sostituisce internet: ogni feed .example.it restituisce le notizie di prova.
    Il dizionario restituito permette ai test di simulare errori."""
    per_fonte = dati_prova.notizie_per_fonte(ora)
    risposte: dict[str, object] = {}
    for fonte, voci in per_fonte.items():
        risposte[f"https://{fonte}.example.it/feed.xml"] = dati_prova.feed_rss(voci, fonte)

    def scarica_finto(url, timeout):
        risposta = risposte.get(url)
        if risposta is None:
            raise raccolta.requests.HTTPError(
                response=type("R", (), {"status_code": 404})()
            )
        if isinstance(risposta, Exception):
            raise risposta
        return risposta

    monkeypatch.setattr(raccolta, "scarica", scarica_finto)
    return risposte

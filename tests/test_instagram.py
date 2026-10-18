import pytest

from giornalize import instagram, raccolta

MODULO = """### Link al post

https://www.instagram.com/p/ABC123/?utm_source=ig_web_copy_link

### Fonte

@factanza

### Titolo

Il caro affitti spiegato in cinque punti

### Riassunto

Un carosello sui prezzi degli affitti nelle città universitarie.

### Data e ora del post

_No response_
"""


def test_post_aggiunto_dal_modulo(config, ora, post_manuali_vuoti):
    notizia = instagram.aggiungi_da_modulo(MODULO, config, ora)
    assert notizia["fonte"] == "factanza"
    assert notizia["link"] == "https://www.instagram.com/p/ABC123/"
    assert notizia["canale"] == "manuale"
    assert notizia["pubblicato"] == raccolta.iso(ora.replace(second=0))  # data vuota = adesso
    # il post è nel file e viene riletto
    letti = instagram.leggi_post_manuali(config)
    assert [n["titolo"] for n in letti] == ["Il caro affitti spiegato in cinque punti"]
    assert "POST AGGIUNTI A MANO" in post_manuali_vuoti.read_text(encoding="utf-8")
    # lo stesso link non si aggiunge due volte
    with pytest.raises(instagram.ErrorePost, match="già stato aggiunto"):
        instagram.aggiungi_da_modulo(MODULO, config, ora)


def test_modulo_con_errori_spiegati(config, ora):
    with pytest.raises(instagram.ErrorePost, match="non trovo la fonte"):
        instagram.aggiungi_da_modulo(MODULO.replace("@factanza", "Pagina Sconosciuta"), config, ora)
    with pytest.raises(instagram.ErrorePost, match="data"):
        instagram.aggiungi_da_modulo(MODULO.replace("_No response_", "ieri sera"), config, ora)
    with pytest.raises(instagram.ErrorePost, match="link"):
        instagram.aggiungi_da_modulo(MODULO.replace("https://www.instagram.com/p/ABC123/", "instagram"), config, ora)


def test_post_scritti_male_saltati(config, post_manuali_vuoti):
    post_manuali_vuoti.write_text(
        """
- fonte: torcha
  link: https://www.instagram.com/p/UNO/
  titolo: Post giusto
  data: 2026-10-17 10:00
- fonte: torcha
  link: https://www.instagram.com/p/DUE/
  titolo: Post senza data
""", encoding="utf-8")
    notizie = instagram.leggi_post_manuali(config)
    assert [n["titolo"] for n in notizie] == ["Post giusto"]
    assert notizie[0]["pubblicato"] == "2026-10-17T08:00:00Z"  # ora italiana -> UTC


def test_titolo_dalla_didascalia():
    titolo, resto = instagram.titolo_da_didascalia(
        "Cosa sappiamo dello sciopero di venerdì 🚆\n\nTreni e bus fermi per 24 ore. #sciopero @trenitalia"
    )
    assert titolo == "Cosa sappiamo dello sciopero di venerdì 🚆"
    assert resto == "Treni e bus fermi per 24 ore."


class _Risposta:
    def __init__(self, dati, codice=200):
        self._dati, self.status_code, self.content = dati, codice, b"x"

    def json(self):
        return self._dati

    def raise_for_status(self):
        if self.status_code >= 400:
            raise raccolta.requests.HTTPError(response=self)


def test_api_instagram(config, ora, monkeypatch):
    fonte = config.fonti_per_id["torcha"]
    fonte.instagram, fonte.instagram_api, fonte.feed, fonte.sito = "@torcha", True, [], ""
    # senza i segreti l'API resta spenta
    _, stato = raccolta.raccogli_fonte(fonte, config, ora)
    assert stato["esito"] == "nessun_canale"

    monkeypatch.setenv("INSTAGRAM_TOKEN", "segreto")
    monkeypatch.setenv("INSTAGRAM_ACCOUNT_ID", "123")
    chiamate = []

    def get_finto(url, params, timeout):
        chiamate.append((url, params))
        return _Risposta({"business_discovery": {"media": {"data": [
            {"caption": "Manovra, cosa cambia per i giovani\nLe misure spiegate. #manovra",
             "permalink": "https://www.instagram.com/p/XYZ/", "timestamp": "2026-10-17T10:00:00+0000"},
            {"caption": "", "permalink": "https://www.instagram.com/p/VUOTO/", "timestamp": "2026-10-17T09:00:00+0000"},
        ]}}})

    monkeypatch.setattr(instagram.requests, "get", get_finto)
    notizie, stato = raccolta.raccogli_fonte(fonte, config, ora)
    assert stato["esito"] == "ok"
    assert [(n["titolo"], n["estratto"], n["canale"]) for n in notizie] == [
        ("Manovra, cosa cambia per i giovani", "Le misure spiegate.", "instagram")]
    assert "business_discovery.username(torcha)" in chiamate[0][1]["fields"]

    monkeypatch.setattr(instagram.requests, "get", lambda url, params, timeout: _Risposta(
        {"error": {"message": "Invalid user id"}}, 400))
    notizie, stato = raccolta.raccogli_fonte(fonte, config, ora)
    assert stato["esito"] == "errore" and "Invalid user id" in stato["errori"][0]

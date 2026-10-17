import socket

import dati_prova
import requests

from giornalize import raccolta


def test_tutte_le_fonti_funzionano(config, internet_finto, ora):
    notizie, stati = raccolta.raccogli_tutto(config, ora)
    assert len(notizie) == len(dati_prova.NOTIZIE)
    assert stati["ansa"]["esito"] == "ok"
    assert all(n["link"].startswith("https://") for n in notizie)
    assert all(len(n["estratto"]) <= config["estratto"]["max_caratteri"] for n in notizie)


def test_fonti_irraggiungibili_non_fermano_le_altre(config, internet_finto, ora):
    internet_finto["https://ansa.example.it/feed.xml"] = requests.ConnectionError("giù")
    internet_finto["https://corriere.example.it/feed.xml"] = requests.Timeout("lento")
    internet_finto["https://ilpost.example.it/feed.xml"] = b"<html><body>Pagina cambiata</body></html>"
    internet_finto["https://fanpage.example.it/feed.xml"] = b"\x00\x01 dati rotti"
    notizie, stati = raccolta.raccogli_tutto(config, ora)

    for rotta in ("ansa", "corriere", "ilpost", "fanpage"):
        assert stati[rotta]["esito"] == "errore", rotta
        assert stati[rotta]["errori"]
    assert stati["ansa"]["errori"][0].endswith("irraggiungibile")
    assert "tempo scaduto" in stati["corriere"]["errori"][0]
    assert stati["repubblica"]["esito"] == "ok"
    assert {n["fonte"] for n in notizie}.isdisjoint({"ansa", "corriere", "ilpost", "fanpage"})
    assert len(notizie) > 20


def test_errore_di_rete_vero(config, ora):
    """Una porta chiusa sul computer stesso: un vero errore di connessione."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        porta = s.getsockname()[1]
    fonte = config.fonti_per_id["ansa"]
    fonte.feed = [f"http://127.0.0.1:{porta}/feed.xml"]
    fonte.sito = ""
    notizie, stato = raccolta.raccogli_fonte(fonte, config, ora)
    assert notizie == [] and stato["esito"] == "errore"


def test_news_sitemap(config, ora):
    voci = dati_prova.notizie_per_fonte(ora)["ansa"]
    notizie = raccolta.leggi_sitemap(config.fonti_per_id["ansa"], dati_prova.sitemap_news(voci), config, ora, 5)
    assert len(notizie) == len(voci)
    assert notizie[0]["canale"] == "sitemap" and notizie[0]["estratto"] == ""


def test_scoperta_automatica_del_feed(config, internet_finto, ora):
    fonte = config.fonti_per_id["ilpost"]
    feed_vero = internet_finto.pop("https://ilpost.example.it/feed.xml")
    fonte.feed = []
    internet_finto["https://ilpost.example.it"] = (
        b'<html><head><link rel="alternate" type="application/rss+xml" href="/nuovo-feed/"></head></html>'
    )
    internet_finto["https://ilpost.example.it/nuovo-feed/"] = feed_vero
    notizie, stato = raccolta.raccogli_fonte(fonte, config, ora)
    assert stato["trovato_in_automatico"] == "https://ilpost.example.it/nuovo-feed/"
    assert stato["esito"] == "ok" and notizie


def test_date_nel_futuro_corrette(config, ora):
    from datetime import timedelta
    voce = {"titolo": "Notizia", "sommario": "", "link": "https://x.it/a", "quando": ora + timedelta(days=2)}
    notizie = raccolta.leggi_feed(config.fonti_per_id["ansa"], dati_prova.feed_rss([voce]), config, ora)
    assert notizie[0]["pubblicato"] == raccolta.iso(ora)

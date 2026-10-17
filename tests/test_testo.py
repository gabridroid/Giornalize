from giornalize.testo import (
    chiave_link,
    parole,
    prepara_estratto,
    pulisci_link,
    pulisci_titolo,
    togli_html,
)


def test_estratto_breve_e_senza_html():
    lungo = "<p>Primo paragrafo <b>importante</b>.</p>" + "<p>" + "parola " * 100 + "</p>"
    estratto = prepara_estratto(lungo, "Titolo", 200)
    assert len(estratto) <= 200
    assert "<" not in estratto and "importante" in estratto
    assert estratto.endswith("…")


def test_estratto_toglie_code_dei_feed_e_titolo_ripetuto():
    grezzo = "Titolo della notizia. Il testo vero. L'articolo Titolo proviene da Il Sito."
    assert prepara_estratto(grezzo, "Titolo della notizia", 200) == "Il testo vero."
    assert prepara_estratto("Titolo della notizia", "Titolo della notizia", 200) == ""


def test_estratto_senza_link():
    assert prepara_estratto("https://video.esempio.it/play/mp4/video/rx66", "Titolo", 200) == ""
    assert prepara_estratto("Guarda il video: https://t.ly/abc - Il racconto", "Titolo", 200) == "Guarda il video: - Il racconto"


def test_togli_html_e_entita():
    assert togli_html("Caf&egrave; <i>e</i>&nbsp;cornetto<script>x()</script>") == "Cafè e cornetto"


def test_titolo_senza_firma_della_testata():
    assert pulisci_titolo("Manovra approvata - Corriere.it", "Corriere della Sera") == "Manovra approvata"
    assert pulisci_titolo("Manovra approvata | Rai News", "Rai News") == "Manovra approvata"
    # una coda che non è il nome della fonte resta
    assert pulisci_titolo("Ucraina - Russia, i colloqui", "ANSA") == "Ucraina - Russia, i colloqui"


def test_link_senza_tracciamento():
    assert pulisci_link("https://www.x.it/a?utm_source=rss&id=3#commenti") == "https://www.x.it/a?id=3"
    assert chiave_link("http://www.x.it/a/") == chiave_link("https://x.it/a?utm_medium=feed")


def test_parole_significative():
    radici = [r for r, _ in parole("L'Ucraina e i migranti: il governo dice no")]
    assert "ucrain" in radici and "migrant" in radici
    assert "dice" not in radici and "il" not in radici
    assert parole("migranti")[0][0] == parole("migrante")[0][0]

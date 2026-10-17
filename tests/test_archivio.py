from datetime import timedelta

from giornalize import archivio, raccolta


def notizia(fonte, titolo, link, ora, ore_fa=1):
    return {
        "id": raccolta.id_notizia(link), "fonte": fonte, "titolo": titolo, "estratto": "",
        "link": link, "pubblicato": raccolta.iso(ora - timedelta(hours=ore_fa)),
        "raccolto": raccolta.iso(ora), "canale": "rss",
    }


def test_doppioni_tolti(ora):
    nuove = [
        notizia("ansa", "Manovra approvata dal governo", "https://www.ansa.it/a.html", ora),
        # stesso articolo da un altro feed della stessa fonte, con tracciamento
        notizia("ansa", "Manovra approvata dal governo", "https://ansa.it/a.html?utm_source=rss", ora),
        # stesso titolo ripubblicato con un altro link nella stessa fonte
        notizia("ansa", "Manovra approvata dal governo.", "https://www.ansa.it/sezione/a.html", ora),
        # titolo quasi identico nella stessa fonte
        notizia("corriere", "Manovra, approvata dal governo la legge di bilancio", "https://corriere.it/1", ora),
        notizia("corriere", "Manovra: approvata dal governo la legge di bilancio oggi", "https://corriere.it/2", ora),
        # stesso titolo ma fonte diversa: NON è un doppione
        notizia("repubblica", "Manovra approvata dal governo", "https://repubblica.it/x", ora),
    ]
    tutte, aggiunte = archivio.unisci([], nuove, ora, 7)
    assert [(n["fonte"], n["link"]) for n in tutte] == [
        ("ansa", "https://www.ansa.it/a.html"),
        ("corriere", "https://corriere.it/1"),
        ("repubblica", "https://repubblica.it/x"),
    ]
    assert aggiunte == 3


def test_aggiornamenti_ripetuti_non_creano_doppioni(ora):
    nuove = [notizia("ansa", f"Notizia numero {i} di oggi", f"https://ansa.it/{i}", ora) for i in range(5)]
    tutte, _ = archivio.unisci([], nuove, ora, 7)
    di_nuovo, aggiunte = archivio.unisci(tutte, nuove, ora + timedelta(hours=3), 7)
    assert len(di_nuovo) == 5 and aggiunte == 0


def test_notizie_vecchie_cancellate(ora):
    vecchia = notizia("ansa", "Notizia vecchia", "https://ansa.it/v", ora, ore_fa=24 * 10)
    nuova = notizia("ansa", "Notizia nuova", "https://ansa.it/n", ora)
    tutte, _ = archivio.unisci([vecchia], [nuova], ora, 7)
    assert [n["titolo"] for n in tutte] == ["Notizia nuova"]


def test_archivio_su_file(tmp_path, ora):
    percorso = tmp_path / "notizie.json"
    dati = [notizia("ansa", "Una notizia", "https://ansa.it/1", ora)]
    archivio.scrivi(percorso, dati, ora)
    assert archivio.leggi(percorso) == dati
    percorso.write_text("{ rotto", encoding="utf-8")
    assert archivio.leggi(percorso) == []  # file rovinato: si riparte senza bloccarsi

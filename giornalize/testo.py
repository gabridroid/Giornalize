"""Strumenti per ripulire e confrontare i testi delle notizie."""

from __future__ import annotations

import html
import re
import unicodedata
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# Parole italiane molto comuni che non aiutano a capire di cosa parla una
# notizia, più alcune parole tipiche dei titoli di giornale ("video", "ecco"...).
STOPWORD = set(
    """
    a ad al allo ai agli all agl alla alle con col coi da dal dallo dai dagli dall dagl dalla
    dalle di del dello dei degli dell degl della delle in nel nello nei negli nell negl nella
    nelle su sul sullo sui sugli sull sugl sulla sulle per tra fra contro verso senza sotto
    sopra dopo prima durante mentre presso oltre circa secondo dentro fuori
    il lo la i gli le un uno una l un'
    e ed o od ma però anche ancora pure né neanche nemmeno neppure se perché perche poiché
    quindi dunque infatti invece oppure ovvero cioè mentre quando come dove chi cosa che cui
    quale quali quanto quanta quanti quante
    io tu lui lei noi voi loro mi ti ci vi si ne me te se sé ce ve gli glielo
    mio mia miei mie tuo tua tuoi tue suo sua suoi sue nostro nostra nostri nostre vostro
    vostra vostri vostre loro
    questo questa questi queste quello quella quelli quelle quel quei quegli
    essere è sono era erano sarà saranno sia siano stato stata stati state sei siamo siete
    fu furono avere ha hanno aveva avevano avrà avranno abbia abbiano avuto ho hai abbiamo
    avete fa fanno fare fatto fatta fatti fatte può possono potrà deve devono dovrà va vanno
    viene vengono dice dicono detto stato
    non più piu meno molto molti molta molte poco tutto tutti tutta tutte ogni altro altra
    altri altre stesso stessa nuovo nuova nuovi nuove primo prima primi ultime ultimo ultima
    ultimi già gia mai sempre ora oggi ieri domani adesso subito poi qui qua lì là così cosi
    tanto troppo solo soltanto proprio forse ecco ecc
    anni anno giorni giorno ore ora mese mesi settimana volta volte
    video foto live diretta news notizie notizia aggiornamenti ultim'ora ultimora intervista
    esclusiva speciale podcast newsletter commento editoriale analisi leggi guarda
    dice spiega annuncia arriva parla chiede
    """.split()
)

_PAROLA = re.compile(r"[^\W\d_]+(?:'[^\W\d_]+)?", re.UNICODE)
_SPAZI = re.compile(r"\s+")

# Parametri dei link che servono solo a tracciare le visite: si tolgono.
_PARAMETRI_TRACCIAMENTO = re.compile(
    r"^(utm_.*|fbclid|gclid|mc_cid|mc_eid|ref|refresh_ce|cmpid|xtor|ito|wt_mc|ns_.*|at_.*|rss)$",
    re.IGNORECASE,
)

# Frasi aggiunte in coda ai feed (WordPress e simili) che non fanno parte del testo.
_CODE_FEED = re.compile(
    r"(L['’]articolo .{0,200}? proviene da .*|The post .{0,200}? appeared first on .*|"
    r"Continua a leggere.*|Leggi (tutto|l['’]articolo).*|\[\s*(…|\.\.\.)\s*\])$",
    re.IGNORECASE | re.DOTALL,
)


class _SoloTesto(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.pezzi: list[str] = []
        self._salta = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "figcaption"):
            self._salta += 1
        elif tag in ("p", "br", "div", "li"):
            self.pezzi.append(" ")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "figcaption") and self._salta:
            self._salta -= 1

    def handle_data(self, data):
        if not self._salta:
            self.pezzi.append(data)


def togli_html(testo: str) -> str:
    """Trasforma un frammento HTML in testo semplice su una riga."""
    if not testo:
        return ""
    if "<" in testo:
        lettore = _SoloTesto()
        try:
            lettore.feed(testo)
            lettore.close()
            testo = "".join(lettore.pezzi)
        except Exception:
            testo = re.sub(r"<[^>]+>", " ", testo)
    testo = html.unescape(testo).replace(" ", " ")
    return _SPAZI.sub(" ", testo).strip()


def taglia(testo: str, massimo: int) -> str:
    """Accorcia un testo a `massimo` caratteri senza spezzare le parole."""
    if len(testo) <= massimo:
        return testo
    tagliato = testo[: massimo - 1]
    if " " in tagliato[massimo // 2 :]:
        tagliato = tagliato[: tagliato.rfind(" ")]
    return tagliato.rstrip(" ,;:.-–—") + "…"


def prepara_estratto(grezzo: str, titolo: str, massimo: int) -> str:
    """Estratto breve dal sommario del feed: senza HTML, senza code, senza
    ripetere il titolo, al massimo `massimo` caratteri."""
    testo = togli_html(grezzo)
    testo = _CODE_FEED.sub("", testo).strip()
    if titolo and testo.lower().startswith(titolo.lower()):
        testo = testo[len(titolo) :].lstrip(" .:-–—")
    if normalizza_titolo(testo) == normalizza_titolo(titolo):
        return ""
    return taglia(testo, massimo)


def normalizza_titolo(titolo: str) -> str:
    """Versione "semplificata" di un titolo, per riconoscere i doppioni."""
    t = unicodedata.normalize("NFKD", titolo.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^\w\s]", " ", t)
    return _SPAZI.sub(" ", t).strip()


def pulisci_titolo(titolo: str, nome_fonte: str = "") -> str:
    """Toglie HTML e la firma della testata in coda (es. "... - Corriere.it")."""
    t = togli_html(titolo)
    if nome_fonte:
        m = re.search(r"\s+[-–—|]\s+([^-–—|]{2,40})$", t)
        if m:
            coda = normalizza_titolo(m.group(1)).replace(" ", "")
            nome = normalizza_titolo(nome_fonte)
            parola_lunga = max(nome.split(), key=len, default="")
            if nome.replace(" ", "") in coda or (len(parola_lunga) >= 4 and parola_lunga in coda):
                t = t[: m.start()].strip()
    return t


def pulisci_link(link: str) -> str:
    """Toglie dal link i parametri di tracciamento e il frammento (#...)."""
    link = (link or "").strip()
    try:
        parti = urlsplit(link)
    except ValueError:
        return link
    if parti.scheme not in ("http", "https") or not parti.netloc:
        return link
    query = [
        (k, v)
        for k, v in parse_qsl(parti.query, keep_blank_values=True)
        if not _PARAMETRI_TRACCIAMENTO.match(k)
    ]
    return urlunsplit((parti.scheme, parti.netloc, parti.path, urlencode(query), ""))


def chiave_link(link: str) -> str:
    """Forma del link usata per riconoscere due link uguali scritti in modo diverso."""
    parti = urlsplit(pulisci_link(link))
    host = parti.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    if host.startswith("amp."):
        host = host[4:]
    percorso = parti.path.rstrip("/")
    if percorso.endswith("/amp"):
        percorso = percorso[:-4]
    return f"{host}{percorso}" + (f"?{parti.query}" if parti.query else "")


def radice(parola: str) -> str:
    """Riduzione molto semplice delle parole alla loro "radice", così
    "migranti" e "migrante", "governo" e "governi" vengono considerate uguali."""
    if len(parola) > 4 and parola[-1] in "aeiouàèéìòù":
        parola = parola[:-1]
        if parola.endswith(("ch", "gh")):  # banche/banca, luoghi/luogo
            parola = parola[:-1]
    return parola


def parole(testo: str) -> list[tuple[str, str]]:
    """Restituisce le parole significative come coppie (radice, forma originale)."""
    risultato = []
    for m in _PAROLA.finditer(testo.replace("’", "'")):
        originale = m.group(0)
        if "'" in originale:  # l'Ucraina -> Ucraina, dell'Europa -> Europa
            prefisso, _, resto = originale.partition("'")
            if len(prefisso) <= 5:
                originale = resto
        minuscola = originale.lower()
        if len(minuscola) < 3 or minuscola in STOPWORD:
            continue
        risultato.append((radice(minuscola), originale))
    return risultato

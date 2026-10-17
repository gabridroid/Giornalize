"""Notizie INVENTATE usate solo per le prove automatiche.

Titoli e testi sono scritti a mano per assomigliare a quelli veri (stessi
argomenti raccontati da fonti diverse con parole diverse), ma non sono
notizie reali e non vengono mai pubblicate.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from xml.sax.saxutils import escape

# (id fonte, ore fa, titolo, sommario, argomento atteso)
# L'argomento atteso serve solo alle prove: None = notizia isolata.
NOTIZIE = [
    # A — legge di bilancio
    ("ansa", 3, "Manovra, il governo approva il testo: stretta sulle pensioni anticipate e taglio del cuneo fiscale",
     "Il Consiglio dei ministri ha approvato la legge di bilancio da 18 miliardi. Quota 103 non sarà rinnovata.", "manovra"),
    ("corriere", 2, "Legge di bilancio, cosa cambia per pensioni e buste paga: le misure della manovra",
     "Dal taglio del cuneo fiscale alle pensioni anticipate: tutte le novità della manovra approvata ieri sera.", "manovra"),
    ("repubblica", 2.5, "Manovra, addio a Quota 103: i sindacati annunciano la mobilitazione contro la stretta sulle pensioni",
     "Cgil e Uil contro la legge di bilancio: «Si fa cassa sulle pensioni».", "manovra"),
    ("ilgiornale", 4, "Manovra, conti in ordine e più soldi in busta paga: il taglio del cuneo fiscale diventa strutturale",
     "Il governo rivendica la legge di bilancio: 18 miliardi, priorità a famiglie e lavoratori.", "manovra"),
    ("ilfatto", 1, "Manovra, la stretta sulle pensioni anticipate pesa sui lavoratori precoci",
     "Nella legge di bilancio sparisce Quota 103 e si allungano le finestre di uscita.", "manovra"),
    ("ilpost", 1, "Cosa c'è nella legge di bilancio approvata dal governo",
     "Pensioni, cuneo fiscale e sanità: le principali misure della manovra da 18 miliardi.", "manovra"),
    ("pagellapolitica", 5, "Quanto vale davvero il taglio del cuneo fiscale nella manovra",
     "Abbiamo verificato i numeri della legge di bilancio sul cuneo fiscale e sulle buste paga.", "manovra"),

    # B — sciopero dei trasporti
    ("ansa", 6, "Sciopero nazionale dei trasporti venerdì: treni e bus a rischio, le fasce di garanzia",
     "Stop di 24 ore per treni, metro e autobus. Garantiti i servizi dalle 6 alle 9 e dalle 18 alle 21.", "sciopero"),
    ("rainews", 5, "Venerdì sciopero dei trasporti di 24 ore: stop a treni, metro e bus. Gli orari garantiti",
     "Lo sciopero generale dei trasporti riguarda ferrovie e trasporto pubblico locale.", "sciopero"),
    ("fanpage", 4, "Sciopero treni e mezzi pubblici venerdì 24 ottobre: orari e fasce garantite",
     "Tutte le informazioni sullo sciopero dei trasporti: treni, metro, bus e tram.", "sciopero"),
    ("open", 2, "Sciopero dei trasporti di venerdì, il governo valuta la precettazione. I sindacati: «Diritto costituzionale»",
     "Treni e bus fermi per 24 ore, si va verso lo scontro tra ministero e sindacati.", "sciopero"),

    # C — maltempo
    ("ansa", 8, "Maltempo, allerta rossa in Emilia-Romagna: scuole chiuse a Bologna e Ravenna",
     "La protezione civile ha diramato l'allerta rossa per piene dei fiumi.", "maltempo"),
    ("corriere", 7, "Allerta rossa per maltempo in Emilia-Romagna, chiuse le scuole a Bologna. Fiumi sorvegliati speciali",
     "Piogge intense attese nelle prossime ore, l'allerta rossa resta fino a domani.", "maltempo"),
    ("lastampa", 6, "Maltempo, l'Emilia-Romagna di nuovo in allerta rossa: evacuazioni preventive nel Ravennate",
     "Le piogge mettono sotto pressione gli argini, scuole chiuse in diversi comuni.", "maltempo"),
    ("fanpage", 5, "Allerta meteo rossa in Emilia-Romagna, scuole chiuse a Bologna e Ravenna: l'elenco dei comuni",
     "L'allerta rossa della protezione civile riguarda le province di Bologna, Ravenna e Forlì-Cesena.", "maltempo"),
    ("avvenire", 6, "Emilia-Romagna, l'allerta rossa riapre la ferita dell'alluvione: opere di prevenzione ancora ferme",
     "Nelle zone colpite dall'alluvione i cantieri sugli argini non sono finiti.", "maltempo"),

    # D — Gaza
    ("ansa", 10, "Gaza, colloqui al Cairo per la tregua: la nuova proposta sul tavolo",
     "Delegazioni al lavoro al Cairo per un cessate il fuoco a Gaza.", "gaza"),
    ("repubblica", 9, "Gaza, al Cairo si tratta sulla tregua. Ma i raid continuano: decine di vittime",
     "Mentre al Cairo si negozia, a Gaza proseguono i bombardamenti.", "gaza"),
    ("manifesto", 12, "Gaza, si muore anche durante le trattative al Cairo per la tregua",
     "I negoziati del Cairo non fermano i raid sulla Striscia.", "gaza"),
    ("avvenire", 11, "Gaza, la tregua appesa ai colloqui del Cairo",
     "Le chiese locali chiedono di fermare i bombardamenti mentre si tratta al Cairo.", "gaza"),
    ("internazionale", 14, "Cosa sappiamo dei negoziati al Cairo per una tregua a Gaza",
     "Le posizioni delle parti e i punti ancora aperti del negoziato.", "gaza"),

    # E — inchiesta (poco coperta dai grandi giornali)
    ("irpimedia", 20, "Appalti del PNRR, la rete di società che ha vinto le gare per gli asili nido in Calabria",
     "Un'inchiesta ricostruisce come un gruppo di imprese collegate si sia aggiudicato decine di appalti per gli asili nido.", "asili"),
    ("valigiablu", 15, "Asili nido del PNRR in Calabria: cosa racconta l'inchiesta sugli appalti",
     "Le gare per gli asili nido finanziati dal PNRR e le società collegate tra loro.", "asili"),
    ("fanpage", 12, "Appalti PNRR per gli asili nido in Calabria, le società collegate che hanno vinto le gare",
     "Decine di appalti per costruire asili nido finiti a imprese legate tra loro.", "asili"),
    ("ilfatto", 10, "Asili nido PNRR, inchiesta sulle gare in Calabria: decine di appalti alle stesse società",
     "Il caso degli asili nido in Calabria finanziati con i fondi europei.", "asili"),

    # F — verifica di un dato (poco coperta)
    ("pagellapolitica", 18, "Il dato sugli sbarchi del 2026 citato nel dibattito tv non torna",
     "Secondo i numeri del Viminale gli sbarchi non sono calati del 60 per cento.", "sbarchi"),
    ("facta", 16, "Sbarchi 2026, il presunto calo del 60 per cento diffuso sui social è fuorviante",
     "Il confronto tra i dati sugli sbarchi del Viminale e quelli circolati online.", "sbarchi"),
    ("open", 14, "Il presunto calo del 60 per cento degli sbarchi nel 2026: cosa dicono davvero i dati del Viminale",
     "Abbiamo confrontato i numeri ufficiali sugli sbarchi.", "sbarchi"),

    # G — studenti e caro affitti (poco coperta)
    ("scomodo", 22, "Le tende degli studenti tornano davanti alle università: il caro affitti a Milano e Bologna",
     "Studenti in tenda contro il caro affitti, dopo due anni la protesta riparte.", "affitti"),
    ("fanpage", 20, "Caro affitti, gli studenti tornano in tenda davanti al Politecnico di Milano",
     "La protesta delle tende contro il caro affitti degli alloggi per studenti.", "affitti"),
    ("ilpost", 19, "Gli studenti sono tornati a protestare in tenda contro il caro affitti",
     "A Milano e Bologna, davanti alle università.", "affitti"),
    ("repubblica", 18, "Caro affitti, tende degli studenti davanti alle università di Milano e Bologna",
     "Riparte la protesta degli studenti fuorisede contro il caro affitti.", "affitti"),

    # H — servizio pubblico e regole europee
    ("domani", 9, "Rai, la riforma della governance resta ferma: l'Europa richiama l'Italia sul Media Freedom Act",
     "Il regolamento europeo sulla libertà dei media chiede garanzie di indipendenza per la Rai.", "rai"),
    ("valigiablu", 8, "Media Freedom Act, perché la riforma della Rai è in ritardo e cosa rischia l'Italia",
     "Le scadenze del regolamento europeo e la governance della Rai.", "rai"),
    ("linkiesta", 7, "Il Media Freedom Act europeo e la Rai: la riforma della governance che non arriva",
     "Bruxelles chiede indipendenza per il servizio pubblico.", "rai"),

    # Notizie isolate, alcune con parole in comune con gli argomenti sopra
    # (per controllare che non vengano mescolate)
    ("rainews", 3, "Sciopero dei medici il 20 novembre contro i tagli alla sanità",
     "I sindacati dei medici ospedalieri annunciano la mobilitazione nazionale.", None),
    ("corriere", 5, "Bologna, inaugurato il nuovo tram: le prime corse in città",
     "La linea rossa collega la stazione all'ospedale Maggiore.", None),
    ("sole24ore", 6, "Pensioni, l'Inps pubblica i dati sugli assegni di settembre",
     "Il numero dei nuovi pensionati è in calo rispetto all'anno scorso.", None),
    ("ansa", 13, "Calabria, sequestrati beni per 20 milioni a un clan della 'ndrangheta",
     "L'operazione della Direzione investigativa antimafia a Reggio Calabria.", None),
    ("fanpage", 16, "Milano, migliaia di studenti in piazza per il clima",
     "Il corteo dei Fridays for Future ha attraversato il centro.", None),
    ("ansa", 1, "Incidente sulla A1 vicino a Firenze, code di otto chilometri",
     "Coinvolti tre mezzi pesanti, nessun ferito grave.", None),
    ("nicolaporro", 6, "La zuppa di oggi: la rassegna stampa del mattino",
     "I titoli dei quotidiani commentati.", None),
    ("breakingitaly", 12, "Le notizie della settimana spiegate in mezz'ora",
     "", None),
    ("ilgiornale", 7, "Sicurezza, più agenti nelle stazioni delle grandi città",
     "Il piano prevede pattuglie fisse negli scali ferroviari.", None),
    ("libero", 9, "Ztl, la protesta dei commercianti del centro di Roma",
     "Negozianti contro i nuovi orari della zona a traffico limitato.", None),
    ("corriere", 3, "Nobel per l'economia, chi sono i vincitori di quest'anno",
     "Premiati tre studiosi per le ricerche sulle istituzioni.", None),
    ("lastampa", 4, "Torino, nuova linea della metropolitana: aperto il cantiere",
     "I lavori dureranno cinque anni.", None),
    ("rainews", 2, "Calcio, la Nazionale convoca tre esordienti per le qualificazioni",
     "Il commissario tecnico punta sui giovani.", None),
    ("avvenire", 15, "Povertà educativa, il rapporto: un minore su sette senza servizi",
     "I dati del nuovo rapporto sulla povertà educativa in Italia.", None),
]


def link(fonte: str, titolo: str) -> str:
    pezzo = "-".join(titolo.lower().split()[:6])
    pezzo = "".join(c for c in pezzo if c.isalnum() or c == "-")
    return f"https://{fonte}.example.it/articolo/{pezzo}"


def notizie_per_fonte(ora: datetime) -> dict[str, list[dict]]:
    per_fonte: dict[str, list[dict]] = {}
    for fonte, ore, titolo, sommario, argomento in NOTIZIE:
        per_fonte.setdefault(fonte, []).append({
            "titolo": titolo,
            "sommario": sommario,
            "link": link(fonte, titolo),
            "quando": ora - timedelta(hours=ore),
            "argomento": argomento,
        })
    return per_fonte


def feed_rss(voci: list[dict], nome: str = "Fonte di prova") -> bytes:
    elementi = "".join(
        f"""
    <item>
      <title>{escape(v['titolo'])}</title>
      <link>{escape(v['link'])}</link>
      <description>{escape(v['sommario'])}</description>
      <pubDate>{format_datetime(v['quando'].astimezone(timezone.utc))}</pubDate>
    </item>"""
        for v in voci
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>{escape(nome)}</title><link>https://example.it</link>
<description>prova</description>{elementi}
</channel></rss>""".encode("utf-8")


def sitemap_news(voci: list[dict]) -> bytes:
    elementi = "".join(
        f"""
  <url><loc>{escape(v['link'])}</loc>
    <news:news><news:publication><news:name>Prova</news:name><news:language>it</news:language></news:publication>
      <news:publication_date>{v['quando'].astimezone(timezone.utc).isoformat()}</news:publication_date>
      <news:title>{escape(v['titolo'])}</news:title></news:news></url>"""
        for v in voci
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">{elementi}
</urlset>""".encode("utf-8")

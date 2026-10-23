# Giornalize

> *Le notizie sono tante. Ma chi decide quali arrivano a te?*

Giornalize raccoglie in automatico le notizie di giornali, testate indipendenti e
pagine di divulgazione, riconosce quando parlano della stessa storia e mette i loro titoli
uno sotto l'altro. Così chi legge vede chi ne parla e **come** la racconta. Ogni titolo porta
sempre all'articolo originale.

Le pagine del sito:
- **Oggi** (la home): le 10 storie più raccontate delle ultime 24 ore, con la barra «chi ne
  parla» per area politica, 4 titoli a confronto scelti perché diversi e i **filoni** della
  storia (i suoi diversi aspetti, ognuno con le sue fonti e la sua barra);
- **Fuori dai radar**: storie raccontate da fonti indipendenti e poco presenti nei feed dei
  grandi giornali;
- **Tutte**: tutto quello che è stato raccolto nelle ultime 48 ore, con i filtri;
- **Temi**: argomenti scelti da te (file `temi.yaml`), seguiti giorno per giorno: chi ne ha
  scritto e chi no;
- **Fonti** e **Metodo** (come funziona); in fondo alla pagina, **Perché esiste questo sito**.

Questa guida spiega come mettere online il sito, come aggiungere o togliere una fonte, come
cambiare le impostazioni e cosa fare se qualcosa non va. Non serve saper programmare: quasi
tutto si fa modificando tre file di testo direttamente dal sito di GitHub.

---

## Indice

1. [Come funziona, in breve](#1-come-funziona-in-breve)
2. [I file del progetto](#2-i-file-del-progetto)
3. [Mettere il sito online (la prima volta)](#3-mettere-il-sito-online-la-prima-volta)
4. [Aggiungere, togliere o correggere una fonte](#4-aggiungere-togliere-o-correggere-una-fonte)
5. [Instagram: aggiungere i post](#5-instagram-aggiungere-i-post)
6. [Temi da seguire](#6-temi-da-seguire)
7. [Cambiare le impostazioni e le soglie](#7-cambiare-le-impostazioni-e-le-soglie)
8. [Scrivere la pagina "Perché esiste questo sito"](#8-scrivere-la-pagina-perché-esiste-questo-sito)
9. [Aggiornare il sito](#9-aggiornare-il-sito)
10. [Controllare gli errori](#10-controllare-gli-errori)
11. [Costi e limiti](#11-costi-e-limiti)
12. [Per chi vuole provarlo sul proprio computer](#12-per-chi-vuole-provarlo-sul-proprio-computer)

---

## 1. Come funziona, in breve

```
 sources.yaml          GitHub (ogni 3 ore, gratis)                      Sito pubblico
 (le fonti)     ──►   1. legge i feed RSS di tutte le fonti     ──►   https://NOME.github.io/giornalize/
 config.yaml           2. toglie i doppioni
 (le soglie)           3. toglie sport e spettacolo
                       4. raggruppa le notizie in storie
                       5. costruisce le pagine del sito
                       6. le pubblica su GitHub Pages
```

- **Feed RSS**: quasi ogni giornale pubblica un elenco aggiornato dei propri articoli, pensato
  apposta per essere letto da programmi. È il modo lecito e "ufficiale" di raccogliere titoli.
- Se un sito non ha un feed, si può usare la sua **news sitemap**: l'elenco degli articoli che
  i giornali preparano per Google News.
- Dal feed prendiamo solo **titolo, un estratto di massimo 200 caratteri, data e link**. Niente
  testo completo, niente immagini.
- Se una fonte non risponde, il programma va avanti con le altre e annota l'errore.

## 2. I file del progetto

| File o cartella | A cosa serve | Lo modifichi tu? |
|---|---|---|
| `sources.yaml` | L'elenco delle fonti | **Sì** |
| `config.yaml` | Impostazioni: soglie, finestre di tempo, nomi delle categorie | **Sì**, ogni tanto |
| `temi.yaml` | I temi da seguire, con le parole da cercare | **Sì** |
| `contenuti/perche-esiste.md` | Il testo della pagina "Perché esiste questo sito" | **Sì** |
| `contenuti/post_instagram.yaml` | I post aggiunti a mano (anche con il modulo "Aggiungi un post") | **Sì**, o con il modulo |
| `data/` | Le notizie raccolte (`notizie.json`, ultimi 3 giorni), lo storico per i temi (`storico/`, un file al giorno, ultimi 30 giorni) e il registro degli errori. Si aggiorna da solo | No |
| `templates/` | L'aspetto delle pagine (HTML) | Solo per cambiare testi fissi |
| `static/` | Colori e stile (`stile.css`), filtri (`filtri.js`), orari tipo "2 ore fa" (`tempo.js`) | Raramente |
| `giornalize/` | Il programma in Python | No |
| `tests/` | Le prove automatiche del programma | No |
| `.github/workflows/` | Le istruzioni per GitHub (aggiornamento ogni 3 ore, modulo dei post) | Solo per cambiare la frequenza |
| `.github/ISSUE_TEMPLATE/` | Il modulo "Aggiungi un post" | No |

## 3. Mettere il sito online (la prima volta)

Tutto quello che segue è **gratuito**.

### 3.1 Creare l'account GitHub

1. Vai su <https://github.com/signup> e crea un account (email, password, nome utente).
   Il **nome utente** comparirà nell'indirizzo del sito: `https://NOMEUTENTE.github.io/giornalize/`.
2. Conferma l'indirizzo email.

### 3.2 Creare il "repository" (la cartella del progetto su GitHub)

1. In alto a destra clicca **+** → **New repository**.
2. **Repository name**: `giornalize`.
3. Scegli **Public**: GitHub Pages è gratuito solo per i progetti pubblici. Chiunque potrà vedere
   il codice e l'elenco delle fonti, ed è coerente con la trasparenza del sito.
4. **Non** spuntare "Add a README" (il progetto ne ha già uno). Clicca **Create repository**.

### 3.3 Caricare i file del progetto

**Strada consigliata:** chiedi a Claude Code di farlo. Apri una sessione di Claude Code collegata
al nuovo repository (su claude.ai/code, scegliendo il repository `giornalize`) e chiedi di
caricare il progetto. Se la sessione in cui è stato creato il progetto non è più disponibile,
allega lo zip del progetto alla nuova sessione.

**Strada manuale (senza Claude):** nella pagina del repository vuoto clicca
**uploading an existing file**. Trascina **il contenuto** della cartella `giornalize`, non la
cartella stessa. Poi clicca **Commit changes**.
Attenzione: la cartella `.github` è "nascosta" (il nome inizia con un punto) e su Mac e Windows
potrebbe non essere trascinata. Controlla che dopo il caricamento esista
`.github/workflows/aggiorna.yml`. Se manca, crealo così:
**Add file → Create new file**, scrivi come nome `.github/workflows/aggiorna.yml`, incolla il
contenuto del file e clicca **Commit changes**. Fai lo stesso per `prova-fonti.yml`.

### 3.4 Attivare GitHub Pages (la pubblicazione del sito)

1. Nel repository: **Settings** → nel menu a sinistra **Pages**.
2. In **Build and deployment** → **Source**, scegli **GitHub Actions**.

### 3.5 Primo aggiornamento

1. Apri la scheda **Actions** del repository. Se GitHub chiede di abilitare i workflow, conferma.
2. Clicca **Aggiorna Giornalize** nella colonna di sinistra, poi **Run workflow** → **Run workflow**.
3. Dopo 1–3 minuti compare un pallino verde. Il sito è online all'indirizzo
   `https://NOMEUTENTE.github.io/giornalize/`, che trovi anche in Settings → Pages.

Da quel momento il sito si aggiorna da solo ogni 3 ore.

### 3.6 Provare le fonti (consigliato dopo il primo avvio)

Gli indirizzi dei feed sono stati provati al primo avvio. Conviene ripetere la prova ogni volta
che aggiungi o correggi una fonte:

1. **Actions** → **Prova le fonti** → **Run workflow** → **Run workflow**.
2. Quando finisce, clicca sull'esecuzione: in fondo alla pagina c'è una tabella con ogni fonte,
   l'esito (✅ funziona, ⚠️ in parte, ❌ non funziona) e un esempio di titolo.
3. Se per una fonte c'è scritto *"trovato in automatico: …"*, copia quell'indirizzo in
   `sources.yaml` al posto di quello che non funziona (vedi il capitolo 4).

### 3.7 (Facoltativo) Un indirizzo tutto tuo

Puoi comprare un dominio (es. `giornalize.it`, circa 10–15 € l'anno) e collegarlo in
Settings → Pages → **Custom domain**. Non è necessario.

## 4. Aggiungere, togliere o correggere una fonte

Si fa tutto nel file `sources.yaml`, anche direttamente dal sito di GitHub:

1. Apri il repository su GitHub e clicca su `sources.yaml`.
2. Clicca sull'icona della **matita** (Edit) in alto a destra del file.
3. Fai la modifica (vedi sotto).
4. Clicca **Commit changes…** e poi di nuovo **Commit changes**.
5. In un paio di minuti il sito si ricostruisce da solo. Se c'è un errore di scrittura nel
   file, l'aggiornamento si ferma, il sito resta com'era e GitHub ti manda un'email: apri
   l'esecuzione nella scheda Actions, dove trovi la spiegazione in italiano dell'errore.

### Aggiungere una fonte

Copia un blocco esistente, incollalo in fondo e cambia i valori. Esempio:

```yaml
  - id: nuovafonte                  # nome breve, minuscolo, senza spazi né accenti, unico
    nome: Nuova Fonte               # come apparirà sul sito
    categoria: Testate online e settimanali
    tipo: Testata online
    orientamento: Progressista      # descrizione libera e indicativa della linea editoriale
    area: centro-sinistra           # posizione indicativa sull'asse sinistra-destra
    sito: https://www.nuovafonte.it
    instagram: "@nuovafonte"
    feed:
      - https://www.nuovafonte.it/feed/
    attiva: true
```

Regole importanti:
- **Gli spazi contano.** Ogni riga del blocco ha gli stessi spazi iniziali delle altre fonti
  (2 spazi prima del trattino, 4 prima degli altri campi). Non usare il tasto Tab.
- La **categoria** deve essere scritta esattamente come una di queste: `Agenzie e all-news`,
  `Quotidiani nazionali`, `Quotidiani locali`, `Testate online e settimanali`,
  `Inchiesta e fact-checking`, `Divulgatori social`. I quotidiani locali contano nelle storie e
  nei temi, ma non per "Fuori dai radar" (né come grandi giornali né come fonti indipendenti).
- L'**area** deve essere una di queste: `sinistra`, `centro-sinistra`, `centro`, `centro-destra`,
  `destra`, `non collocabile`. Regola usata finora: l'area si ricava dalla descrizione in
  `orientamento`; se la descrizione non parla di sinistra o destra (per esempio "Cattolico",
  "Economico", "Non schierato") la fonte è `non collocabile`. Se manca, vale `non collocabile`.
- Gli account Instagram vanno tra virgolette (`"@nome"`), perché la @ confonde il formato YAML.

**Come trovare il feed RSS di un sito:**
- prova ad aggiungere `/feed/` o `/rss` all'indirizzo del sito (es. `https://www.sito.it/feed/`):
  se si apre una pagina piena di testo tipo codice, con i titoli degli articoli, è il feed;
- oppure lascia `feed: []` e indica il `sito`: il programma prova a trovare il feed da solo e
  scrive nel rapporto quale indirizzo ha usato;
- per un canale YouTube: `https://www.youtube.com/feeds/videos.xml?channel_id=ID_DEL_CANALE`.
- Se il sito non ha un feed ma ha una news sitemap, usa `sitemap:` al posto di `feed:`.

### Togliere una fonte

- **Sospenderla** (consigliato): cambia `attiva: true` in `attiva: false`. Le sue notizie
  spariscono dal sito ma la fonte resta nel file, pronta per essere riattivata.
- **Cancellarla**: elimina tutto il suo blocco, dal `- id:` fino alla riga prima della fonte successiva.

### Correggere un feed che non funziona

Nella pagina **Fonti** del sito, accanto a ogni fonte, c'è scritto se la raccolta funziona.
Se una fonte risulta "Non raggiungibile" per giorni, il suo indirizzo è probabilmente cambiato:
cerca il nuovo feed (vedi sopra), sostituiscilo in `sources.yaml` e lancia **Prova le fonti**.

## 5. Instagram: aggiungere i post

Instagram non offre un feed RSS: per le pagine che pubblicano solo lì ci sono due strade, che
possono convivere.

### 5.1 Aggiungere un post a mano (funziona già)

**Dal telefono o dal computer, con il modulo:**

1. Apri il repository su GitHub → scheda **Issues** → **New issue** → **Aggiungi un post**.
2. Compila: link al post, fonte (es. `Factanza` o `@factanza`), titolo, un breve riassunto
   scritto da te e, se vuoi, data e ora del post. Se le lasci vuote si usa l'ora attuale.
3. Premi **Create**. Entro un paio di minuti compare un commento:
   - ✅ il post è stato aggiunto, la issue si chiude da sola e il sito si aggiorna;
   - ❌ c'è qualcosa da correggere (per esempio una fonte che non esiste): modifica la issue
     e il controllo riparte da solo.

Il modulo funziona solo se la issue la apri tu, proprietario del progetto: le issue aperte da
altre persone vengono ignorate.

**Oppure direttamente nel file** `contenuti/post_instagram.yaml`, con la matita, seguendo
l'esempio scritto in cima al file.

Sul sito il riassunto compare come «Riassunto di Giornalize», per distinguerlo dal testo
della fonte. Il post resta visibile per le ore indicate in `tutte.finestra_ore` (48), a partire
dalla sua data. Per toglierlo, cancellalo dal file.

La fonte deve già esistere in `sources.yaml`. Per una pagina nuova aggiungila prima lì
(capitolo 4), anche senza feed (`feed: []`).

### 5.2 API ufficiale di Instagram (facoltativa, da attivare)

Con l'API ufficiale di Meta (funzione "Business Discovery") il programma legge da solo gli
ultimi post pubblici delle pagine con `instagram_api: true` in `sources.yaml`. Funziona solo per
gli account **professionali** (Business o Creator), che sono la quasi totalità delle pagine di
divulgazione.

È **gratuita**, ma richiede alcuni account:
- un tuo account Instagram **professionale** (si cambia gratis dalle impostazioni dell'app);
- una **Pagina Facebook** collegata a quell'account;
- un account sviluppatore Meta e una "app" su <https://developers.facebook.com>.

Alla fine si ottengono due codici da inserire su GitHub in **Settings → Secrets and variables →
Actions → New repository secret**:
- `INSTAGRAM_TOKEN`: il codice di accesso;
- `INSTAGRAM_ACCOUNT_ID`: il numero che identifica il tuo account Instagram professionale.

Finché questi due segreti non ci sono, l'API resta spenta e tutto il resto funziona normalmente.

### 5.3 Rinnovare il codice di Instagram

Il codice della Pagina non scade, ma Meta chiede di riconfermare l'accesso ai dati **circa ogni
90 giorni**. Quando serve te ne accorgi così:
- nella pagina **Fonti** del sito, le pagine Instagram risultano "Non raggiungibili";
- nel file `data/registro.log` compare: «ATTENZIONE: il codice di Instagram è scaduto».

Per rinnovarlo (circa 5 minuti, dal computer):

1. Apri <https://developers.facebook.com/tools/explorer>, scegli l'app **Giornalize** e clicca
   **Generate Access Token** (permessi: `instagram_basic`, `instagram_manage_insights`,
   `pages_show_list`, `pages_read_engagement`). Conferma nella finestra di Facebook.
2. Clicca la "i" accanto al codice → **Open in Access Token Tool** → in fondo **Estendi token
   d'accesso**. Copia il nuovo codice.
3. Torna nell'Explorer, incolla il codice nel campo **Access Token**, scrivi nella barra delle
   richieste `me/accounts?fields=name,access_token,instagram_business_account` e premi **Submit**.
4. Copia il valore di `access_token` della Pagina Giornalize. Controlla su
   <https://developers.facebook.com/tools/debug/accesstoken> che la scadenza sia **Mai**.
5. Su GitHub: **Settings → Secrets and variables → Actions** → `INSTAGRAM_TOKEN` → **Update**
   (la matita) → incolla il nuovo codice → **Update secret**.

Il numero `INSTAGRAM_ACCOUNT_ID` non cambia.

## 6. Temi da seguire

I temi si scrivono nel file `temi.yaml` (matita → Commit changes, come per le fonti). Ogni tema
ha un **nome** e le parole da **cercare** nei titoli e negli estratti:

```yaml
  - nome: Denunce e multe ai manifestanti
    cerca: "denunciati, identificati, multe, sanzioni, foglio di via + tir, agricoltori, carovita"
```

- la **virgola** vuol dire "oppure": basta una delle parole;
- il **+** vuol dire "e anche": serve almeno una parola di ogni gruppo. L'esempio trova
  «Tir, 40 camionisti denunciati» ma non «Multe agli automobilisti»;
- singolare e plurale, maschile e femminile vanno bene da soli ("multa" trova anche "multe");
- l'**asterisco** trova tutte le parole che iniziano così: `denunc*` trova denuncia, denunce,
  denunciati, ma anche "denunciano" (attenzione a non allargare troppo);
- maiuscole e accenti non contano;
- `attivo: false` nasconde un tema senza cancellarlo.

La pagina **Temi** mostra per ogni tema: quante notizie e di quali fonti, una colonnina per ogni
giorno, chi ne ha scritto e chi no, una tabella fonte per fonte e giorno per giorno (ultimi 14
giorni) e l'elenco degli articoli giorno per giorno.

I temi guardano indietro fino a 30 giorni, grazie allo **storico** (`data/storico/`, un file al
giorno). Lo storico è partito il 23 ottobre 2026 con le notizie dei giorni precedenti ancora in
archivio: nelle prime settimane i temi coprono quindi meno di 30 giorni (la pagina dice sempre
quanti). Lo storico occupa circa 20 MB nel progetto su GitHub: è gratuito e i giorni più vecchi
di 30 si cancellano da soli.

**Per controllare a mano** quello che il sito non vede (articoli fuori dai feed): cerca le stesse
parole su Google News con il filtro "Ultima settimana", e aggiungi il nome di un giornale locale
per vedere se ne ha scritto.

## 7. Cambiare le impostazioni e le soglie

Apri `config.yaml` e modifica i numeri come per `sources.yaml`. I più utili:

| Impostazione | Cosa fa | Valore iniziale |
|---|---|---|
| `oggi.finestra_ore` | Quante ore indietro guarda la pagina "Oggi" | 24 |
| `oggi.max_storie` | Quante storie al massimo nella pagina "Oggi" | 10 |
| `oggi.min_fonti` | Quante fonti diverse servono perché una storia vada in "Oggi" | 3 |
| `oggi.titoli_a_confronto` | Quanti titoli mostrare uno sotto l'altro in ogni storia | 4 |
| `oggi.titolo_preferito_da` | Da quali categorie prendere per primo il titolo della storia | Agenzie e all-news |
| `oggi.max_filoni` | Quanti filoni al massimo mostrare sotto ogni storia | 6 |
| `temi.giorni` | Quanti giorni indietro guarda la pagina "Temi" | 30 |
| `temi.giorni_tabella` | Quanti giorni mostra la tabella "fonte per fonte, giorno per giorno" | 14 |
| `raccolta.giorni_storico` | Per quanti giorni si conserva lo storico usato dai temi | 30 |
| `tutte.finestra_ore` | Quante ore indietro guardano "Tutte" e "Fuori dai radar" | 48 |
| `tutte.max_notizie_singole_per_fonte` | In "Tutte", quante notizie di una sola fonte mostrare per ogni fonte | 8 |
| `raggruppamento.soglia_somiglianza` | Quanto devono assomigliarsi due notizie per stare nello stesso gruppo (da 0 a 1) | 0.30 |
| `raggruppamento.soglia_storie` | Quanto devono assomigliarsi due gruppi per diventare una sola storia | 0.18 |
| `raggruppamento.soglia_aggancio` | Quanto deve assomigliare una notizia di una sola fonte a una storia per entrarci | 0.25 |
| `fuori_dai_radar.min_fonti_alternative` | Minimo di fonti indipendenti (testate online, inchiesta, divulgatori) | 2 |
| `fuori_dai_radar.max_fonti_grandi` | Massimo di agenzie e quotidiani nazionali | 1 |
| `fuori_dai_radar.segnalazioni_singole_da` | Da quali categorie si accettano le segnalazioni di una sola fonte | Inchiesta e fact-checking |
| `fuori_dai_radar.somiglianza_con_argomenti_coperti` | Scarta i "pezzi" di storie già coperte dai grandi giornali (0 = controllo spento) | 0.20 |
| `fuori_dai_radar.escludi_indirizzi` / `escludi_titoli` | Cosa non conta per "Fuori dai radar" (opinioni, rubriche, rassegne, dirette...) | vedi file |
| `estratto.max_caratteri` | Lunghezza massima dell'estratto | 200 |
| `aree` | I nomi e i colori delle aree politiche | sinistra … destra, non collocabile |

**Escludere sport, spettacolo e altre sezioni.** Nella parte `filtri` di `config.yaml` ci sono
tre elenchi, validi per tutte le fonti:
- `escludi_indirizzi`: una notizia è scartata se il suo indirizzo contiene uno di questi pezzi
  (es. `"/sport/"`, `"/spettacoli/"`);
- `escludi_titoli`: ...oppure se il titolo corrisponde a una di queste espressioni (es.
  `"^serie a\\b"` = titoli che iniziano con "Serie A");
- `escludi_sezioni_feed`: ...oppure se il feed della fonte la mette in una di queste sezioni
  (es. `sport`): serve per i giornali che non scrivono la sezione nell'indirizzo.

Per aggiungere una voce, copia una riga dell'elenco e cambia il testo tra virgolette. Per
escludere qualcosa di una sola fonte, usa invece `escludi` in `sources.yaml`.

**Come tarare il raggruppamento.** Guarda la pagina "Oggi" per qualche giorno:
- se vedi **notizie diverse nella stessa storia**, alza `soglia_storie` (es. da 0.18 a 0.20);
- se vedi **la stessa storia spezzata in più storie**, abbassala (es. a 0.16).

Cambia di 0.02 alla volta. I valori iniziali sono stati scelti provando su circa 3.000 notizie
vere: con 0.16 si univano vicende diverse, con 0.20 la stessa storia finiva divisa in due.

## 8. Scrivere la pagina "Perché esiste questo sito"

Il testo è nel file `contenuti/perche-esiste.md`. Si modifica come gli altri file (matita →
Commit changes). In cima al file c'è una breve spiegazione del formato.

- I pezzi tra parentesi quadre che iniziano con `SEGNAPOSTO` compaiono sul sito **evidenziati
  in giallo**: sostituiscili tutti con il tuo testo, togliendo anche le parentesi quadre,
  prima di far conoscere il sito.
- Il riquadro in cima alla pagina, che dice che si tratta di un'opinione personale separata
  dalla raccolta automatica, viene aggiunto dal sito da solo.
- La parola "censura" va usata **solo** in questa pagina: il resto del sito non la usa mai e
  una prova automatica lo controlla.

## 9. Aggiornare il sito

- **In automatico**: ogni 3 ore, senza fare niente.
- **Subito**: scheda **Actions** → **Aggiorna Giornalize** → **Run workflow**.
- **Dopo una modifica** a `sources.yaml`, `config.yaml`, ai testi o allo stile: si aggiorna da solo.

**Cambiare la frequenza**: nel file `.github/workflows/aggiorna.yml` cambia la riga
`- cron: "17 */3 * * *"`. Il `3` è il numero di ore: `*/2` = ogni 2 ore, `*/4` = ogni 4 ore.
Aggiorna anche `ogni_quante_ore` in `config.yaml`, che serve solo per il testo mostrato sul sito.
GitHub a volte ritarda gli aggiornamenti programmati di qualche decina di minuti: è normale.

**Se GitHub sospende l'aggiornamento automatico.** Nei progetti pubblici GitHub mette in pausa
gli aggiornamenti programmati se per 60 giorni nessuno modifica il progetto. Le notizie salvate
dal programma dovrebbero bastare a evitarlo. Se però ricevi un'email che lo segnala, vai in
**Actions** → **Aggiorna Giornalize** e clicca **Enable workflow**.

## 10. Controllare gli errori

Ci sono tre posti dove guardare:

1. **Pagina "Fonti" del sito**: per ogni fonte dice se la raccolta funziona e quante notizie ha
   dato nelle ultime 48 ore.
2. **Scheda Actions su GitHub**: ogni aggiornamento è una riga. Pallino verde = tutto bene;
   rosso = l'aggiornamento si è fermato e il sito è rimasto com'era. Cliccandoci si vede il
   motivo, che di solito è un errore di scrittura in `sources.yaml` o `config.yaml`.
   GitHub ti avvisa anche per email.
3. **File `data/registro.log`** e **`data/stato_fonti.json`**: il registro dettagliato degli
   avvisi (fonti irraggiungibili, feed trovati in automatico, ecc.).

Una fonte irraggiungibile **non** fa diventare rosso l'aggiornamento: è normale che ogni tanto
un sito non risponda. Il programma la salta e riprova al giro successivo.

## 11. Costi e limiti

- **Costi**: zero. GitHub, GitHub Actions e GitHub Pages sono gratuiti per i progetti pubblici,
  e questo sito usa una piccola parte dei limiti gratuiti. L'unico costo possibile è un dominio
  personalizzato (facoltativo).
- **Intelligenza artificiale**: non è usata. Il raggruppamento confronta le parole dei titoli.
  Si potrà valutare in futuro: ha un costo e va segnalata sul sito.
- **Feed incompleti**: alcuni giornali mettono nel feed solo una parte dei loro articoli. Quindi
  una notizia può finire in "Fuori dai radar" anche se un giornale ne ha parlato. Il sito lo
  spiega e offre il link «Verifica tu», che la cerca sui siti dei grandi giornali.
- **Instagram**: le pagine con `instagram_api: true` sono lette con l'API ufficiale (capitolo 5);
  si possono sempre aggiungere post a mano.
- **Siti che bloccano i programmi automatici**: Fanpage e Scomodo rifiutano l'accesso ai server
  di GitHub. Non aggiriamo il blocco: di queste due testate si leggono i post Instagram con l'API
  ufficiale (titolo e link al post), e gli articoli si possono aggiungere a mano.
- **Fonti senza feed**: Il Foglio e Claim oggi non hanno un feed che funzioni, e quello di ISPI è
  fermo da novembre 2024. Restano nell'elenco e si possono aggiungere a mano; il programma
  riprova a ogni giro.
- **Edizioni locali di Repubblica**: non hanno un feed RSS; si leggono le loro "news sitemap".
  Gli articoli dell'edizione nazionale sono esclusi, perché sono già nella fonte "la Repubblica".
- **Sport e spettacolo**: i filtri si basano su indirizzi, titoli e sezioni dei feed, quindi ogni
  tanto qualche articolo passa lo stesso. Si corregge aggiungendo una voce ai filtri (capitolo 7).
- **Corriere della Sera**: a ottobre 2026 i vecchi feed del Corriere si erano fermati; ora usa
  quelli nuovi (`feed-hp` e `dynamic-feed`). Se tornasse a 0 notizie, lancia **Prova le fonti**:
  il rapporto mostra gli indirizzi trovati sul sito.

## 12. Per chi vuole provarlo sul proprio computer

Serve Python 3.12 o più recente. Dal terminale, nella cartella del progetto:

```bash
python -m venv .venv
source .venv/bin/activate              # su Windows: .venv\Scripts\activate
pip install -r requirements.txt

python -m giornalize aggiorna          # raccoglie le notizie e costruisce il sito in site/
python -m giornalize prova-fonti       # prova tutti i feed e stampa un rapporto
python -m giornalize prova-fonti ansa ilpost   # prova solo alcune fonti
python -m pytest -q                    # esegue le prove automatiche
python -m http.server -d site 8000     # poi apri http://localhost:8000 nel browser
```

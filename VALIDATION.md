# Verifica del 15 settembre 2026

- 11 test automatici superati: intervalli e 915%, classificazione, valori mancanti,
  effemeridi coerenti, alias, input, DST e report con target senza eventi.
- Cinque target richiesti, 365 giorni dal 2026-09-15: 1.126 eventi enumerati.
  Sequenza dei cicli verificata indipendentemente con Astropy, senza buchi o duplicati.
- 260 righe terrestri TAPIR confrontabili; nessuna anomalia >2 punti percentuali nelle query suddivise.
- Massimo residuo temporale BJD_TDB/UTC: 0,040153 secondi.
- Convergenza griglia 120 vs 30 secondi su tre eventi parziali: differenza massima
  0,000621 punti percentuali. Verifica numerica mirata, non certificazione di ogni caso limite.
- PDF pratici: 5 Prima scelta, 4 Alternative, 19 Da valutare.
- Classi astronomiche complete: 7 Prima scelta, 8 Alternative, 106 Da valutare,
  1.005 Non consigliato (inclusi eventi diurni/non visibili).
- HD 189733 b: prova reale aggiuntiva di 14 giorni, 7 eventi, controlli passati.
- Alias reale WASP-77 b risolto a WASP-77 A b; prova di un giorno senza eventi riuscita.
- Caso storico CoRoT-11 b del 26/06/2027: copertura ricalcolata 45,2068%,
  coerente con 45,3% ricavato dagli orari arrotondati, non 915%.
- PDF: 2 / 2 / 7 pagine, prime e ultime pagine renderizzate e controllate;
  coordinate dei testi nella pagina sospetta verificate, nessuna sovrapposizione.
- Hash degli originali e integrità ZIP verificati. TAPIR originale senza differenze tracciate;
  commit locale uguale a upstream dd08869fa142f1a90a6a4973b3cd38d1376fdc56 al controllo.
- Tempo misurato esecuzione annuale finale: 428,7 secondi, circa 7,1 minuti.
  Riepilogo per target aggiunto in una successiva generazione dei report; metriche immutate.

Il programma e il profilo sono descritti in README.md. L'output finale è:
/home/gaetano/Downloads/GaetanoTrovato_20260915_CLI

# Audit di chiusura (15 settembre 2026, sessione finale)

- Suite: 11/11 test superati prima e dopo le verifiche; nessun TODO/FIXME nel codice.
- Riproducibilità da clone pulito (`/tmp`): `uv venv` + `uv pip install -r requirements.txt`
  + unittest 11/11 + `./uan-transits plan --help`: PASS.
- Run 67 target reali (lista UAN, 30 giorni dal 2026-09-15): COMPLETATO in 605 s,
  1089 eventi, 67/67 target elaborati, 0 esclusioni, 0 anomalie TAPIR.
  `verify_output.py`: PASS (enumerazione cicli senza buchi/duplicati, hash, ZIP,
  max residuo temporale 0,0404 s, convergenza griglia <0,00005 pp).
  Massimo scarto percentuali TAPIR vs ricalcolo: 0,50 punti (soglia 2).
- Smoke test freschi con download NASA ex novo: WASP-77 A b 2 giorni (1 evento) e
  Qatar-1 b 2 giorni (2 eventi, target mai usato in sviluppo): entrambi PASS.
- Run annuale 5 target riverificato con il codice attuale: PASS (1126 eventi).
- Controllo scientifico indipendente (WASP-77 A b, ciclo 1050, 2026-12-11):
  centro da effemeride NASA PS grezza con conversione diretta BJD_TDB→UTC
  (inclusa light travel time baricentrica): accordo 0,033 s con TAPIR;
  quote ingresso/centro/uscita: accordo 0,0 arcmin; Sole a -45°...-67° (notte profonda),
  Luna sotto orizzonte e al 3%: coerente con metriche registrate.
- PDF del run 67 target: 3 categorie, testo estraibile e intestazioni coerenti coi conteggi
  pratici (19/7/40); categorie vuote e target senza eventi gestiti (riepilogo_target.csv).
- `git diff --check`: PASS; repository senza file generati o spazzatura.

# Formato PDF richiesto (15 settembre 2026, serata)

- I tre PDF di categoria ora replicano il pacchetto storico: tabelle TAPIR originali
  in A4 orizzontale, una query TAPIR delimitata per evento pratico, colonne identiche
  alla stampa web (data locale/UTC, nome e link, V, Start-Mid-End con Luna, durata,
  BJD_TDB, % transito/baseline con diagramma).
- Implementazione: query TAPIR individuale per evento (finestra 1 o 2 giorni secondo
  il periodo), tabella estratta staticamente, colonne nascoste dal JS del sito rimosse,
  rendering con chromium headless. Fallback automatico alle schede ReportLab.
- Fix during test: `risultati.csv` ora include tutte le chiavi presenti negli eventi
  (prima Crash se un evento aveva campi extra); rendering in temp sotto $HOME perché
  snap chromium non accede a /tmp.
- Rigenerati i PDF dei pacchetti esistenti senza ricalcolare le metriche:
  67 target: 66/66 tabelle (141 s); 5 target: 28/28 (63 s). Conteggi e ZIP invariati,
  `verify_output.py`: PASS su entrambi; una pagina per evento (19/7/40 e 5/4/19).
- Suite 11/11 dopo le modifiche. Smoke end-to-end WASP-77 A b (2 giorni): PASS.

# Run annuale 67 target con policy v1 (15-16 settembre 2026)

- Policy UAN v1 implementata: copertura >=90% operativa (100% ideale), baseline per
  lato <50% debole / 50-79% accettabile / >=80% buona, etichetta geometria target
  (NON CONSIGLIATO DAL SITO <15°, MOLTO DIFFICILE 15-20°, MARGINALE 20-30°, BUONO
  30-40°, MOLTO FAVOREVOLE >=40°), score secondario 0-100 (30/15/20/10/10/10/5,
  quota saturata a 40°, mai sopra le classi), PRIMARY+BACKUP1+BACKUP2 per target.
- Run: 67 target UAN, 365 giorni da 2026-09-15, effemeridi NASA aggiornate.
  Completato in 5809 s (~97 min). Output: GaetanoTrovato_20260915_192917_339538.
- 13264 eventi: 439 PRIMA SCELTA, 244 ALTERNATIVE, 2439 DA VALUTARE, 10142 NON
  CONSIGLIATO. In fascia pratica (fino alle 01:00): 143/89/449.
- Geometrie: 51 MOLTO FAVOREVOLE, 5 BUONO, 2 MARGINALE, 2 MOLTO DIFFICILE,
  7 NON CONSIGLIATO DAL SITO (incl. WASP-121 b ~10°, WASP-4 b ~7°).
- Coerenza col lavoro storico: WASP-77 A b MOLTO FAVOREVOLE con PRIMARY PRIMA SCELTA
  (10/11/2026, score 96.8); CoRoT-11 b geometria favorevole ma eventi DA VALUTARE;
  WASP-142 b MARGINALE con migliori eventi DA VALUTARE; nessun primary per WASP-121/4 b.
- 14 anomalie TAPIR (es. 777%, 1422%) segnalate e conservate con ricalcolo indipendente
  (36%, 22%, ...), classe decisa dal ricalcolo, mai dal valore TAPIR.
- Massimo residuo temporale BJD_TDB/UTC: 0,046 s. Enumerazione cicli completa senza
  buchi/duplicati. PDF categoria in formato TAPIR: 143+89+449 pagine, una per evento.
- verify_output.py: PASS (hash, ZIP 44 MB, convergenza griglia <0,0001 pp).

# Policy v2.1 (16 settembre 2026): Luna a 4 livelli, logistica separata, selezione per target

- Implementata la v2.1 dall'audit `AUDIT_RIASSEGNAZIONE_UAN_v2.md`:
  gerarchia rigida (timing -> geometria -> copertura -> baseline -> quota -> effemeride
  -> Luna -> logistica -> score); copertura >=99.5% per PRIMA SCELTA (90-99.5 max
  ALTERNATIVE); Luna BASSA/MODERATA/ALTA/ESTREMA con le 9 regole dell'audit (ESTREMA ->
  DA VALUTARE); logistica P1/P2/P3 separata dalla qualità; reason_codes su ogni evento
  (MOON_HIGH, ALTITUDE_MID_LOW, TARGET_GEOMETRY_MARGINALE, ...); score v2 30/20/20/15/10/5
  senza magnitudine e profondità; selezione per target PRIMARY+BACKUP1+BACKUP2 con
  diversificazione temporale (>=7 giorni, fallback >=3); PDF ridotti alla selezione.
- 12/12 test (aggiunti: 9 esempi Luna dell'audit, frontiere 99.5/50/80, score v2,
  diversificazione backup, pool P1).
- Archivio annuale riclassificato offline (niente ricalcolo TAPIR/Astropy, solo policy):
  13264 eventi -> PRIMA SCELTA 439->311, ALTERNATIVE 244->318, DA VALUTARE 2439->2493.
  In fascia operativa P1: 2605 eventi. Selezionati 174 eventi su 58 target (73 primary
  PRIMA SCELTA, 32 ALTERNATIVE, 69 DA VALUTARE; 9 target senza pool operativo).
- Controlli spot contro l'audit: KELT-16 21/09 -> ALTERNATIVE/MODERATA; KELT-16 22/09 ->
  ALTERNATIVE/ALTA; WASP-93 28/09, HAT-P-20 16/03, HAT-P-23 12/09 -> DA VALUTARE/ESTREMA;
  WASP-135 23/09 -> ALTERNATIVE/MODERATA: tutti conformi.
- Nuovi PDF: 68 + 12 + 36 pagine (era 143+89+449): solo PRIMARY/BACKUP per target,
  tabelle TAPIR originali. verify_output.py: PASS (incl. selezione P1 e separazione backup).
- Esempio selezione WASP-77 A b: PRIMARY 10/11/2026 (99.9), BACKUP1 10/12/2026 (99.9),
  BACKUP2 09/01/2027 (96.9) — notti ben separate.
- Fix durante l'implementazione: intro TAPIR ripetute nel PDF di selezione (ora solo
  una); `tapir_anomaly` persa nel refactor (ripristinata, 14 anomalie ancora tracciate).

# Audit v2.1 (16 settembre 2026, sessione di verifica)

- Bug reale trovato e corretto nella selezione: la separazione temporale prevaleva
  sulla quality_class (PRIMA a +4 gg perdeva contro ALTERNATIVE a +20). Ora la classe
  migliore viene cercata prima, poi separazione >=7 giorni, poi >=3, poi classe inferiore.
  7 selezioni dell'archivio annuale corrette; 14/14 test inclusi i casi A-D sintetici.
- Provenance: manifest ora con policy_version, git_commit, generated_at, logistics_counts;
  0_LEGGIMI dichiara la policy; planner_source dell'archivio annuale aggiornato al codice
  v2.1 realmente usato (era rimasto lo snapshot v1).
- Hard-constraint audit automatico su 13264 eventi: nessuna PRIMA SCELTA viola i requisiti
  (copertura >=99.5, baseline >=80, quota >=30, Luna BASSA); nessuna ALTERNATIVE contiene
  trigger DA VALUTARE; ogni DA VALUTARE ha reason_code giustificativo. PASS.
- Falso allarme documentato: TrES-3 b e Qatar-1 b con score 99.9 restano DA VALUTARE
  per TTV (corretto: lo score non promuove mai).
- Suite 14/14 con exit code reale; smoke end-to-end WASP-77 A b + verify_output PASS;
  verify_output sull'archivio annuale PASS; git diff --check OK.

# Presentazione PDF cronologica (16 settembre 2026)

- Solo presentazione, zero cambi a classificazione, score, ruoli o selezione:
  i tre PDF di selezione sono ora in ordine cronologico GLOBALE per centro locale
  (mid_local, Europe/Rome), con separatori mensili (SETTEMBRE 2026, ...) e
  intestazione esplicita per evento: TARGET — ROLE, centro locale con timezone,
  classe, score, nota "Tabella TAPIR originale: orari UTC" (valori TAPIR invariati).
- Pagina per PDF: 143/89/449 -> 102/18/54 eventi (uno per pagina, ordine globale).
  L'insieme selezionato e' identico (174 eventi, 58 target); i test verificano
  l'uguaglianza prima/dopo e che l'ordinamento ignori i nomi dei target.
- 18/18 test (4 nuovi: ordine globale, confine d'anno, offset DST +02/+01,
  insieme selezione invariato). verify_output PASS; controllo visivo di prima
  pagina, cambio mese (OTTOBRE 2026 a pagina 7) e ultima pagina: OK.

# Calendario operativo: EXTRA visibili (16 settembre 2026, reporting only)

- Policy v2.1.1 NON modificata: classificazione, moon risk, score, logistica P1/P2/P3
  e selezione PRIMARY/BACKUP1/BACKUP2 restano esattamente gli stessi (verificato da test).
- PRIMARY/BACKUP sono le TRE raccomandazioni principali per target, non un filtro:
  1_PRIMA_SCELTA.pdf e 1_PRIMA_SCELTA.html ora contengono TUTTI gli eventi
  PRIMA SCELTA + P1 (97 nell'archivio annuale: 78 PRIMARY/BACKUP + 19 EXTRA, 34 target)
  in ordine cronologico globale con layout compatto a tabella (3 pagine, prima 102).
- 2_ALTERNATIVE: calendario cronologico puro degli ALTERNATIVE+P1 (116 eventi, 3 pagine).
- 3_DA_VALUTARE: vista curata per target (migliori 3 P1 per target, cronologica, 5 pagine).
- Nuovi file machine-readable: calendario_prima_scelta.csv/.json (20 campi, ordinati).
- riepilogo_target: aggiunti first_choice_p1_count, extra_first_choice_p1_count,
  extra_first_choice_dates. Manifest: sezione reporting + conteggi calendario.
- verify_output esteso: completezza PRIMA/P1, purezza di classe, nessun P2/P3,
  nessun duplicato, ordine cronologico, ruoli invariati, EXTRA coerenti. PASS.
- WASP-77 A b regression: 3 occasioni vere (PRIMARY 10/11, BACKUP1 10/12, BACKUP2 09/01);
  nessun EXTRA forzato: tutte le altre notti falliscono davvero la policy (copertura
  parziale, baseline debole, Luna, transito diurno).
- 30/30 test (12 nuovi di calendario). TAPIR/Astropy NON rieseguiti: solo reporting.

# Calendario operativo congiunto (16 settembre 2026, reporting only)

- Nuovo output `0_CALENDARIO_OPERATIVO.{html,pdf,csv,json}`: vista cronologica unica
  di TUTTI gli eventi (PRIMA SCELTA o ALTERNATIVE) AND P1, senza altri filtri nè limiti
  per target. Risponde alla domanda "qual e' la prossima osservazione buona o ottimale?".
- Archivio annuale: 213 eventi (97 PRIMA/P1 + 116 ALTERNATIVE/P1), 5 pagine PDF.
- Regression case KELT-16 b 21/09/2026 23:16: presente come ALTERNATIVE (EXTRA),
  reason_code MOON_MODERATA, score 96.2, NON promosso. verify_output lo controlla.
- Le tabelle calendario mostrano ora anche quality_class e moon_risk per riga
  (presentazione; nessuna soglia o classe modificata).
- 31/31 test (1 nuovo aggregato con i 12 casi richiesti). verify_output PASS
  (inclusi: 4 file presenti, conteggio == (PRIMA or ALTERNATIVE) and P1, nessun
  duplicato, ordine cronologico, KELT-16, nessuna modifica ai risultati scientifici).
- Future work (NON implementato, YAGNI): conflict detection, scheduling solver,
  modelli telescopio/camera, SNR, stelle di confronto Gaia, priorita' ExoClock, meteo.

# Dossier 1/2/3 nel formato TAPIR autentico (16 settembre 2026)

- Produttivizzazione del renderer dello spike (commit a58f37d): i dossier ufficiali
  1_PRIMA_SCELTA, 2_ALTERNATIVE e 3_DA_VALUTARE sono ora pagine TAPIR autentiche
  aggregate (HTML sorgente -> Chromium -> PDF), ordine cronologico globale per
  mid_local (Europe/Rome), indice con anchor interni, disclaimer source-of-truth.
- Contenuti: 1 = PRIMA SCELTA+P1 (97 eventi/34 target, 52 pagine, 2.30 MB);
  2 = ALTERNATIVE+P1 (116/31, 61 pagine, 2.76 MB); 3 = shortlist DV corrente
  (174/54, 92 pagine, 4.16 MB). 0_CALENDARIO_OPERATIVO: byte-identico (5 pagine).
- Fix spike: ID HTML unificati via namespace per evento (zero duplicati);
  header mese + primo finding = blocco indivisibile (niente header orfani);
  banda TAPIR inizia su pagina nuova (niente pagina quasi vuota);
  indice chiuso correttamente (era la causa dell'impaginazione rotta).
- 27 frammenti TAPIR della shortlist DV generati lazialmente in reporting
  (query di sola presentazione: nessun dato astronomico ricalcolato).
- Policy v2.1.1 invariata: quality/logistics/score/PRIMARY-BACKUP-EXTRA verificati
  identici prima/dopo (snapshot 13264 eventi). risultati.json/csv e 0_CALENDARIO
  byte-identici. Regression: WASP-77 10/11 PRIMARY in 1; KELT-16 21/09 ALTERNATIVE
  EXTRA in 2 e assente da 1.
- 39/39 test (nuovi: ID unici, anchor validi, mutazione assente, confine anno+DST
  nel documento, KELT-16 escluso da 1, frammento mancante = errore esplicito).
  verify_output PASS (esteso: set dossier, ID unici, anchor, regression).

# BUGFIX framenti TAPIR nei dossier (16 settembre 2026, serata)

- Bug reale segnalato e confermato: KELT-1 b c2935 (16/09 22:26) incorporava la
  tabella TAPIR dell'evento 11/11 (c2981). Causa: nomi file frammento sequenziali
  per-target riusati fra generazioni diverse (run annuale -> dossier-era -> lazy),
  con puntatori stali nei risultati memorizzati.
- Fix generale (downstream, nessuna policy/selection/score toccata):
  1. naming deterministico per evento: tapir_event_c{cycle}.html (zero collisioni);
  2. validazione obbligatoria dell'IDENTITA' di ogni frammento incorporato:
     target TAPIR == target planner E midpoint TAPIR (Start-Mid-End, convertito
     in Europe/Rome) == mid_local del planner entro 120 s;
  3. mismatch -> rigenerazione presentazione-only (1 query TAPIR per evento);
     secondo mismatch -> errore esplicito, frammento mai inserito;
  4. preamboli query-level TAPIR ("Only 1 target matches...", "Upcoming events...")
     rimossi dai dossier aggregati.
- Nota tecnica TAPIR: la cella BJD_TDB stampata da TAPIR in alcune query singole
  e' interna al suo output di ~7 min rispetto alla propria colonna Start-Mid-End;
  la validazione usa quindi la colonna Start-Mid-End (coerente col planner entro
  60 s) e NON la cella BJD. Il mid scientifico resta jd_utc_exact del planner
  (residuo indipendente 0,04 s).
- 41/41 test (nuovi: validazione identity, wrong target/mid, ensure su esistente/
  puntatore/copertura rigenerazione con engine finto, assenza preamboli).
- verify_output PASS (esteso: identity di TUTTI i 387 frammenti dei dossier,
  regression KELT-1 c2935/c2981 distinti e coerenti, KELT-16 in 2 non in 1).
- Dati scientifici invariati: snapshot 13264 eventi identico; risultati.json/csv e
  0_CALENDARIO_OPERATIVO.* byte-identici. Dossier rigenerati: 52/61/92 pagine.
- Nota: l'audit di riproducibilita' TAPIR ha sovrascritto i soli raw
  KELT-1_b_event_c2935.txt/.log (timestamp CGI; riga scientifica identica).

Limiti: soglie euristiche; niente modello di strumentazione/meteo; effemeridi lineari,
TTV segnalate, covarianza ed errore durata non propagati; orizzonte piano e rifrazione
assente. IERS oltre l'intervallo disponibile genera un avviso di precisione a livello
arcosecondo, conservato in warnings.log. Verificare effemeridi aggiornate prima di osservare.

# Audit finale di release (16 settembre 2026)

- Verificati i 27 frammenti TAPIR generati lazialmente per 3_DA_VALUTARE:
  creati ESCLUSIVAMENTE come artefatti di presentazione (dossier 3), la shortlist
  era gia' determinata prima delle query (curated_review_rows usa solo
  quality_class/logistics_class/score/giorno, tutti pre-esistenti); nessun valore
  TAPIR usato per quality/logistics/score/selection (snapshot 13264 eventi
  identico al baseline). Query di tutti i 27 ricostruite e confrontate con
  l'output TAPIR archiviato: start_date/days coerenti al 100%.
- Zero sovrascritture di frammenti pre-esistenti (collisione di nomi esclusa).
- Provenance nel manifest: sezione 'provenance' con distinzione esplicita fra
  dati astronomici (run originale, non ricalcolati), riclassificazione offline,
  reporting (commit 49d48d0) e frammenti TAPIR lazy (mappatura completa
  evento->frammento/raw/query/UTC). git_commit aggiornato (era stale 92d0462).
- risultati.json/csv byte-identici; 0_CALENDARIO_OPERATIVO.* byte-identici;
  13264 eventi invariati campo per campo.
- Nota: tag v2.1.2 (-> 8c79bc0) esiste nel repo ma non e' stato creato in
  questa sessione; segnalato, nessuna azione.

# Release finale (16 settembre 2026)

- Stato consegnato: policy UAN v2.1.1 stabile, calendario operativo + dossier TAPIR
  autentici (1/2/3) + export Google Calendar (ICS/CSV) + archivio con provenance.
- 41/41 test; verify_output PASS su tutti i pacchetti; dipendenze ridotte
  (rimossi reportlab e pillow); renderer documentati in README.md.
- README.md riscritto come documentazione definitiva: architettura 0/1/2/3/9,
  policy completa, source-of-truth, provenance, limiti.

# Policy UAN v2.2.0 — gate di eleggibilita' (19-21 settembre 2026)

- Regola nuova: entrano nella pipeline solo i transiti con copertura 100% REALE
  ricalcolata da Astropy. Criterio sulla durata non coperta
  (`transit_uncovered_seconds <= 1e-3 s`), non sulla percentuale: nessun round(),
  nessun 99.5%, nessun valore TAPIR. La tolleranza sta sopra il rumore float
  dell'aritmetica in secondi unix (~1e-6 s a 1.7e9) e sotto la risoluzione della
  griglia 120 s con interpolazione lineare dei passaggi.
- Eventi non eleggibili: restano TUTTI in risultati.csv/json (enumerazione dei
  cicli invariata) con eligible=false, exclusion_reason=TRANSIT_NOT_100,
  category NON ELEGGIBILE, senza quality_class, logistics_class, score o ruolo.
  Nessuno compare in 0_CALENDARIO_OPERATIVO, 1_PRIMA_SCELTA, 2_ALTERNATIVE,
  3_DA_VALUTARE, ICS/CSV.
- DA VALUTARE cambia significato: transito completo al 100% con un altro problema
  (TTV, baseline debole, Luna ESTREMA, quota, dati mancanti), mai transito parziale.
- Nessun'altra soglia della policy modificata; algoritmo astronomico invariato.
- Confronto sul run annuale 2026-09-15 (67 target, 13264 eventi), riclassificato
  offline senza ricalcolare nulla di astronomico:
  cicli 13264 -> 13264, metriche astronomiche cambiate 0;
  eligible 1106 / esclusi TRANSIT_NOT_100 12158;
  PRIMA SCELTA 311 -> 311, ALTERNATIVE 318 -> 318, DA VALUTARE 2493 -> 477,
  NON CONSIGLIATO 10142 -> 0, NON ELEGGIBILE 0 -> 12158;
  dossier 1/2 invariati (97/116), 3_DA_VALUTARE 174 -> 116;
  ruoli 58/58/58 -> 55/50/45 (prima 25 ruoli stavano su eventi <100%);
  i 1106 eventi al 100% mantengono classe, score e logistica identici; 3 soli
  cambi di ruolo, tutti conseguenza diretta del gate.
- Target rimasti senza PRIMARY perche' privi di eventi P1 al 100%:
  CoRoT-11 b, HAT-P-41 b, WASP-52 b.
- verify_output: invarianti forti nuove (ogni riga operativa eligible e full
  transit, nessun TRANSIT_NOT_100 in calendari/dossier/ICS, esclusi tutti in
  archivio, enumerazione completa, DA VALUTARE mai parziale).
- Bug latenti pre-esistenti trovati e corretti: export calendario_prima_scelta.*
  non piu' scritto da 49d48d0; lookup di versione reportlab dopo la rimozione in
  4b103f4 (CLI in errore all'avvio); tapir_event_html non importato in planner.py
  (NameError a fine run).

# Audit incrociato esterno (21 settembre 2026)

Revisione avversaria in due passate (scout + verificatore, z-ai/glm-5.3-flash via
OpenRouter, ~$0.03) sull'intero sorgente + docs + test. Output integrale in
verification/audit-glm/. Ogni finding riverificato sul codice prima di agire.

Corretti:
- verify_output era cucito sul run annuale (WASP-77 10/11, KELT-1 c2935/c2981,
  KELT-16 21/09 senza guardia): crashava su qualunque altro pacchetto. Ora i casi
  di regressione si applicano solo se quegli eventi esistono. Provato: PASS su un
  pacchetto HAT-P-3 b / Qatar-5 b di 14 giorni.
- verify_output imponeva |residuo BJD| < 2 s a ogni evento, mentre la policy
  ammette residui maggiori con classe DA VALUTARE (TIMING_FAILED) e il limite e'
  un parametro di profilo. Ora verifica la coerenza del flag con
  timing_residual_limit_seconds.
- Gate fail-open: compute_selection/calendari/shortlist usavano
  e.get('eligible',True); su un risultati.json pre-v2.2 (path di riclassificazione
  offline documentato) un transito parziale sarebbe rientrato. Ora fail-closed.
- Separazione dei backup verificata solo rispetto a PRIMARY: ora rispetto a tutti
  i pick precedenti, con la deroga documentata del fallback (quando nessun
  candidato del target e' abbastanza separato). Il primo giro ha trovato
  KELT-9 b a 2.96 giorni: legittimo, e' il fallback.
- Link NASA nei calendari: quote() su un nome gia' pre-escaped produceva
  %2520 (link rotti per ogni target con spazi).
- Testi 0_LEGGIMI/NOTE_SELEZIONE allineati ai report reali (dossier 1/2 = tutti
  gli eventi P1 della classe con EXTRA, non solo la selezione; eleggibilita' v2.2
  al posto del 99.5%; Luna MODERATA illum >=70 come nel codice) e albero del
  pacchetto in README (ICS/CSV stanno in 9_ARCHIVIO_COMPLETO).
- Assert tautologico sulla copertura dell'identity dei frammenti (+n-n).

Respinti dopo verifica: indice fisso dts[2] in tapir_fragment_identity
(speculativo, e comunque errore rumoroso, non una raccomandazione sbagliata);
moon_risk con Luna sopra l'orizzonte solo durante la finestra osservabile
(conforme alla policy, direzione conservativa); disallineamento geocentrico vs
baricentrico ai bordi della finestra (l'effetto reale e' la derivata del light
travel time, ~5 s/giorno, non gli 8 minuti ipotizzati).

55/55 test; verify_output PASS sul pacchetto annuale riclassificato e su un
pacchetto smoke con target diversi.

# Vista 0_EFFEMERIDI_100 e boundary audit (21 settembre 2026)

Vista nuova, solo reporting: `0_EFFEMERIDI_100.html` + `.csv` nella radice del pacchetto,
TUTTI e SOLI gli eventi con `eligible == true`, ordine cronologico globale (Europe/Rome),
senza nessun altro filtro (tutte le quality_class, tutte le logistiche, anche senza ruolo).
Sul run annuale: 1106 righe = 1106 eventi eleggibili, zero duplicati, `transit_percent`
tutti 100.0 e `transit_uncovered_seconds` tutti 0.0; composizione PRIMA SCELTA 311,
ALTERNATIVE 318, DA VALUTARE 477; P1 415, P2 410, P3 281; 956 eventi senza ruolo
(che i calendari operativi non mostravano). verify_output e i test dimostrano
`set(0_EFFEMERIDI_100) == set(eventi eligible)` senza numeri hardcoded.

Invarianza verificata dopo la modifica (reporting-only): 13264 cicli identici, ZERO campi
diversi su tutti gli eventi, 0_CALENDARIO_OPERATIVO.json / calendario_prima_scelta.json /
riepilogo_target.json e i dossier 1/2/3 byte-identici.

Boundary audit ad alta risoluzione sugli 11 eventi con 99.5% <= copertura < 100%
(solo quelli: gli altri 13253 non sono stati ricalcolati). Sampling 120 s (archivio),
30 s e, per i casi entro 30 s dalla soglia, 10 s. Tolleranza del gate: 1e-3 s.

```
target        cycle  mid_local          cov120    cov30    cov10   unc120  unc30  unc10  eligible
WASP-3 b       2566  2026-10-23 20:34  99.8765  99.8765  99.8765   12.40  12.40  12.40  False
WASP-77 A b    1042  2026-11-30 00:36  99.8061  99.8061  99.8061   15.15  15.15  15.15  False
WASP-76 b      1150  2026-12-12 19:33  99.5359  99.5357      n/d   63.49  63.51    n/d  False
WASP-12 b      3476  2026-12-26 19:50  99.7759  99.7757  99.7757   24.21  24.22  24.22  False
HAT-P-36 b     2667  2027-01-19 22:56  99.5778  99.5774      n/d   33.90  33.93    n/d  False
WASP-3 b       2656  2027-04-08 01:42  99.5470  99.5467      n/d   45.50  45.53    n/d  False
KELT-9 b       1745  2027-05-15 02:32  99.5922  99.5927      n/d   61.07  61.00    n/d  False
Qatar-1 b      2807  2027-05-30 22:30  99.7996  99.8001  99.8001   11.97  11.95  11.94  False
WASP-114 b     2792  2027-06-10 02:14  99.6596  99.6596      n/d   34.06  34.06    n/d  False
WASP-103 b     4660  2027-08-03 22:42  99.9083  99.9084  99.9084    8.55   8.54   8.54  False
WASP-93 b      2031  2027-08-11 22:20  99.9584  99.9585  99.9585    3.34   3.33   3.33  False
```

11/11 restano non eleggibili: nessun cambio di stato, nessun dato o output modificato.
Il caso piu' vicino alla soglia (WASP-93 b, 3.33 s scoperti) sta 3300 volte sopra la
tolleranza; la differenza fra 120 s e 10 s di sampling e' al massimo ~0.03 s, quindi
la griglia non e' il fattore limitante e la classificazione del gate e' stabile.

# Merge di origin/main (9a8bde8) e release v2.3.0 (21 settembre 2026)

`origin/main` conteneva `9a8bde8` "policy: require exact 100% transit coverage" (squash del
branch `origin/policy/full-transit-100`, 30 commit, albero identico: nessun contenuto ulteriore).
E' una implementazione alternativa della stessa richiesta, fatta a partire da 49ebe1f: alza a 100
le soglie percentuali nel profilo e vieta classi/ruoli sotto il 100%. Il lavoro locale risolve lo
stesso problema a monte, con un gate sulla durata non coperta.

Merge esplicito (`--no-ff`, nessun rebase, nessun force). Principio di risoluzione: una sola fonte
della regola, il gate `transit_uncovered_seconds <= 1e-3 s`. Da 9a8bde8 sono state tenute solo le
etichette di versione (v2.1 -> v2.2.0) e il testo piu' preciso del motivo TRANSIT_COVERAGE_LOW.

Sono state RIMOSSE quattro fonti concorrenti della stessa policy, che il merge avrebbe introdotto:

1. `capodimonte.json`: `transit_operational_percent`/`first_choice_min_percent` a 100.
   Con il gate, un evento eleggibile puo' avere copertura 99.99999% (1e-3 s scoperti su 3 h):
   `classify` lo avrebbe marcato TRANSIT_COVERAGE_LOW/DA VALUTARE, in diretta contraddizione con
   il gate e con la semantica "DA VALUTARE = transito completo con un altro problema".
   Ripristinate le soglie storiche 90 / 99.5, raggiungibili solo a valle del gate.
2. `planner.validate_profile`: vincolo che imponeva soglie esattamente 100 nel profilo.
3. `verify_output`: `assert transit_percent >= 100` per PRIMA SCELTA/ALTERNATIVE e le stringhe
   `operational_scope ... transit_percent == 100`, sostituiti dall'invariante di eleggibilita'.
4. `reports.compute_selection`: 9a8bde8 rimuoveva DA VALUTARE dalle classi ammesse ai backup
   (commit "policy: remove review-only backup class"). Cambia la selezione (41 ruoli su 150 nel
   run annuale) e la policy PRIMARY/BACKUP, esplicitamente fuori dal mandato: ripristinata.
   Era l'unico conflitto arrivato in un blocco NON conflittuale, individuato dal drift di
   selezione rilevato da verify_output su CoRoT-2 b c2283.

Tre test introdotti da 9a8bde8 codificavano quelle fonti e sono stati riallineati al gate
(profilo senza vincolo sul 100%; label favorevole stantia espressa con eligible=False;
un target con soli DA VALUTARE riceve comunque PRIMARY, policy invariata).

Dopo il merge, sul run annuale: 13264 cicli, ZERO campi diversi, 0_CALENDARIO_OPERATIVO.json,
calendario_prima_scelta.json, riepilogo_target.json, i dossier 1/2/3 e 0_EFFEMERIDI_100.csv
byte-identici a prima del merge. 1106 eligible / 12158 esclusi, EFFEMERIDI_100 == eligible,
ruoli 55/50/45 (41 su DA VALUTARE, invariati), 11/11 boundary case ancora non eleggibili.
59/59 test; verify_output PASS sull'annuale e su uno smoke HAT-P-23 b / KELT-3 b.

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

Limiti: soglie euristiche; niente modello di strumentazione/meteo; effemeridi lineari,
TTV segnalate, covarianza ed errore durata non propagati; orizzonte piano e rifrazione
assente. IERS oltre l'intervallo disponibile genera un avviso di precisione a livello
arcosecondo, conservato in warnings.log. Verificare effemeridi aggiornate prima di osservare.

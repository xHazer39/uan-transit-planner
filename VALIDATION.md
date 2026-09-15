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

Limiti: soglie euristiche; niente modello di strumentazione/meteo; effemeridi lineari,
TTV segnalate, covarianza ed errore durata non propagati; orizzonte piano e rifrazione
assente. IERS oltre l'intervallo disponibile genera un avviso di precisione a livello
arcosecondo, conservato in warnings.log. Verificare effemeridi aggiornate prima di osservare.

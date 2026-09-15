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

Limiti: soglie euristiche; niente modello di strumentazione/meteo; effemeridi lineari,
TTV segnalate, covarianza ed errore durata non propagati; orizzonte piano e rifrazione
assente. IERS oltre l'intervallo disponibile genera un avviso di precisione a livello
arcosecondo, conservato in warnings.log. Verificare effemeridi aggiornate prima di osservare.

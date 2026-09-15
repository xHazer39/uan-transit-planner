# UAN Transit Planner v1

CLI personale per Kubuntu: TAPIR enumera i transiti; Astropy ricontrolla tempi,
quote, notte, Luna e copertura; ReportLab crea PDF consultabili.

## Installazione da GitHub

Richiede Linux/Kubuntu, Git, `uv` e una copia funzionante di
[TAPIR con le sue dipendenze Perl](https://github.com/elnjensen/Tapir#readme).

```bash
git clone https://github.com/xHazer39/uan-transit-planner.git
cd uan-transit-planner
uv venv .venv --python 3.13
uv pip install --python .venv/bin/python -r requirements.txt
./uan-transits plan "WASP-77 A b" --tapir ~/Downloads/Tapir
```

Il launcher funziona dalla cartella clonata e attraverso link simbolici.
I cataloghi e i pacchetti di osservazione vengono generati localmente; non sono inclusi nella repository.

## Uso

```bash
uan-transits plan "WASP-77 A b" "CoRoT-11 b"
uan-transits plan --targets targets.txt --site capodimonte --start 2026-09-15 --days 365
uan-transits plan "WASP-142 b" --session-start 17:45 --session-end 01:00
uan-transits plan "HD 189733 b" --days 30 --min-altitude 25
```

Il comando è installato in `/home/gaetano/.local/bin/uan-transits`.
Se la shell non lo trova: `/home/gaetano/uan-transit-planner/uan-transits`.
`targets.txt`: un pianeta per riga, commenti con `#` su righe separate.
Nomi canonici/varianti ortografiche e alias NASA sono accettati; una stella
non viene automaticamente scambiata per un suo pianeta.

Oggi e 365 giorni sono i default. L'intervallo include i centri di transito
fra mezzanotte locale della data iniziale (inclusa) e quella finale (esclusa).
Ogni esecuzione crea una nuova cartella e ZIP in `~/Downloads`.
`--output /percorso/nuovo` sceglie una cartella che **non deve esistere**.

## Profilo

Modifica `capodimonte.json`, oppure passa un altro JSON con `--site /percorso/profilo.json`.
Coordinate verificate: [INAF](https://www.oacn.inaf.it/come-raggiungerci/).

- Copertura: Sole <= -12°, altezza >=20°.
- Qualità desiderata: 30°; quota grave: 15°.
- Baseline: un'ora per lato + errore del centro (1 sigma quando noto).
- Per classi favorevoli: almeno 30 minuti osservabili per lato; errore centro <=10 minuti.
- Luna critica: contemporaneamente >=70% illuminata, <=40° dal target e sopra l'orizzonte
  durante la parte osservabile. Altrimenti non viene automaticamente penalizzata.
- Transito completo: al massimo un secondo mancante.
- Orari pratici: crepuscolo nautico reale fino alle 01:00; la baseline può finire dopo.
- Le soglie sono **euristiche configurabili, non regole ufficiali UAN**.
- I PDF espongono la baseline pratica; l’archivio conserva anche quella astronomica.
- `riepilogo_target.csv`/`.json` riportano quota teorica e conteggi anche senza eventi.

Gli orari ISO includono l'offset stagionale. La notte è identificata dal mezzogiorno locale
precedente. Se si imposta un limite in un'ora autunnale ripetuta, si usa la seconda
occorrenza; se il limite cade nell'ora primaverile inesistente, viene spostato avanti.
I default 01:00 e inizio al crepuscolo non hanno queste ambiguità.

`--max-v` e `--min-depth` sono filtri espliciti opzionali; nessun limite fotometrico di default.
Gaia G non è V: con `--max-v` un target senza V verificabile viene escluso con motivazione.
I valori mancanti non diventano zero. Senza modello della camera/telescopio
il programma non garantisce misurabilità di una data profondità.

## Cosa aprire

1. `0_LEGGIMI.txt`: sintesi e istruzioni.
2. `1_PRIMA_SCELTA.pdf`, `2_ALTERNATIVE.pdf`, `3_DA_VALUTARE.pdf`: eventi in fascia pratica,
   presentati come **tabelle TAPIR originali** (una query TAPIR per evento, come nel
   pacchetto storico): orari locali/UTC, magnitudine, Luna, BJD_TDB, diagramma del
   transito e link a finding chart/airmass. Le intestazioni sono una sintesi locale;
   le percentuali TAPIR restano non validate (vedi sotto).
3. `9_ARCHIVIO_COMPLETO/index.html`: tutti gli eventi per target, inclusi fuori orario
   e non consigliati; tabelle originali TAPIR e link alle carte del campo/airmass online.
4. `risultati.csv`/`risultati.json`: metriche; `NOTE_SELEZIONE.txt`: metodo e limiti;
   `manifest.json`: parametri, versioni, hash e tempi; `target_esclusi.json`: esclusioni.

I PDF delle categorie richiedono `chromium` (snap va bene) e Internet al momento della
generazione per CSS e icone remote; il PDF finale è autonomo. Senza chromium, o se una
query TAPIR per evento fallisce, la categoria ricade automaticamente sulle schede
locali ReportLab (le categorie vuote usano sempre le schede).

TAPIR è copiato nell'output: il checkout in `~/Downloads/Tapir` non viene modificato.
La copia del template CSV espone il JD UTC preciso già calcolato dal motore.
Il comando richiede l'installazione Perl locale funzionante, inclusi i moduli in `~/perl5`.

## Dati e ripetibilità

Il catalogo viene aggiornato a ogni esecuzione. Si scelgono epoca e periodo dalla stessa
riga NASA PS, con BJD-TDB esplicito; i fallback su durata/fotometria sono documentati.
Le effemeridi con sistema temporale ambiguo non vengono indovinate.
La selezione minimizza l'errore massimo agli estremi dell'intervallo richiesto.

Cache solo esplicita:

```bash
uan-transits plan "WASP-77 A b" --cache /archivio/9_ARCHIVIO_COMPLETO/dati_originali
uan-transits plan "WASP-77 A b" --cache /archivio/9_ARCHIVIO_COMPLETO/dati_originali --offline
```

La prima usa la cache solo in caso di errore rete; la seconda non scarica.
La query deve corrispondere: la cache PS vale per lo stesso insieme di target.
La data originale e l'uso della cache sono riportati nei file `.meta.json` e sul terminale.
Uscita 2: errore oppure nessun target utilizzabile; il manifest registra lo stato.
Quando alcuni target falliscono, le esclusioni vengono conservate e gli altri elaborati.

## Verifica e dipendenze

```bash
.venv/bin/python -m unittest discover -s . -v
```

Versioni fissate in `requirements.txt`; ambiente isolato `.venv`.
Per ricrearlo con `uv`:

```bash
uv venv .venv
uv pip install --python .venv/bin/python -r requirements.txt
```

## Limiti dichiarati

- Periodo lineare; TTV note richiedono valutazione e un'ephemeride dedicata.
- Covarianza epoca/periodo e errore sulla durata non propagati.
- Quote senza rifrazione, orizzonte piano: edifici e ostacoli locali non modellati.
- Intervalli interpolati su griglia di 120 s; Luna su griglia <=10 min; non sono un solver di contatti ad alta precisione.
- IERS distribuito con Astropy: oltre la previsione disponibile vengono emessi avvisi,
  conservati in `warnings.log`. Le coordinate future non sono misure future.
- I link a carte del campo e airmass richiedono Internet; i report e i dati sono locali.
- Gli HTML originali TAPIR conservano le percentuali originali e sono marcati non validati.
- Date e quantità storiche 260/30/16 non sono obiettivi né risultati da forzare.

Fonti: [TAPIR](https://github.com/elnjensen/Tapir),
[NASA PS](https://exoplanetarchive.ipac.caltech.edu/docs/API_PS_columns.html),
[alias NASA](https://exoplanetarchive.ipac.caltech.edu/docs/sysaliases.html),
[Astropy](https://docs.astropy.org/en/stable/time/index.html).

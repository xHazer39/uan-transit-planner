# UAN Transit Planner

CLI locale (Kubuntu) che pianifica le osservazioni di transiti esoplanetari:
enumera i transiti con [TAPIR](https://github.com/elnjensen/Tapir), li **riclassifica e
verifica in modo indipendente** con [Astropy](https://www.astropy.org/) secondo la
**policy UAN v2.2.0**, e produce un pacchetto consegnabile alla sezione:
calendario operativo, dossier nel formato TAPIR autentico, archivio completo e
export per Google Calendar.

**Principio architetturale:** il **planner è la source of truth** (inclusione,
quality_class, logistics_class, score, PRIMARY/BACKUP/EXTRA, verifiche indipendenti).
**TAPIR è solo il formato di presentazione dettagliato.** Nessun valore TAPIR viene
usato per classificare o riselezionare eventi (in passato TAPIR ha prodotto valori
impossibili, es. "915%": il planner ricalcola e segnala, non corregge a mano).

---

## Installazione

Richiede Linux, Git, `uv`, Python 3.13 e una copia funzionante di
[TAPIR con le sue dipendenze Perl](https://github.com/elnjensen/Tapir#readme)
+ `chromium` (per il rendering HTML→PDF dei dossier).

```bash
git clone https://github.com/xHazer39/uan-transit-planner.git
cd uan-transit-planner
uv venv .venv --python 3.13
uv pip install --python .venv/bin/python -r requirements.txt
./uan-transits plan "WASP-77 A b" --tapir ~/Downloads/Tapir
```

Dipendenze runtime: astropy, numpy, pyerfa (+ pyerfa/pyyaml transitive). Niente
reportlab, niente database, niente web app.

## Uso

```bash
uan-transits plan "WASP-77 A b" "CoRoT-11 b"                 # default: oggi, 365 giorni, Capodimonte
uan-transits plan --targets targets.txt --days 365           # lista target da file (1 per riga)
uan-transits plan "WASP-142 b" --session-start 17:45 --session-end 01:00
uan-transits plan "HD 189733 b" --days 30 --min-altitude 25 --max-v 14 --min-depth 5
uan-transits plan "WASP-77 A b" --cache ARCHIVIO/9_ARCHIVIO_COMPLETO/dati_originali --offline
```

- Ogni esecuzione crea una **nuova cartella** `GaetanoTrovato_<timestamp>/` + ZIP in `~/Downloads`
  (mai sovrascritture).
- Gli effemeridi vengono **aggiornati dal NASA Exoplanet Archive a ogni run**:
  periodo/epoca scelti dalla stessa riga PS con BJD_TDB esplicito, minimizzando l'errore
  propagato agli estremi della finestra. Durata/fotometria con fallback documentato su PSCompPars.
- Cache solo esplicita via `--cache` (+ `--offline` per non scaricare nulla).
- Exit code: 0 ok, 2 errore o nessun target utilizzabile.

## Struttura dell'output (progressive disclosure)

```text
GaetanoTrovato_<timestamp>/
├── 0_CALENDARIO_OPERATIVO.pdf/html/csv/json   LIVELLO 1 — DECISIONE
│       "Qual è la prossima osservazione buona o ottimale?"
│       TUTTI gli eventi (PRIMA SCELTA o ALTERNATIVE) AND P1,
│       ordine cronologico globale (Europe/Rome), layout compatto.
│       Ruoli: PRIMARY/BACKUP1/BACKUP2 = le 3 raccomandazioni del target,
│       EXTRA = altra occasione valida della stessa classe (non nascosta).
│
├── 1_PRIMA_SCELTA.pdf/html                    LIVELLO 2 — FINDING
├── 2_ALTERNATIVE.pdf/html         dossier dettagliati nel FORMATO TAPIR AUTENTICO
├── 3_DA_VALUTARE.pdf/html         (aggregazione dei frammenti TAPIR originali
│       per evento, ordine cronologico, indice con anchor interni).
│       1 = tutti i PRIMA SCELTA+P1 · 2 = tutti gli ALTERNATIVE+P1
│       3 = shortlist di review per target (max 3, motivo visibile).
│       Ogni frammento è VALIDATO: target TAPIR == target planner e midpoint
│       TAPIR (colonna Start-Mid-End, convertita Europe/Rome) == mid_local
│       planner entro 120 s; mismatch → rigenerazione, secondo mismatch → errore.
│
├── 0_LEGGIMI.txt                              come leggere il pacchetto
├── 1_PRIMA_SCELTA.ics / .google_calendar.csv  export per Google Calendar (97 eventi)
└── 9_ARCHIVIO_COMPLETO/                       LIVELLO 3 — AUDIT
    ├── index.html                  tutti gli eventi, anche fuori serata e scartati
    ├── risultati.csv / .json       metriche + reason_codes di OGNI ciclo enumerato,
    │                               con eligible / exclusion_reason (TRANSIT_NOT_100)
    ├── calendario_prima_scelta.*   export machine-readable del dossier 1
    ├── 0_CALENDARIO_OPERATIVO.*    copia machine-readable della dashboard
    ├── riepilogo_target.csv/.json  vista per target: geometria, PRIMARY/BACKUP, EXTRA
    ├── manifest.json               provenance completa (vedi sotto)
    ├── dati_originali/             cataloghi NASA, frammenti TAPIR raw, sorgente planner
    └── <target>/                   tabelle TAPIR originali per target
```

**Orari:** indice e calendario in ora locale (Europe/Rome, offset esplicito);
le tabelle TAPIR incorporate sono in UTC e lo dicono. Le due fonti non si mescolano mai
senza etichetta.

## Policy UAN v2.2.0 (gerarchia rigida)

Uno score alto **non compensa mai** un problema di livello superiore. Valutazione
per evento, in ordine:

| # | Controllo | Regola |
|---|---|---|
| 0 | **Eleggibilità (v2.2)** | solo transiti con copertura **100% reale** ricalcolata da Astropy: durata non coperta ≤ 0.001 s (`transit_uncovered_seconds`, tolleranza numerica sopra il rumore float, sotto la risoluzione della griglia 120 s; nessun `round`, nessuna soglia %). Altrimenti `eligible=false`, `exclusion_reason=TRANSIT_NOT_100`, categoria archivio `NON ELEGGIBILE`: **nessuna** quality_class, logistics_class, score, ruolo o report operativo; l'evento resta in `risultati.csv/json` |
| 1 | Integrità temporale | residuo BJD > 2 s, TTV, σ centro > 10 min → `DA VALUTARE` |
| 2 | Geometria del target | quota teorica < 15° → `NON CONSIGLIATO DAL SITO` (15-20 MOLTO DIFFICILE, 20-30 MARGINALE, 30-40 BUONO, ≥40 MOLTO FAVOREVOLE) |
| 3 | Copertura transito | raggiunto solo da transiti al 100% (gate 0); le soglie storiche restano nel codice: < 90% → `DA VALUTARE`; 90-99.5% → max `ALTERNATIVE`; ≥ 99.5% → eleggibile PRIMA SCELTA |
| 4 | Baseline per lato | < 50% su un lato → `DA VALUTARE`; 50-79.9% → max `ALTERNATIVE`; ≥ 80% entrambi → eleggibile PRIMA SCELTA |
| 5 | Quota evento (assoluta) | centro < 30° → `DA VALUTARE`; centro ≥ 30° ma minimo < 30° → max `ALTERNATIVE` |
| 6 | Luna | ESTREMA → `DA VALUTARE`; ALTA/MODERATA → max `ALTERNATIVE`; BASSA → nessun downgrade |
| 7 | Logistica (separata) | P1 = transito intero in fascia operativa; P2 = parziale; P3 = fuori serata (archivio scientifico) |
| 8 | Score | solo ordinamento interno, mai promozione |

`DA VALUTARE` significa **transito completo al 100% con un altro problema da valutare**
(TTV, baseline debole, Luna ESTREMA, quota, dati mancanti), mai un transito parziale.

**Luna (solo se sopra l'orizzonte; sotto orizzonte = BASSA):**

| Rischio | Condizioni (illuminazione % / separazione °) | Effetto |
|---|---|---|
| ESTREMA | ≥90 & <40 · ≥70 & <20 · ≥40 & <10 | `DA VALUTARE` |
| ALTA | ≥80 & <60 · ≥50 & <40 · ≥20 & <20 | max `ALTERNATIVE` |
| MODERATA | ≥70 & ≤100 · ≥50 & ≤70 · ≥20 & ≤40 | max `ALTERNATIVE` |
| BASSA | tutto il resto | nessuna penalità |

La distanza può pesare più della fase: 63% a 8.5° è ESTREMA, 90% a 120° è BASSA.

**Score secondario (0-100, solo ordinamento):** 30% copertura + 20% baseline minima +
20% quota centro (saturazione a 40°) + 15% Luna (penalità continua `illum × exp(-sep/45)`) +
10% affidabilità temporale + 5% comodità oraria. **Magnitudine e profondità non entrano**
finché non esiste un profilo strumentale reale (saturazione, SNR).

**Selezione per target:** PRIMARY = miglior evento operativo (P1) per classe poi score;
BACKUP1/BACKUP2 = prossimi con diversificazione temporale (≥ 7 giorni, fallback ≥ 3),
**ma la quality_class domina sempre la separazione**: una PRIMA SCELTA a 4 giorni batte
un'ALTERNATIVE a 20. Gli altri eventi PRIMA/P1 diventano **EXTRA** nel calendario:
visibili, non nascosti.

**Copertura e baseline sono ricalcolate indipendentemente** (Astropy, intersezione
notte nautica −12° × quota ≥ 20°, griglia 120 s): le percentuali TAPIR non sono mai
usate come verità (conservate come dati originali, con scarto segnalato).

## Provenance e riproducibilità

`manifest.json` distingue esplicitamente:

- `astronomical_data` — run originale (TAPIR+Astropy), **mai ricalcolato dopo**;
- `reclassification` — applicazione offline della policy sui valori esistenti;
- `reporting` — commit git del codice che ha generato i report correnti;
- `lazy_tapir_fragments` — frammenti TAPIR generati in fase di reporting
  (solo presentazione) con mappatura evento→frammento→raw→query→UTC;
- `source_sha256` — hash di tutti i file originali;
- `source_sha256` del sorgente planner sotto `dati_originali/planner_source/`.

Rigenerare i report **non** tocca i dati astronomici: `write_reports` legge
`risultati.json` e non riesegue TAPIR/Astropy. Le query TAPIR per-evento emesse in
reporting sono solo presentazione e vengono validate in ingresso.

## Sviluppo

```bash
.venv/bin/python -m unittest discover -s .        # 52 test (exit code reale)
.venv/bin/python verify_output.py <pacchetto>     # audit di un pacchetto generato
```

`verify_output.py` verifica: gate v2.2 (ogni riga operativa è `eligible` con transito 100%,
nessun `TRANSIT_NOT_100` in calendari/dossier, esclusi tutti in archivio), enumerazione completa dei cicli (niente buchi/duplicati),
percentuali in 0-100, residuo temporale BJD, set esatti dei dossier, anchor e ID HTML
unici, **identity di ogni frammento TAPIR incorporato**, coerenza manifest.

Struttura del codice (tutto in 4 moduli):

- `planner.py` — CLI, catalogo NASA, scelta effemeridi, orchestrazione TAPIR, manifest
- `observing.py` — policy v2.2.0: gate di eleggibilità (`evaluate`), classify, moon_risk, score, finestre Astropy, analisi evento
- `reports.py` — calendari, dossier TAPIR, export ICS/CSV, riepiloghi, provenance
- `verify_output.py` — audit post-generazione di un pacchetto

## Limiti dichiarati

- Effemeridi lineari; TTV solo segnalate; covarianza epoca/periodo ed errore durata non propagati.
- Orizzonte piano, senza rifrazione; ostacoli locali e meteo non modellati.
- Griglia 120 s (non un solver di contatti); IERS distribuito con Astropy.
- Niente modello strumentale (SNR, saturazione, stelle di confronto): magnitude e
  profondità sono esposte, non usate nello score.
- Le date/quantità storiche (260/30/16) non sono obiettivi da riprodurre.

## Fonti

[TAPIR (Jensen)](https://github.com/elnjensen/Tapir) ·
[NASA Exoplanet Archive PS](https://exoplanetarchive.ipac.caltech.edu/docs/API_PS_columns.html) ·
[alias NASA](https://exoplanetarchive.ipac.caltech.edu/docs/sysaliases.html) ·
[Astropy](https://docs.astropy.org/en/stable/time/index.html) ·
coordinate sito: [INAF Capodimonte](https://www.oacn.inaf.it/come-raggiungerci/)

Le decisioni di policy e la storia delle verifiche release per release sono in
[VALIDATION.md](VALIDATION.md). La specifica originale è in [SPEC.txt](SPEC.txt).

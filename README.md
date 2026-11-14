# CtC Capture – strukturierte Erfassung historischer Geburtsakte

> **Version 1.5.1:** Für die Aktualisierung einer bestehenden Installation siehe [`UPGRADE_1_5_1.md`](UPGRADE_1_5_1.md); für alle Änderungen siehe [`CHANGELOG.md`](CHANGELOG.md). **Nie eine bestehende `data/ctc.sqlite` überschreiben.**


**CtC Capture ist die Streamlit-Implementierung innerhalb des Forschungsprojekts From Code to Code (CtC).** Das ältere Repository `codetocode` dokumentiert einen anderen Entwicklungsansatz und wird durch dieses Repository nicht ersetzt.

Kleine lokale Streamlit-Anwendung zur **manuellen quellengebundenen Erfassung** von *atti di nascita*.
Die historische Quelle kann auf Papier, auf demselben Bildschirm oder auf einem weiteren Gerät vorliegen. Ein integrierter Scan-Viewer ist nicht vorgesehen.

## Version 1.5 – Historische Vorschlagswörterbücher

Die SQLite-Datenbank erhält drei getrennt abfragbare Listen für **Vornamen, Nachnamen und Berufe**. Die Daten stammen aus vollständig gespeicherten Akten und werden bei Korrekturen fortlaufend aktualisiert. Tippe im jeweiligen RAW-Feld einen Anfang, markiere mit **↑/↓** einen Vorschlag und übernimm ihn mit **Tab**. Ohne markierten Vorschlag verlässt Tab das Feld mit dem unveränderten eigenen Wortlaut. Die Listen sind ein Lese-/Erfassungshilfsmittel, keine automatische Normalisierung.

Der Sidebar-Abschnitt „Wörterbücher“ zeigt die Anzahl der Einträge und lässt den Bestand ansehen. Intern speichert `vocabulary_entries` alle drei Kategorien mit Häufigkeiten. Unter `vocabulary_given_names`, `vocabulary_surnames` und `vocabulary_professions` stehen separate SQL-Views für Abfragen bereit.

Nach „Speichern & nächster Akt“ versucht CtC, zum Formularanfang zurückzuspringen und das erste Eingabefeld zu fokussieren. Diese neue GUI-Funktion sollte auf dem lokalen Windows-Rechner geprüft werden. Details: [`UPGRADE_1_5.md`](UPGRADE_1_5.md) und [`DATABASE_SCHEMA_1_5.md`](DATABASE_SCHEMA_1_5.md).

## Installation unter Windows (VS Code / Terminal)

1. ZIP-Datei entpacken und den enthaltenen Ordner `ctc` in VS Code öffnen.
2. Im **Terminal** (nicht in einem Jupyter-Notebook) nacheinander ausführen:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Der Browser öffnet sich üblicherweise unter `http://localhost:8501`.
Zum Stoppen: `Ctrl+C` im Terminal.

Alternativ unter macOS/Linux:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run app.py
```

## Einstieg mit der bereits erfassten Catarina Catalano

Ein kleines Test-Arbeitsblatt liegt unter `samples/ctc_capture_test.xlsx`. Diese Datei wird **nicht automatisch verändert oder importiert**.

1. Links **Excel · Import / Export** öffnen.
2. Die Datei `samples/ctc_capture_test.xlsx` auswählen und **Excel importieren** klicken.
3. Unter **Gespeicherten Akt auswählen** `NAS1875_001` öffnen.
4. Prüfen, ob Titel, Act, Declarant, Mutter, Kind und zwei Zeugen wie in der Excel-Datei erscheinen.
5. Testweise `Ba(r)ile` beibehalten, einen Zeugen ergänzen oder einen Wert ändern und speichern.
6. Erneut öffnen und kontrollieren; anschliessend den Export vorbereiten und herunterladen.

Die Datenbank liegt nach dem Start unter `data/ctc.sqlite` und bleibt beim Schliessen der App erhalten. **Vor Neuinstallation oder Überschreiben des Ordners unbedingt die Datenbank sichern.**

## Datenmodell

- `registers` – Register, einmalige Kontextangaben (`register_id`)
- `nas` – ein Akt pro Datensatz (`act_id` und `register_id`)
- `participants` – quellengebundene Referenzen mit Rolle und Sequenz (`participant_id`, `act_id`)

Referenzen innerhalb eines Aktes werden **nicht** automatisch zu historischen Personen verbunden. Eine Vaterrolle wird nicht als zweite quellengebundene Person verdoppelt, wenn derselbe Declarant als Vater erfasst wird. Die Begründung kann im Rohfeld `mother_relationship_to_declarant_raw` stehen.

### Konventionen

| Eingabe | Bedeutung |
|---|---|
| `Ba(r)ile` | Unsicher gelesener Buchstabe |
| `(Barile)` | Unsicher gelesener ganzer Name |
| `(...)rile` | Unlesbarer Anfang |
| `(???)rile` | Drei unlesbare Zeichen |
| `[Ba]rile` | Editorisch ergänzt |
| `x` | Manuell gesetzter Marker für geprüft/keine Angabe; **bei optionalen Feldern nicht erforderlich** |
| leeres Feld (Entwurf) | Nicht erfasst oder noch nicht geprüft |
| leeres optionales Feld (vollständig geprüfter Akt) | Die Angabe war in diesem Akt nicht vorhanden bzw. nicht anwendbar |

Die App normalisiert keine historischen Namen und keine Monate wie `Gennajo`, `corrente` oder Alterswörter wie `trenta`. Nur die **ausdrücklich vereinbarten** Zeitkürzel `a`/`p` werden zu `ante`/`po` ergänzt.

### Excel

Import: `Registers`, `NAS`, `Participants` (entsprechend der beigefügten Datei). Der Import geschieht als **atomarer Upsert**: gleiche technische IDs werden aktualisiert; andere bereits vorhandene Datensätze werden nicht gelöscht. Er verändert die eingelesene XLSX-Datei nicht. Die neue optionale NAS-Spalte `mother_relationship_to_declarant_raw` und `capture_status` werden akzeptiert, wenn vorhanden, ansonsten leer bzw. `draft` behandelt.

Export ab v1.3: die Standardblätter `Registers`, `NAS`, `Participants`, `TranscriptionEvents`. `NAS` enthält `source_url`, `image_number`, `image_total`. Bei Akten über mehrere Aufnahmen kommt `AdditionalImages` hinzu. Die internen SQLite-Tabellen für Bildreferenzen bleiben bestehen. Alte v1.2-Excel-Dateien mit `SourceImages` und `ActImages` können weiterhin importiert werden.

### Validierung und Speichern

- SQLite-Fremdschlüssel verhindern Teilnehmer ohne Akt und Akte ohne Register.
- Akt plus Personen werden transaktional gespeichert.
- Vorhandene `participant_id` bleiben beim Bearbeiten stabil.
- `Save & Next` bewahrt das Register und schlägt bei numerischer Aktnummer die nächste Nummer vor.
- **Entwurf speichern** benötigt vorläufig eine Aktnummer; vollständig gekennzeichnete Akte zusätzlich die wichtigsten Personenrollen und die angegebenen Vornamen.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Die Python-Tests decken SQLite, Relationen, Rollensequenzen, Mehrfachzeugen, ID-Stabilität, Bearbeitung, Transaktionen und Excel-Roundtrip ab. **Tastaturfokus, tatsächliche Tab-Reihenfolge und Reaktionszeit** müssen zusätzlich manuell in Streamlit auf Windows überprüft werden; ein reiner Python-Test kann sie nicht bestätigen.

## Grenzen des Prototyps

- Nur NAS-Oberfläche; MAT und MOR sind für eine spätere Version vorgesehen. Die historischen Originalvorlagen werden nicht im öffentlichen Repository gespeichert.
- Kein OCR, keine Normalisierung, kein Record Linkage, keine Signaturen.
- Noch kein automatisches Speichern ungesicherter Texte; **Browser neu laden kann ungespeicherte Eingaben verwerfen**. Vor längeren Pausen Entwurf speichern.
- Beim Hinzufügen von Zeugen oder Umschalten bedingter Vaterfelder kann sich der Tastaturfokus ändern. Das muss im praktischen Erfassungsversuch beurteilt werden.
- Textfelder sind zur Ergonomie teilweise auf die üblichen Angaben zugeschnitten; weitere bereits vorhandene `participants`-Spalten bleiben im Datenmodell erhalten.
- Für einen produktiven Langzeitbetrieb bleiben unabhängige SQLite-Backups wichtig. Speichervorgänge werden seit v1.2 in `transcription_events` protokolliert; dies ist kein manipulationssicheres Archiv.

## Technische Struktur

```text
ctc/
  app.py                 # Streamlit-Oberfläche
  database.py            # SQLite, Transaktionen, IDs
  models.py              # Capture-Spalten, Rollen, IDs
  excel_io.py            # Excel-Import/Export
  validation.py          # Prüfregeln, Pandas-Report
  samples/               # Beispiel-Excel für Tests
  tests/                 # pytest
  data/                  # SQLite-Datei nach Programmstart
```

**Prinzip:** Ein historischer Akt → ein Erfassungsvorgang → ein kohärenter Speichervorgang.

---

## Update auf v1.2 – Provenienz und FamilySearch-Aufnahmen

Bitte zuerst `UPGRADE_1_2.md` lesen. Die App migriert beim ersten Start ein bestehendes v1.1-SQLite-Schema und legt vorher automatisch `data/ctc.pre_v1_2.sqlite` an; dennoch **vorher selbst sichern**.

Zusätzlich zur bisherigen NAS-Erfassung gibt es:

- **Zeugen:** individueller Wohnort nur in „Weitere Zeugenangaben“; Standardgemeinde wird aus der innerhalb des Akts genannten Gemeinde und dem Wortlaut `in questo comune` semantisch aufgelöst. Die View `witness_domicile_resolved` zeigt resolved values plus Auflösungsgrund; historische Rohzeichen bleiben unverändert.
- **Quellenbilder:** `source_images` und `act_images` stellen eine n:m-Beziehung zwischen Aufnahmen und Geburtsakten her; eine FamilySearch-Aufnahme kann viele Akte enthalten und ein Akt mehrere Aufnahmen umfassen.
- **Transkriptionsmetadaten:** Name, erste Speicherung/letzte Speicherung in UTC, Akten-Lesbarkeit 1–5, quellenkritische Notiz, Sitzungsnotiz; gespeicherte Änderungen sind über `transcription_events` nachvollziehbar.
- **Excel:** `Registers`, `NAS`, `Participants`, `SourceImages`, `ActImages`, `TranscriptionEvents`. Alte Drei-Blatt-Arbeitsmappen bleiben importierbar.

### Die neuen SQLite-Objekte

```text
registers             (bestehend)
nas                   (um 6 Metadaten-Spalten erweitert)
participants          (bestehend)
source_images         (neue, wiederverwendbare Bilddatensätze)
act_images            (n:m-Verknüpfung Akt–Aufnahme)
transcription_events  (append-only Speicherprotokoll)
app_settings          (zuletzt benutzte transkribierende Person)
witness_domicile_resolved (SQL-View; berechnete Wohnortauflösung)
```

**Achtung:** `act_comune_raw`, die gedruckte Formel und der daraus abgeleitete Wohnort sind unterschiedliche semantische Ebenen. Ein als `domicile_raw` gespeicherter individueller Ortsname erhält Vorrang vor der allgemeinen Formel. Die Ansicht löst keine historisch unbelegten Personenidentitäten auf.

---

## Update auf v1.3 – Quellennahe Ergonomie und vereinfachte Referenzen

**Bitte `UPGRADE_1_3.md` lesen.** Die SQLite-Tabellen bleiben kompatibel; die Anwendung ergänzt lediglich eine SQL-View für den abgeleiteten Wohnort von Dichiarante und separat erwähntem Vater.

- Neuer NAS-Akt: Registerjahr und zuletzt neu erfassten Beurkundungsmonat vorschlagen.
- Dichiarante: `di/fu`, Vatername und Alterseinheit unter „Weitere Angaben“; Wohnort aus Akten-Gemeinde vorschlagen, Abweichung überschreibbar.
- Zeugen: Alter und Beruf in einer Zeile.
- `a` oder `p` + Tab als Kurzschreibweise für `ante` / `po`.
- FamilySearch: URL und „Aufnahme Nr. von Gesamtzahl“ direkt sichtbar; Mehrfachaufnahmen optional.
- Excel: Quellenreferenz im NAS-Blatt statt in zwei separaten Bildblättern; Mehrfachaufnahmen im Blatt `AdditionalImages`.
- Optionale Felder dürfen bei vollständig geprüften Akten leer bleiben. Die Prüfhilfe für häufig erwartete Felder ist einsehbar, aber erzwingt keine pauschale `x`-Füllung.

Siehe auch `DATABASE_SCHEMA_1_3.md` und `CHANGELOG.md`.

### CtC 1.4: Dauer der manuellen Erfassung

Seit 1.4 speichert CtC den Beginn eines neuen NAS-Aktes sowie den Zeitpunkt der ersten **vollständigen** Speicherung. Die Zeitdifferenz in Sekunden wird im Blatt `NAS` des Excel-Exports verfügbar gemacht (`capture_started_at_utc`, `capture_saved_at_utc`, `capture_duration_seconds`). Entwürfe besitzen bis zum Abschluss keine gemessene Dauer. Bestehende Akte aus früheren Versionen behalten leere Zeitmessfelder; spätere Korrekturen verändern eine bereits gemessene Dauer nicht. Zeitangaben enthalten UTC-Zeitzoneninformationen. Gemessen wird die verstrichene Uhrzeit einschliesslich Recherche und Pausen.

Vor Update auf einem bestehenden Rechner die SQLite-Datei extern sichern; siehe `UPGRADE_1_4.md`.
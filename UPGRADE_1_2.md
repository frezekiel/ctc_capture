# CtC v1.2 – Sicheres Update einer bestehenden Windows-Installation

**Ausgangspunkt:** funktionierende CtC-v1.1-Installation im Ordner `ctc`, inklusive `data/ctc.sqlite` und `.venv`.

## 1. CtC beenden und Datenbank sichern

1. Im PowerShell-Terminal, in dem Streamlit läuft: **Ctrl+C**.
2. Im bisherigen Ordner `ctc` den Unterordner `data` öffnen.
3. Die Datei **`ctc.sqlite`** an einen **anderen sicheren Ort** kopieren, beispielsweise als `ctc_backup_v1_1_2026-11-14.sqlite`. Bei OneDrive-Synchronisierung idealerweise auch auf ein zweites Medium.
4. Sicherstellen, dass die Sicherung tatsächlich vorhanden ist. Nicht nur den Excel-Export sichern.

## 2. Die Programmdateien aktualisieren

1. `ctc_update_v1_2.zip` **entpacken**.
2. Die Dateien aus seinem Unterordner **`ctc`** in den **bereits vorhandenen `ctc`-Programmordner** kopieren, in dem `app.py` liegt.
3. Bei gleichnamigen Programmdateien **„Dateien im Ziel ersetzen“** bestätigen.
4. **`data` und `.venv` nicht löschen, verschieben, entpacken oder ersetzen.** Sie sind im Update-Paket absichtlich nicht enthalten.
5. Die vorhandene SQLite-Datei nicht aus einer alten ZIP oder einem Excel-Export neu erstellen.

## 3. CtC starten und die Schema-Migration prüfen

Im geöffneten `ctc`-Ordner PowerShell starten:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

**Beim ersten Start** erkennt CtC die alte Datenbankstruktur. Bevor Tabellen geändert werden, erzeugt das Programm automatisch `data/ctc.pre_v1_2.sqlite` als SQLite-konsistente Momentaufnahme. Danach ergänzt es die neuen Metadaten-Spalten, die Protokoll- und Bildtabellen sowie die Wohnort-View. Alte Datensätze werden **nicht** automatisch als von einer bestimmten Person transkribiert oder nachträglich datiert.

**Kontrolle:** Im Menü „Gespeicherten Akt auswählen“ müssen weiterhin die bisherigen Akte zu sehen sein (bei deinem letzten Export waren es `NAS1875_001`, `NAS1875_002` und `NAS1875_003`). Öffne einen alten Akt, überprüfe Namen, Zeugen, den Status und die Quellenangaben. Ein **neuer Excel-Import ist nicht erforderlich**.

## 4. Version 1.2 testen

1. Einen neuen NAS-Akt beginnen. Im Abschnitt „8 · Testimoni“ müssen Wohnort-Eingaben aus dem Standard-Durchlauf verschwunden sein.
2. „Weitere Zeugenangaben“ öffnen: Dort erscheint die Gemeinde aus der Aktenformel als vorbelegter Wohnort. Eine ausdrücklich andere Gemeinde lässt sich überschreiben.
3. Nach „9 · Bild- und Quellenreferenzen“ bei Bedarf eine FamilySearch-Aufnahme (z. B. `228` von `1536`) und einen Link hinterlegen.
4. Unter „10 · Transkriptionsmetadaten und Quellenkritik“ **einmal den Namen** eintragen, die Handschrift mit 1–5 bewerten und gegebenenfalls eine editorische Bemerkung schreiben.
5. Speichern. Der Name wird bei neu begonnenen Akten vorgeschlagen. Die gespeicherten UTC-Zeitpunkte und Bearbeitungsereignisse sind unter den Metadaten sichtbar.
6. Excel-Kopie herunterladen. Sie hat jetzt **sechs Blätter**: `Registers`, `NAS`, `Participants`, `SourceImages`, `ActImages`, `TranscriptionEvents`.

**Hinweis zur Lesbarkeit:** `1 = sehr gut`, `2 = gut`, `3 = mittel`, `4 = schwierig`, `5 = sehr schwierig / weitgehend unleserlich`. Bewertung pro Akt. Unbewertete Altbestände bleiben leer.

**Hinweis zum Zeitstempel:** `transcribed_at_utc` bezeichnet die **erste Speicherung in CtC**, nicht den Beginn des Lesevorgangs. `updated_at_utc` bezeichnet die letzte Speicherung. Die Zeitangaben sind in UTC.

## 5. Tests (optional)

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Die Entwicklerumgebung bestand 37 automatisierte Tests. Die realen Klicks/Tab-Stopps unter deinem Windows-Browser müssen noch praktisch kontrolliert werden.

## Rückkehr zur alten Version

1. CtC beenden.
2. Die bisherigen v1.1-Programmdateien aus deiner Sicherung zurückkopieren.
3. Wenn auch der alte **Datenbankstand** wiederhergestellt werden soll, die gesicherte v1.1-SQLite-Datei als `data/ctc.sqlite` zurückkopieren (vorher die neue Version an anderer Stelle sichern!). Änderungen, die nach dem Update erfasst wurden, sind **nicht** im alten Backup enthalten.

Das Upgrade-Paket enthält **weder `ctc.sqlite` noch `.venv`** und überschreibt diese Dateien nicht.

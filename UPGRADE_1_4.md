# CtC 1.4 – Update-Anleitung (Windows)

**Ziel:** Eine automatische, quellenunabhängige Zeitmessung für die manuelle Erfassung von NAS-Akten. Das Update enthält den konsolidierten Code aus CtC 1.3 und 1.4 und kann direkt auf einer bestehenden Installation **1.2 oder 1.3** eingespielt werden. MAT/MOR und Record Linkage sind **nicht** enthalten.

## 1. Vor dem Update: Sicherheitskopie

1. CtC/Streamlit im PowerShell-Fenster mit **Strg+C** beenden.
2. Die derzeitige Datenbank `ctc/data/ctc.sqlite` **aus dem Projektordner heraus an einen zweiten Ort kopieren**.
3. Die funktionierenden v1.3-Programmdateien als Rückfallversion aufbewahren.
4. Einen aktuellen Excel-Export behalten (ergänzend, nicht anstelle des Datenbank-Backups).

## 2. Programm aktualisieren

1. `ctc_update_v1_4.zip` entpacken.
2. **Nur die enthaltenen Dateien** aus dem Ordner `ctc` in deinen bestehenden Arbeitsordner `ctc` (wo `app.py` liegt) kopieren; gleiche Dateien ersetzen.
3. **`data` und `.venv` nicht löschen oder ersetzen.** Das Update-Paket enthält bewusst keine Forschungsdatenbank.
4. PowerShell im Projektordner starten:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Beim ersten Start erweitert CtC die NAS-Tabelle automatisch um drei Spalten. **Vorher erstellt das Programm eine SQLite-konsistente Kopie unter `data/ctc.pre_v1_4.sqlite`.** Sie wird bei späteren Starts nicht überschrieben. Diese interne Kopie ersetzt nicht die manuelle Sicherung.

## 3. Was und wie wird gemessen?

| Datenbankfeld (NAS) | Bedeutung |
| --- | --- |
| `capture_started_at_utc` | Beginn: wenn ein neuer Akt in der Streamlit-Maske geöffnet wird |
| `capture_saved_at_utc` | Erster erfolgreicher Abschluss: «Als vollständig speichern» oder «Speichern & nächster Akt» |
| `capture_duration_seconds` | Verstrichene Sekunden zwischen diesen beiden Zeitpunkten |

**Entwürfe:** «Entwurf speichern» bewahrt den Beginn, erzeugt aber noch **keine** abgeschlossene Dauer. Der erste spätere vollständige Speichervorgang schliesst die Messung ab. **Korrekturen** an einem vollständig gespeicherten Akt verändern die drei Werte nicht.

**Altbestand:** Die sechs vor Version 1.4 erfassten Geburtsakte erhalten keine nachträglich geschätzten Messzeiten. Auch nach einer späteren Korrektur bleiben die Zeitmessfelder leer, falls der Start damals nicht gemessen wurde. Bereits vorhandene `transcribed_at_utc`/`updated_at_utc` bleiben erhalten und behalten ihre bisherige Bedeutung.

Die Dauer bezeichnet **verstrichene Uhrzeit**, nicht aktive Maus-/Tastaturzeit. Nachnamensrecherchen, Unterbrechungen, längere Pausen sowie – bei zwischengespeicherten Entwürfen – auch die Zeit bis zum Wiederaufnehmen können darin enthalten sein. Für belastbare Vergleiche mit 50/100/500 Akten sollte man solche Fälle bei der Auswertung kenntlich machen oder ausschliessen. Starte einen *neuen* Akt daher am besten unmittelbar vor der tatsächlichen Transkription.

Die Zeitstempel werden mit UTC-Zoneninformation gespeichert; dadurch werden Zeitzonen und Sommerzeit eindeutig behandelt.

## 4. Test nach Installation

1. Prüfe, ob im Seitenmenü **v1.4** angezeigt wird.
2. Kontrolliere, ob die bisherigen sechs Akte unverändert vorhanden sind.
3. Öffne einen **neuen** NAS-Akt; unter «Transkriptionsmetadaten und Quellenkritik» erscheint der Erfassungsbeginn.
4. Erfasse einen Akt und klicke auf **«Speichern & nächster Akt»**. Beim späteren Öffnen des abgeschlossenen Akts wird die Dauer in Minuten und Sekunden angezeigt.
5. Korrigiere diesen Akt und speichere erneut; die ursprüngliche Dauer muss gleich bleiben.
6. Exportiere eine Excel-Kopie. Im NAS-Blatt stehen die drei neuen Zeitspalten. Bei älteren Akten bleiben sie leer.

Optional alle Tests ausführen:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Falls eine Fehlermeldung erscheint: keine Daten erneut importieren. Zunächst PowerShell-Meldung sichern und Datenbank-Backup unverändert aufbewahren.

## 5. Technischer Teststatus

- **51 Python-Tests bestanden**, darunter 7 neue Timing-/Migrationstests. Eine direkte Migration von 1.2 auf 1.4 wurde zusätzlich geprüft.
- Die echte Excel-Datei vom 14.11.2026 (2 Register, 6 NAS, 36 Teilnehmerpositionen, 5 Bearbeitungsereignisse) wurde mit unveränderten 1.3-Dateien in einer Testdatenbank importiert und anschließend auf 1.4 migriert: Integritätsprüfung OK, keine fehlerhaften Fremdschlüssel, Zeilen und Transkriptionsdaten unverändert. Ein Excel-Rückimport mit 1.4 war erfolgreich.
- Der Browserbetrieb unter Windows und die tatsächliche Zeitmessung in einer realen lokalen Streamlit-Sitzung konnten hier nicht live beobachtet werden.

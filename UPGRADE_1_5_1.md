# CtC 1.5.1 – kleiner Fehlerfix für den Ehefrau-Default

1. Streamlit mit Ctrl+C beenden.
2. Eine Kopie von `data/ctc.sqlite` ausserhalb des Projektordners sichern.
3. Den Inhalt des Update-Ordners `ctc` in deinen vorhandenen Ordner `ctc` kopieren und die geänderten Python-Dateien ersetzen. `data/` und `.venv/` nicht anfassen.
4. Start: `.\.venv\Scripts\python.exe -m streamlit run app.py`
5. **Neuen NAS-Akt** öffnen; das Feld „Beziehung zum Declarant (Wortlaut)“ sollte nun mit tatsächlichem schwarzem Eingabewert `sua moglie seco lui convivente` vorbelegt sein. Speichern und im Excel-Blatt NAS kontrollieren.

Bereits gespeicherte ältere Akte mit leeren Angaben bleiben absichtlich leer. Diese dürfen nur nach Quellenkontrolle berichtigt werden. Der Default ist ein Vorschlag aus der Druckvorlage und muss bei nicht zutreffender Formulierung angepasst oder gelöscht werden.

Kein Datenbankschema-Update; alle Änderungen aus 1.5 bleiben enthalten.

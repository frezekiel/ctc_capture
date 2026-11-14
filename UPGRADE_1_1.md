# CtC v1.1 – Update der vorhandenen Installation (Windows)

**Wichtig: Die vorhandene SQLite-Forschungsdatenbank bleibt bestehen.**
Dieses Update verändert keine bestehenden Tabellen/Spalten. In den ZIP-Dateien ist **keine** `ctc.sqlite` enthalten.

## Empfohlen: kleines Update-Paket

1. CtC im PowerShell-Terminal mit `Ctrl+C` beenden. Die App im Browser schliessen.
2. Im Windows-Explorer den bisherigen Projektordner **`ctc`** öffnen – dort liegen `app.py`, `models.py`, `database.py` und der Unterordner `data`.
3. Vor dem Update **`data/ctc.sqlite` separat sichern** (Datei kopieren, etwa nach `ctc_backup_2026-11-14.sqlite`, idealerweise zusätzlich ausserhalb des Projektordners). Falls keine Datei vorhanden ist, wurde in diesem Projektordner noch keine SQLite-Datenbank erzeugt.
4. `ctc_update_v1_1.zip` entpacken. Die darin enthaltenen Dateien und Ordner **in den bestehenden `ctc`-Ordner kopieren** und vorhandene gleichnamige Dateien ersetzen. Insbesondere `app.py`, `database.py` und `excel_io.py` ersetzen; die neue `capture_defaults.py` hinzufügen.
5. **Nichts aus dem vorhandenen Ordner `data` löschen oder ersetzen.** Den ganzen Projektordner nicht neu anlegen.
6. CtC wie bisher starten, z. B. in einem PowerShell-Terminal im `ctc`-Ordner:

   ```powershell
   .\.venv\Scripts\python.exe -m streamlit run app.py
   ```

7. Einen existierenden Akt öffnen und prüfen. Danach einen **neuen** Akt starten: die Gemeinde sollte aus dem Register stammen, der Sindaco aus dem vorherigen Akt und die kollektive Zeugenformel vorbelegt sein.

## Technische Prüfungen (optional)

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Wenn die virtuelle Umgebung im CtC-Ordner noch nicht installiert ist, die bisherige Startanleitung aus `README.md` verwenden. Bei einem normalen Update muss weder Python noch die virtuelle Umgebung neu installiert werden.

## Was das Update nicht tut

- Kein Import ist nötig: Bestehende Daten bleiben in `data/ctc.sqlite`.
- Bestehende Akte werden beim Öffnen **nicht nachträglich** mit Defaults überschrieben.
- Kein neues SQLite-Schema und keine MAT/MOR-Maske.
- FamilySearch-Link, Aufnahme-/Bildnummer und Mehrfachbilder pro Akt sind weiterhin für v1.2 geplant.
- Die tatsächliche Tab-Fokus-Reihenfolge muss auf deinem Windows-Rechner im Browser getestet werden; automatisierte Python-Tests können den Browserfokus nicht belegen.

## Rückkehr zu v1.0

CtC schliessen und die gesicherten v1.0-Python-Dateien zurückkopieren. Die `ctc.sqlite` wird bei diesem UI-Update nicht verändert, abgesehen von normal von dir gespeicherten Transkriptionen.

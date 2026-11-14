# CtC 1.5 – Update-Anleitung (Windows)

**Ziel:** Autovervollständigung für historische Vornamen, Nachnamen und Berufe mit Pfeiltasten und Tab, drei persistierten Vorschlagslisten in SQLite und Rücksprung zum Formularanfang nach „Speichern & nächster Akt“.

Das Update ist **kumulativ ab CtC 1.2, 1.3 oder 1.4**. Die vorhandenen Funktionen (Transkriptionsmetadaten, Quellenreferenzen und Erfassungszeitmessung) sind weiterhin enthalten. MAT/MOR und Record Linkage sind nicht Bestandteil dieser Version.

## Vor dem Update

1. In PowerShell **Strg+C** zum Beenden von Streamlit drücken.
2. Die **echte** Forschungsdatenbank `ctc/data/ctc.sqlite` separat ausserhalb des Projektordners sichern (nicht bloss eine Excel-Kopie).
3. Das funktionierende Vorgängerprojekt oder die ZIP-Datei aufbewahren.
4. Empfehlung: Zusätzlich den letzten Excel-Export archivieren.

## Installation

1. `ctc_update_v1_5.zip` entpacken.
2. Den **Inhalt des darin enthaltenen Ordners `ctc`** in den vorhandenen Arbeitsordner `ctc` kopieren; gleichnamige **Programmdateien** ersetzen.
3. Die lokalen Ordner **`data/`** und **`.venv/`** weder löschen noch ersetzen. Im Update ist keine Forschungsdatenbank enthalten.
4. Wegen des neuen Streamlit-Komponenten-APIs einmal die Abhängigkeiten aktualisieren (die bestehende virtuelle Umgebung bleibt erhalten):

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

5. Wie gewohnt starten:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Die App verlangt für die neue Autovervollständigung **Streamlit 1.58 oder neuer**. Das bisher verwendete Streamlit 1.67 erfüllt diese Voraussetzung. Beim ersten Start ergänzt CtC die SQLite-Tabelle `vocabulary_entries` und die drei lesbaren Views. Vor der Änderung erstellt CtC eine transaktionskonsistente Sicherung unter **`data/ctc.pre_v1_5.sqlite`**. Bereits vorhandene Sicherungen werden nicht überschrieben.

## Die drei Listen in SQLite

Die **physische Tabelle** `vocabulary_entries` speichert die Rohschreibweise, Kategorie und Anzahl der Personenreferenzen, in denen sie vorkommt. Die SQL-Views `vocabulary_given_names`, `vocabulary_surnames` und `vocabulary_professions` erlauben drei separate Listenabfragen. Es werden ausschliesslich **vollständig gespeicherte** Akte ausgewertet. Zusätzliche Quellen-Nennungen derselben Person (Titel und Haupttext mit gleichem Wortlaut) zählen nur einmal pro Teilnehmerreferenz. Unsichere Lesungen mit `(...)` oder `[...]`, sowie die Platzhalter `x`/`q`, erscheinen nicht als automatische Vorschläge.

- Beim Speichern oder Importieren wird der Vorschlagsindex aus aktuellen Daten neu aufgebaut. Eine korrigierte Lesung bleibt also nicht irrtümlich als Vorschlag bestehen.
- `Giovanni`, `Gio.` und `Giovan` werden **nicht** stillschweigend normiert oder zu einer Personenidentität zusammengeführt.
- Die Tabellen sind ein Hilfsmittel zur Texterfassung, **keine** historische Normalisierungs- oder Identitätstabelle.
- Ein Excel-Export enthält weiterhin die historischen Haupttabellen. Der Vorschlagsindex lässt sich jederzeit daraus neu aufbauen und wird deshalb nicht als eigene zusätzliche Excel-Tabelle exportiert.

## Tastaturtest

1. Öffne einen neuen Akt. Klicke in „Vorname (raw)“ und tippe den Anfang eines bereits im Korpus vorkommenden Namens (z. B. `Giu`).
2. Die Vorschlagsliste soll erscheinen; mit **Pfeil unten/oben** navigieren.
3. **Tab** übernimmt nur einen durch die Pfeiltasten markierten Vorschlag und springt zum nächsten Feld. Ohne Markierung wird dein genau getippter Wortlaut gespeichert und Tab springt ebenfalls weiter.
4. Ein nicht bekannter Name darf frei eingetragen werden; die App ergänzt nichts gegen deinen Willen.
5. Teste das gleiche Verhalten bei Nachnamen und Berufen sowie beim zweiten Zeugen.
6. Teste anschliessend „Speichern & nächster Akt“: Die Ansicht soll automatisch zum Formularanfang zurückkehren und den Fokus auf „Numero“ setzen.
7. Korrigiere zum Test einen vollständig gespeicherten Namen, speichere erneut und kontrolliere im Seitenmenü unter „Wörterbücher“, ob die alte, nun nicht mehr belegte Variante aus der Liste entfernt wurde.

## Technischer Teststatus

- **60 automatisierte Python-Tests bestanden**, einschliesslich der 51 bisherigen Tests sowie 9 neuer Tests zur Wörterbuchverwaltung.
- Die echte Datei `ctc_capture_2026-11-14_155303.xlsx` wurde in eine v1.4-Testdatenbank importiert und dann auf 1.5 migriert: **2 Register, 11 Geburtsakte, 66 Personenreferenzen**; SQLite-Integritätsprüfung `ok`, keine ungültigen Fremdschlüssel. Neu aufgebaut: 30 Vornamen-, 27 Nachnamen- und 12 Berufseinträge.
- Der JavaScript-Tastaturvertrag wurde separat mit Node geprüft (Pfeiltasten, Tab ohne `preventDefault`, freiwillige Übernahme, freier Rohwert).
- **Nicht live getestet:** Streamlit-Browser unter Windows, tatsächliches Fokus-/Rerun-Verhalten und Scrollposition. Diese Punkte unbedingt mit der lokalen Anwendung prüfen. Wenn das Tastaturverhalten stört, nicht weiter in der App erfassen, sondern Screenshot und PowerShell-Meldung zur gezielten Korrektur sichern.

Die Update-Dateien umfassen keine Forschungsdatenbank und können die Originaldatei nicht beim Entpacken überschreiben. Bei einer Fehlermeldung keine alten Daten erneut importieren, bevor die betroffene Datenbankdatei geklärt ist.

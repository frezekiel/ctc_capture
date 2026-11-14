# CtC v1.3 – Upgrade einer bestehenden Windows-Installation

**Voraussetzung:** CtC 1.2 läuft lokal in deinem Ordner `ctc`. Diese Version ist weiterhin **NAS-only**.

## 1. Vorher: Programm beenden und Forschungsdaten sichern

1. Streamlit im PowerShell-Fenster mit **Strg+C** beenden.
2. **`ctc/data/ctc.sqlite` an einen anderen Ort kopieren**, z. B. `ctc_backup_v1_2_2026-11-14.sqlite`. Kontrollieren, ob sich diese Kopie tatsächlich öffnen liesse; mindestens Dateigrösse prüfen.
3. Das bisher funktionierende Projekt (insbesondere Python-Dateien) separat sichern, z. B. als ZIP.
4. Einen aktuellen Excel-Export aufbewahren, aber **nicht** als Ersatz für das SQLite-Backup betrachten.

## 2. Dateien ersetzen

1. `ctc_update_v1_3.zip` herunterladen und **entpacken**.
2. Den Inhalt seines Unterordners `ctc` in **deinen bestehenden Ordner `ctc` mit `app.py`** kopieren; gleichnamige Dateien ersetzen.
3. Die vorhandenen Ordner **`data` und `.venv` unverändert lassen**. Im Update sind diese absichtlich nicht enthalten.
4. Die alte ZIP-Datei im Programmordner kannst du unabhängig davon als Archiv liegen lassen.

## 3. Start

In PowerShell im bestehenden `ctc`-Ordner:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Es sind keine zusätzlichen Python-Abhängigkeiten nötig. Die SQLite-Tabellen bleiben kompatibel; CtC ergänzt beim Start eine **berechnete SQL-View**, keine neue Pflichtspalte. Bestehende Transkriptionen werden **nicht** neu geschrieben. Eine automatische zusätzliche Sicherung ist für 1.3 nicht vorgesehen, weil das Tabellenschema nicht geändert wird. Die bestehende v1.2-Migrationssicherung bleibt vorhanden.

## 4. Nach dem Start gezielt prüfen

1. Im Menü müssen weiterhin alle bisherigen NAS-Akte erscheinen (letzter bereitgestellter Export: **2 Register, 6 NAS-Akte, 36 Personenpositionen**). Bereits gespeicherte Akte öffnen und Namen, Rohwerte und Notizen stichprobenartig vergleichen.
2. **Neuen NAS-Akt im Register Girifalco 1875 anlegen:** `Jahr = 1875`; der letzte gespeicherte Erfassungsmonat wird angeboten. `Tag` bleibt leer.
3. **Dichiarante:** Tabfolge durch Vor-/Nachnamen, Alter, Beruf und Gemeinde testen. `di/fu`, Vatername und `anni` liegen unter „Weitere Angaben“. Die Gemeinde ist ein **editierbarer Vorschlag**. Unveränderte Vorschläge werden als erschlossene Gemeinde ausgewiesen und **nicht** stillschweigend nach `domicile_raw` geschrieben.
4. **Zeugen:** Alter und Beruf stehen in derselben Zeile. Individuelle Abweichungen des Wohnorts können im Zusatzbereich erfasst werden.
5. **Zeitangaben:** In den Feldern zur Beurkundungs- und Geburtszeit nur `a` oder `p` eintippen und mit **Tab** weitergehen; das gespeicherte Feld muss `ante` bzw. `po` enthalten.
6. **Quellenreferenz:** Im sichtbaren Abschnitt 9 eine FamilySearch-URL und „Aufnahme Nr. / Aufnahmen insgesamt“ erfassen. Bei mehreren Bildern kann eine Zusatzaufnahme geöffnet werden.
7. **Excel-Kopie:** Im Blatt `NAS` stehen `source_url`, `image_number`, `image_total`; die beiden internen Bildtabellen werden nicht mehr als eigenständige Blätter exportiert. Falls ein Akt **mehr als eine Aufnahme** hat, erscheint zusätzlich das Blatt `AdditionalImages`.
8. **Vollständigkeitsprüfung:** Neben dem Speichern gibt es eine ausklappbare Prüfhilfe für häufig erwartete Felder. **Leere optionale Felder müssen nicht mit `x` markiert werden.** Entwürfe dürfen unvollständig sein.

**Wichtig:** „Speichern & nächster Akt“ übernimmt den Monat und die letzte Aufnahme aus dem **gerade gespeicherten Akt**. „Neuer NAS-Akt“ verwendet die Werte des **zuletzt neu angelegten Akts im aktiven Register**. Ändert man einen alten Akt, ändert dies nicht unbemerkt die Vorschläge für neue Akte.

## 5. Tests und Grenzen

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Es bestehen **44 automatisierte Python-Tests**, einschliesslich des sechs Akte umfassenden Exports und eines vollständigen Excel-Rückimports. Der tatsächliche Tastatur-Fokus und das Verhalten des Webbrowsers müssen lokal überprüft werden; sie lassen sich durch Python-Unit-Tests allein nicht belegen.

**Nicht Teil von 1.3:** 1809er Formularprofile, MAT/MOR, Normalisierung, Record Linkage und automatische Erfassung der handschriftlichen Jahresendung `cinque`.

## 6. Rollback

CtC beenden, die gesicherten bisherigen Python-Dateien zurückkopieren. **Die SQLite-Datei nicht zurücksetzen**, wenn du nach der Aktualisierung neue Transkriptionen speichern möchtest. Falls eine Wiederherstellung nötig ist: zuerst eine Kopie der aktuellen Datei sichern, danach die v1.2-Sicherung bewusst zurückspielen (alle später erfassten Akte wären sonst nicht darin vorhanden).

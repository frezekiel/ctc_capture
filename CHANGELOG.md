## 1.5.1 – Korrektur der vorbelegten Ehefrau-Formel (14.11.2026)

- In neuen NAS-Akten wird `mother_relationship_to_declarant_raw` jetzt mit dem tatsächlichen, editierbaren Wert `sua moglie seco lui convivente` initialisiert. In 1.5 war die Formel lediglich ein Streamlit-Placeholder, weshalb Excel/SQLite bei unverändertem Feld leer blieben.
- Die Formulierung wird ohne zusätzliche Interaktion auch bei unverändertem Feld gespeichert. Bei anderer oder fehlender Quellenformulierung muss sie aktiv geändert oder gelöscht werden.
- Beim Laden bestehender Akte werden leere Angaben **nicht** automatisch überschrieben oder rückwirkend aufgefüllt.
- Keine Schema-Migration, keine Abhängigkeitsänderungen. Zusätzliche Regressionstests.

# CtC – Änderungsprotokoll

## v1.5 – Wörterbücher und Navigation (14.11.2026)

- Neue SQLite-Tabelle `vocabulary_entries` mit drei Kategorien `given_name`, `surname`, `profession`, getrennten SQL-Views und Häufigkeiten. Vorschläge entstehen aus abgeschlossenen Akten; vorhandene Rohdaten bleiben unverändert.
- Gleiche Name-Nennung im Titel/Haupttext einer Personenreferenz zählt nur einmal. Unsichere oder editorisch ergänzte Rohwerte sowie `x`/`q` werden nicht als geprüfte Vorschläge aufgenommen.
- Index wird atomar mit jedem Speichern beziehungsweise Excel-Import aktualisiert. Ein korrigierter Name oder Beruf verschwindet bei fehlenden anderen Belegen aus der Vorschlagsliste.
- Neues tastaturorientiertes Streamlit-Components-v2-Eingabefeld: Tippen → ↑/↓ zur aktiven Auswahl → Tab übernimmt und wechselt zum nächsten Feld. Ohne explizite Auswahl bleibt der freie RAW-Wert erhalten. Keine Maus oder Enter-Taste notwendig.
- Nach erfolgreichem „Speichern & nächster Akt“ einmaliger Rücksprung zur Eingabe am Formularanfang mit Fokussierungsversuch auf Numero.
- Seitenmenü mit Eintragszahlen und Einsicht in die drei Wörterbücher.
- Automatische Sicherung `data/ctc.pre_v1_5.sqlite` vor der neuen Schema-Tabelle. Aktualisiertes `requirements.txt`: Streamlit 1.58 oder neuer (Components v2).
- **60 Python-Tests bestanden** (51 bestehende + 9 neue). Upgrade-Test mit 11 echten NAS-Akten / 66 Positionen bestanden. JavaScript-Pfeil-/Tab-Logik separat geprüft. Windows-Browserlauf weiterhin vom Anwender zu verifizieren.


## v1.3 – Ergonomie, Quellenreferenzen und konservative Datenqualität (14.11.2026)

- **Beurkundung:** Bei einem neuen NAS-Akt `act_year_raw` aus dem aktiven Register und `act_month_raw` aus dem zuletzt neu angelegten Akt desselben Registers vorbelegen; editierbar und unveränderte Raw-Schreibweise. Bei „Speichern & nächster Akt“ den Monat des eben gespeicherten Aktes verwenden.
- **Zeiteingabe:** `a` → `ante`, `p` → `po` bei Beurkundung und Geburt, per Feldwechsel/Tab ohne zusätzliche Enter-Eingabe; andere Quellenlesarten werden nicht überschrieben.
- **Dichiarante:** `di/fu`, Vatername und standardmässiges `anni` in den ausklappbaren Zusatzbereich; Alter, Beruf und Wohnort kompakt in einer Zeile. Gemeinde aus `act_comune_raw` als editierbarer Kontextvorschlag.
- **Separat genannter Vater:** Gemeinde des Aktes ebenfalls als editierbarer Vorschlag; keine duplizierte Vaterposition, wenn Dichiarante selbst der Vater ist.
- **Zeugen:** Alterswortlaut und Beruf direkt nebeneinander; individuelle Wohnortabweichungen weiter im ausklappbaren Abschnitt. Der kollektive Wortlaut `in questo comune` bleibt auf Aktenebene.
- **Provenienz des Wohnorts:** Neuer SQL-View `participant_domicile_resolved` für Dichiarante/separaten Vater. Ein unveränderter Default wird **nicht** zu einem fiktiven `domicile_raw`-Transkript.
- **FamilySearch:** Quellen-URL direkt sichtbar; darunter Aufnahme Nr. und Gesamtzahl. Vorbelegung der letzten Aufnahme, mehrseitige Akte über „Weitere Aufnahme“ möglich; keine Bilddateien speichern.
- **Excel:** URL und Aufnahmenummer im `NAS`-Blatt, zusätzlich aufgelöste Wohnorte samt Herkunft im `Participants`-Blatt. Kein `SourceImages`/`ActImages` mehr im Standard-Export; bei mehr als einer Aufnahme erscheint `AdditionalImages`. Alte v1.2-Dateien sind weiterhin importierbar.
- **Vollständigkeitsprüfung:** Ausklappbare, nicht-blockierende Prüfhilfe für erwartete Informationen. Fehlende optionale Felder benötigen kein manuelles `x`; Entwürfe bleiben unvollständig zulässig.
- **Kompatibilität:** SQLite-Tabellen bleiben unverändert. 44 automatisierte Tests bestanden, plus Sechs-Akte-Import und Rückexport (2 Register, 6 NAS, 36 Positionen, SQLite-Integritätsprüfung bestanden). Die Streamlit-GUI muss lokal im Browser geprüft werden.

**Bewusst nicht implementiert:** Formularprofil 1809, MAT/MOR und explizite Segmentierung der handschriftlichen Jahresendung `cinque`.


## v1.2 – Quellenkritik, Transkriptionsprovenienz und Bildreferenzen (14.11.2026)

**Neue aktenbezogene Metadaten, dauerhaft in SQLite:**

- `transcriber_name`: Wer transkribiert? Bei einem neuen Akt wird der zuletzt gespeicherte Name als **editierbarer Vorschlag** eingesetzt (in `app_settings` gespeichert).
- `transcribed_at_utc`: Zeitpunkt der **ersten Speicherung in CtC**. Bei bereits vorhandenen Akten bleibt der unbekannte ursprüngliche Zeitpunkt `NULL`; er wird nicht nachträglich erfunden.
- `updated_at_utc`: Zeitpunkt der letzten Speicherung, automatisch in UTC.
- `source_legibility_1_5`: Lesbarkeit der Handschrift dieses Akts, 1 (sehr gut) bis 5 (sehr schwierig), optional. Wertebereich in der Benutzeroberfläche und SQLite eingeschränkt.
- `transcription_note`: Freitext für quellenkritische/editorische Beobachtungen, z. B. versehentlich versetzte Altersangaben.
- `session_note`: Separate, optionale Sitzungsnotiz.
- `transcription_events`: unveränderliche Speicherereignisse mit Zeitpunkt, eingetragenem Namen, Entwurf/Vollständig-Status und Aktion `create`/`update`. Auch nach Korrekturen bleibt der frühere Eintrag im Protokoll erhalten.

**Quellennaher Zeugen-Workflow:**

- Individuelles Zeugen-Wohnortfeld aus der normalen Tab-Reihenfolge entfernt; im aufklappbaren Abschnitt **„Weitere Zeugenangaben“** erscheint stattdessen die erschlossene Gemeinde als editierbarer Vorschlag.
- Nicht abweichende Gemeinden werden **nicht** als wörtliche Quelle in `participants.domicile_raw` dupliziert. Die gedruckte gemeinsame Formel bleibt in `nas.witness_domicile_collective_raw`.
- SQLite-View `witness_domicile_resolved`: löst `in questo comune` auf `nas.act_comune_raw` auf und unterscheidet `intra_act_collective_reference`, `intra_act_individual_reference`, `explicit_individual_raw`, `unresolved`.
- Kompatibilität mit bereits erfassten Varianten: `x` oder `in questo comune` als historisch vorhandene individuelle Rohangabe bleiben erhalten, ohne als Ortsname fehlinterpretiert zu werden.
- Bei der Vorlage „entrambi“ wird ohne individuelle Wohnortangabe nur bei genau zwei Zeugen automatisch aufgelöst.

**Bild-/Quellenreferenzen:**

- Zwei neue Tabellen: `source_images` (Aufnahmenummer, Gesamtzahl der Aufnahmen, FamilySearch-/Quellenlink, Register) und `act_images` (n:m-Verbindung Akte ↔ Aufnahmen, mit Reihenfolge).
- Ein Bild kann mehrere Akte enthalten; ein Akt kann mehreren Bildern zugeordnet werden. Optionaler, standardmässig eingeklappter Quellenbereich in der Eingabemaske.
- Export und Import unterstützen zusätzlich die Blätter `SourceImages`, `ActImages` und `TranscriptionEvents`. Alte Arbeitsmappen mit nur drei Blättern bleiben gültig.

**Bedienung und Datensicherheit:**

- Streamlit-Überschriften-Anker deaktiviert, damit kein unnötiger Tastatur-Fokus durch Kettensymbole entsteht.
- Das bestehende NAS-Datenmodell wird **in-place** mittels `ALTER TABLE` erweitert; alte Akte und Positionen bleiben erhalten.
- **Automatische einmalige SQLite-Sicherung** vor einer Migration: `data/ctc.pre_v1_2.sqlite`. Unabhängig davon ist eine manuelle Sicherung vor dem Update ausdrücklich empfohlen.
- 37 automatisierte Python-Tests bestanden. Migration anhand des aktuellen Exports mit **3 NAS-Akten und 18 Positionen** erfolgreich geprüft. Streamlit-Browser-Test auf Windows steht noch aus.

## v1.1 – NAS Capture-Workflow

- Gemeinde (`act_comune_raw`) nach dem Sindaco und vor dem Declarant in Quellenreihenfolge.
- Neuer NAS-Akt: Gemeinde aus dem jeweils aktiven Register als editierbarer Vorschlag.
- Neuer NAS-Akt: Sindaco aus dem zuletzt angelegten Akt desselben Registers als editierbarer Vorschlag.
- Geburt: zuerst Tageszeit/Stunde/Minuten, dann Tag/Monat, danach Geburtsadresse.
- Kind: Geschlechtsangabe vor Vor- und Nachname.
- Zeugen: Alterseinheit `anni` aus dem Vordruck ohne eigenes Eingabefeld.
- Gemeinsamer, editierbarer Zeugen-Wohnorthinweis `entrambi residenti in questo comune`.
- Excel-Export mit Datum und Uhrzeit im Dateinamen; SQLite/Excel-Bezeichnungen geklärt.

## Bewusste Grenzen von v1.2

- Weiterhin **nur NAS**, keine MAT/MOR-Masken und noch keine gemeinsame `acts`-Tabelle.
- Die Skala zur Lesbarkeit wird **pro Akt** bewertet, nicht automatisch für das gesamte Register.
- Keine automatisierte Handschrifterkennung, KI-Normalisierung oder personenbezogene Record-Linkage.
- Die FamilySearch-Bildreferenz ist eine **Quellenreferenz**, kein integrierter Bildbetrachter.
- Neu erfasste Quelleigenschaften werden nicht rückwirkend als vermeintlich historische Tatsachen in Altbestände eingetragen.

## v1.4 – Zeitmessung der Akterfassung

- `capture_started_at_utc`: Beim Start einer **neuen** NAS-Erfassung einmalig gesetzt; Streamlit-Neuzeichnungen setzen den Wert nicht zurück.
- `capture_saved_at_utc`: Zeitpunkt der **ersten erfolgreichen vollständigen Speicherung**. Ein Entwurfsspeichern gilt nicht als abgeschlossene Erfassung.
- `capture_duration_seconds`: Automatisch aus Erfassungsbeginn und erster vollständiger Speicherung berechnete, nichtnegative Dauer in Sekunden; spätere Korrekturen ändern sie nicht.
- Neue Felder in SQLite und im NAS-Blatt des Excel-Exports; kompatibler Import alter Dateien. Keine rückwirkend erfundenen Dauern für die bisherigen Akte.
- Automatische Datenbanksicherung `data/ctc.pre_v1_4.sqlite` vor einer Migration aus 1.3.
- Die Maske zeigt Erfassungsbeginn und (bei abgeschlossenen Akten) Dauer; Erklärung, dass Recherche/Pausen in der Wall-Clock-Zeit enthalten sind.
- 7 zusätzliche automatisierte Tests für Zeitsemantik, Entwürfe, Änderungen, Altbestand, Import/Export und Migration. Real-Datensatz mit sechs Akten durch Datenbankupgrade und Excel-Rückimport geprüft.

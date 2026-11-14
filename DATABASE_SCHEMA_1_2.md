# CtC 1.2 – Datenmodell und Provenienz

## Bestehende Tabellen

`registers` beschreibt einen Registerband; `nas` einen individuellen Geburtsakt; `participants` die Rollen bzw. quellengebundenen Personenreferenzen zu einem Akt. Die technischen IDs sind **keine** aufgelösten historischen Personenidentitäten.

## Neue Spalten in `nas`

| Spalte | Datentyp | Bedeutung |
|---|---|---|
| `transcriber_name` | TEXT | Name, der beim letzten Speichern des Akts als transkribierende Person eingetragen war |
| `transcribed_at_utc` | TEXT, ISO 8601 | Erste Speicherung in CtC, **nicht** sicherer Beginn des Lesens; bei Altbeständen ohne frühere Erfassung bleibt `NULL` |
| `updated_at_utc` | TEXT, ISO 8601 | Letzte Speicherung in CtC |
| `source_legibility_1_5` | INTEGER, 1–5 | Subjektive Handschrift-Lesbarkeit **dieses Akts**, optional |
| `transcription_note` | TEXT | Editorische/quellenkritische Bemerkungen, nicht wörtliche Transkription |
| `session_note` | TEXT | Hinweise zum Arbeitsvorgang |

Skala: 1 sehr gut, 2 gut, 3 mittel, 4 schwierig, 5 sehr schwierig/weitgehend unleserlich. Die Lesbarkeit ist weder ein KI-Konfidenzwert noch eine automatisch bestimmte Eigenschaft.

## Neue Tabellen

- `app_settings(key,value)`: aktuell `last_transcriber`, damit neue Akte einen editierbaren Namen vorschlagen.
- `transcription_events(event_uid,act_id,recorded_at_utc,actor_name,event_type,capture_status)`: **append-only** Protokoll von Speichervorgängen. Korrekturen der Zuordnung löschen frühere Protokolleinträge nicht. Das Feld `transcriber_name` in `nas` zeigt den aktuellen Wert, die Ereignistabelle die gespeicherten historischen Bearbeitungsschritte.
- `source_images(image_id,register_id,image_number_raw,image_total_raw,familysearch_url)`: digitale Aufnahmen eines Registers. `image_number_raw` bezeichnet die Aufnahme im Viewer, **nicht** automatisch die historische Seitenzahl.
- `act_images(act_id,image_id,sequence_no)`: Zuordnung von 0–n Aufnahmen pro Geburtsakt; jede Aufnahme darf mehreren Akten zugeordnet sein. Dieselbe Aufnahme wird nach `(register_id,image_number_raw,familysearch_url)` wiederverwendet.

## Berechnete Wohnorte

Die SQL-View `witness_domicile_resolved` bietet die Spalten:

- `participant_id`, `act_id`, `sequence_no`
- `domicile_resolved`: aufgelöster Ort oder NULL
- `resolution_basis`: `explicit_individual_raw`, `intra_act_individual_reference`, `intra_act_collective_reference` oder `unresolved`

Beispiel: `nas.act_comune_raw = Girifalco` und `nas.witness_domicile_collective_raw = entrambi residenti in questo comune` führen bei zwei Zeugen zu `domicile_resolved = Girifalco` mit `resolution_basis = intra_act_collective_reference`.

Die historisch überlieferten Rohangaben bleiben davon unberührt; insbesondere wird `participants.domicile_raw` **nicht** automatisch mit Girifalco befüllt. Eine ausdrücklich abweichende individuelle Rohangabe hat Vorrang. Auch bisherige individuelle Rohwerte `x` und `in questo comune` bleiben erhalten und werden nicht als wörtliche Gemeindenamen ausgegeben.

## Datensicherheit

Vor der einmaligen Migration erstellt CtC automatisch `data/ctc.pre_v1_2.sqlite` als konsistente Sicherung. Zusätzlich sollte vor jedem Programmupdate manuell `data/ctc.sqlite` gesichert werden. Excel enthält künftig die drei Grundtabellen sowie `SourceImages`, `ActImages` und `TranscriptionEvents`, ist aber **kein Ersatz** für eine SQLite-Datenbanksicherung.

**Geltungsbereich:** Noch NAS, nicht MAT/MOR; die gemeinsame typübergreifende `acts`-Architektur bleibt ein gesonderter Entwicklungsschritt.

# CtC 1.5 – SQLite-Vorschlagsvokabulare

Bestehende Haupttabellen `registers`, `nas`, `participants`, `source_images`, `act_images`, `transcription_events`, `app_settings`, `id_counters` bleiben unverändert. Die NAS-Timing-Felder aus Version 1.4 bleiben erhalten.

## Neue Materialisierung

```sql
CREATE TABLE vocabulary_entries (
  kind TEXT NOT NULL CHECK(kind IN ('given_name','surname','profession')),
  value_raw TEXT NOT NULL,
  occurrence_count INTEGER NOT NULL CHECK(occurrence_count > 0),
  PRIMARY KEY(kind, value_raw)
);
```

Drei einfache lesbare Views werden zusätzlich angelegt: `vocabulary_given_names`, `vocabulary_surnames`, `vocabulary_professions` (jeweils `value_raw, occurrence_count`). Beispielsweise:

```sql
SELECT value_raw, occurrence_count
FROM vocabulary_surnames
ORDER BY occurrence_count DESC, value_raw;
```

## Herkunft und Gültigkeit

- `given_name`: `participants.given_name_raw`, `participants.given_name_title_raw`
- `surname`: `participants.surname_raw`, `participants.surname_title_raw`
- `profession`: `participants.profession_raw`
- Nur Daten zu `nas.capture_status='complete'`.
- Jeweils `DISTINCT participant_id, kind, value_raw`, damit die gleiche Schreibweise in Titel und Haupttext nicht doppelt zählt.
- Leerwerte, `x`/`q` und Zeichenfolgen mit Unsicherheits-/Editionsnotation `(`, `)`, `[`, `]`, `?`, `…` werden **nicht** in den Vorschlagsindex übernommen, bleiben aber als RAW-Werte in der Quelle unverändert.
- Keine stillschweigende Umstellung von Gross-/Kleinschreibung oder Orthographie. Verschiedene Schreibweisen und historische Varianten bleiben getrennt.
- `refresh_vocabulary(con)` erzeugt alle drei Listen atomar innerhalb desselben Speichervorgangs wie die Personenpositionen. Auch ein fehlgeschlagener Speichervorgang hinterlässt keinen teilaktualisierten Wörterbuchindex.
- Bei Migration wird eine SQLite-Backup-Kopie `ctc.pre_v1_5.sqlite` erstellt. Ein bereits migrierter Bestand wird nicht erneut verändert; die Indizes werden bei neuen Datensätzen aktualisiert.

## Noch nicht Teil von Version 1.5

- Manuell gepflegte Normformen, kontrollierte Schreibvarianten oder Wörterbuchfreigaben.
- Register-/Jahr-abhängige Vorschlagsgewichtung.
- Personenidentitätsentscheidungen, MID/GID, Record Linkage.
- MAT/MOR-Erfassung (die allgemeine Wörterbuchstruktur könnte später ohne Semantikänderung wiederverwendet werden).

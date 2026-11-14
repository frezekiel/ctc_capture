# CtC 1.4 – Ergänzung des SQLite-Datenmodells

Das relationale NAS-Modell aus Version 1.3 wird **nicht** ersetzt. Die Tabellen `registers`, `nas`, `participants`, `source_images`, `act_images`, `transcription_events`, `app_settings` und `id_counters` sowie die abgeleiteten Wohnort-Views bleiben erhalten.

Neu in `nas`:

```sql
capture_started_at_utc TEXT,
capture_saved_at_utc TEXT,
capture_duration_seconds INTEGER CHECK (capture_duration_seconds >= 0)
```

**Zeitsemantik:** `capture_started_at_utc` bezeichnet das Öffnen einer *neuen* NAS-Erfassungsmaske; `capture_saved_at_utc` die erste **erfolgreiche vollständige** Speicherung. `capture_duration_seconds` ist deren Zeitdifferenz und wird serverseitig berechnet. Ein Speichern als Entwurf lässt `capture_saved_at_utc` und `capture_duration_seconds` NULL. Spätere Korrekturen überschreiben die drei Werte nicht. Beim Import älterer Dateien werden bereits vorhandene Messwerte nicht gelöscht.

`transcribed_at_utc` aus 1.2 bleibt separat: erster Speichervorgang (auch ein Entwurf). `updated_at_utc` bleibt die Zeit der jeweils letzten Speicherung. Es handelt sich nicht um historische Quellendaten, sondern Metadaten des Erfassungsprozesses.

**Wissenschaftliche Einschränkung:** Die Dauer ist die Zeit zwischen den Zeitpunkten, **einschliesslich** möglicher Recherche und Unterbrechungen. Bei Entwurfsspeicherung und späterem Abschluss umfasst sie den gesamten Zeitraum bis zum Abschluss. Ein leerer Messwert bei alten Akten darf nicht mit null Sekunden verwechselt werden.

Alle drei Felder werden in `NAS_COLUMNS` sowie dem Blatt `NAS` des Excel-Exports ausgegeben und beim Import einer 1.4-Datei wiederhergestellt.

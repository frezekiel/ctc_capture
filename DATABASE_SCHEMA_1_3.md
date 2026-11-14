# CtC 1.3 – Datenbank und exportierte Quellenreferenzen

Das persistente v1.2-Datenbankschema bleibt bestehen. **Keine neue Tabellenmigration ist erforderlich.** Neue Speicherfelder wurden für 1.3 bewusst vermieden, wo eine relationale Ansicht genügt.

## Tabellen (wie 1.2)

- `registers`: Registerkontext mit `register_id`, `comune`, `year`, `register_type`.
- `nas`: alle NAS-Aktfelder, Status und Transkriptionsmetadaten.
- `participants`: positionsgebundene Personenreferenzen mit `participant_id`, Rolle, optionalen Rohfeldern.
- `source_images`: Link + Position der aufgenommenen Seite im FamilySearch-Viewer (keine Bildbytes).
- `act_images`: n:m-Verknüpfung zwischen Akt und Aufnahme mit Positionsnummer.
- `transcription_events`: unveränderliche Speicherereignisse.
- `app_settings`, `id_counters`: Benutzervorschläge und ID-Stabilität.

## SQL-Views

- `witness_domicile_resolved` (seit v1.2) löst das gemeinsame `in questo comune` auf `nas.act_comune_raw` auf, soweit die Formulierung und die Anzahl Zeugen dies erlauben.
- `participant_domicile_resolved` (neu v1.3) zeigt bei Dichiarante und separat erfasstem Vater den abgeleiteten Wohnort als `domicile_resolved` mit `resolution_basis = suggested_from_act_comune`. Explizite individuelle Eintragungen in `participants.domicile_raw` haben Vorrang und erhalten `resolution_basis = explicit_individual_raw`.

Die Gemeindevorbelegung für Dichiarante/Vater ist **kein Beleg dafür, dass der Gemeindename im individuellen Quellentext wörtlich steht**. Deshalb bleibt `domicile_raw` bei unveränderter Vorbelegung leer, während die aufgelöste Ortsangabe in der View bzw. im Export erscheint. Das ist eine bewusste konservative Grenze: Ein ausdrücklich gleichlautender Quellenname muss, wenn nötig, separat als wörtliche Angabe verifiziert werden.

## Excel-Kopie ab v1.3

Die Standardmappe enthält:

1. `Registers`
2. `NAS` – inkl. `source_url`, `image_number`, `image_total` für die **erste** Aufnahme pro Akt
3. `Participants` – inkl. abgeleitetem `domicile_resolved` und `domicile_resolution_basis`, neben unverändertem `domicile_raw`
4. `TranscriptionEvents`

Nur wenn ein Akt aus mehreren Bildern besteht, entsteht zusätzlich:

5. `AdditionalImages` – jede weitere Aufnahme mit `act_id` und `sequence_no`.

Die internen Tabellen `source_images` und `act_images` existieren weiterhin in SQLite, **nicht mehr als Standard-Excel-Blätter**. V1.3 kann sowohl die alte sechsblättrige v1.2-Mappe als auch die neue flache v1.3-Mappe importieren. Die SQL-Zuordnung mit mehreren Akten pro Bild und mehreren Bildern pro Akt bleibt erhalten.

## Erfassung und Interpretation

- `act_year_raw` wird bei neuen Akten als editierbarer Wert aus dem aktiven Register vorgeschlagen; es bedeutet nicht, dass alle Ziffern handschriftlich eingetragen wurden.
- `act_month_raw` wird als Rohwortlaut aus dem zuletzt neu erfassten Akt desselben Registers vorgeschlagen. Der Geburtsmonatsbezug `birth_month_raw` bleibt davon unabhängig.
- `act_time_type_raw`, `birth_time_type_raw`: Die Benutzerkürzel `a` und `p` werden beim Verlassen des Feldes bzw. spätestens beim Speichern zu `ante` und `po` expandiert. Andere Schreibweisen bleiben erhalten.
- `age_unit_raw = anni` ist in der verwendeten NAS-Druckvorlage ein vorgegebener Wert; die Anzeige kann deshalb aus dem normalen Tastaturworkflow verschwinden.
- Leere **optionale** Felder werden nicht automatisch mit `x` gefüllt. Der Status `complete` betrifft die Prüfung des gesamten Akts, nicht eine Behauptung, dass alle theoretisch möglichen Angaben vorliegen.

# CtC 1.5.1 – Tests

- **62 automatische Tests bestanden** (`python -m pytest -q`), inklusive der 60 Tests aus CtC 1.5 und zweier zusätzlicher Regressionstests.
- Neuanlage: `mother_relationship_to_declarant_raw` hat den echten vorbelegten Feldwert und wird beim Speichern in SQLite sowie beim Excel-Export erhalten.
- Änderung oder explizites Löschen der Formel bleibt möglich. Bereits gespeicherte leere Angaben bleiben leer.
- Keine Datenbankschema-Änderung.
- Browser-UI-Test auf lokalem Windows/Streamlit noch ausstehend.

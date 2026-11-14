"""SQLite persistence for the CtC manual capture layer.

All modifications of one act (NAS + participants) are atomic. No person linkage.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from uuid import uuid4
from typing import Iterator, Any

from models import (
    NAS_COLUMNS, PARTICIPANT_COLUMNS, REGISTER_COLUMNS,
    assign_participant_ids, make_act_id,
)
from validation import validate_capture
from vocabulary import refresh_vocabulary

DB_DEFAULT = Path(__file__).resolve().parent / "data" / "ctc.sqlite"

# Columns added in CtC 1.2. Existing historical records MUST NOT receive
# fabricated transcription dates, names, or source-quality scores.
V12_NAS_TYPES = {
    "transcriber_name": "TEXT",
    "transcribed_at_utc": "TEXT",
    "updated_at_utc": "TEXT",
    "source_legibility_1_5": "INTEGER CHECK(source_legibility_1_5 BETWEEN 1 AND 5)",
    "transcription_note": "TEXT",
    "session_note": "TEXT",
}
# Time-to-completion is wall-clock time from opening a NEW act to its first
# successful COMPLETE save. Draft saves and subsequent edits do not reset it.
V14_NAS_TYPES = {
    "capture_started_at_utc": "TEXT",
    "capture_saved_at_utc": "TEXT",
    "capture_duration_seconds": "INTEGER CHECK(capture_duration_seconds >= 0)",
}
NAS_TYPES = {**V12_NAS_TYPES, **V14_NAS_TYPES}


def _backup_before_migration(path: str | Path) -> None:
    """One SQLite-consistent snapshot before upgrading an existing 1.0/1.1 DB."""
    path = Path(path)
    if not path.exists() or path.stat().st_size == 0:
        return
    backup_path = path.with_name(path.stem + ".pre_v1_2.sqlite")
    if backup_path.exists():
        return
    with sqlite3.connect(path) as con:
        if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='nas'").fetchone():
            return
        columns = {row[1] for row in con.execute('PRAGMA table_info(nas)')}
        if set(V12_NAS_TYPES).issubset(columns):
            return
        # SQLite online backup (rather than copying a possibly live WAL file).
        with sqlite3.connect(backup_path) as destination:
            con.backup(destination)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _duration_seconds(started: str | None, saved: str) -> int | None:
    """Time between two UTC timestamps; do not invent missing/invalid values."""
    if not started:
        return None
    try:
        beginning = datetime.fromisoformat(started)
        end = datetime.fromisoformat(saved)
    except (ValueError, TypeError):
        return None
    if beginning.utcoffset() is None or end.utcoffset() is None:
        return None
    elapsed = (end - beginning).total_seconds()
    if elapsed < 0:
        return None
    return round(elapsed)


def _backup_before_v14_migration(path: str | Path) -> None:
    """One transactionally consistent copy of the old schema before migration."""
    path = Path(path)
    if not path.exists() or path.stat().st_size == 0:
        return
    backup_path = path.with_name(path.stem + '.pre_v1_4.sqlite')
    if backup_path.exists():
        return
    with sqlite3.connect(path) as source:
        if not source.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='nas'").fetchone():
            return
        existing = {row[1] for row in source.execute('PRAGMA table_info(nas)')}
        if set(V14_NAS_TYPES).issubset(existing):
            return
        # Using the SQLite backup API also handles DBs using WAL mode.
        with sqlite3.connect(backup_path) as destination:
            source.backup(destination)


def _backup_before_v15_migration(path: str | Path) -> None:
    """SQLite-safe backup before adding the three managed vocabulary lists."""
    path = Path(path)
    if not path.exists() or path.stat().st_size == 0:
        return
    backup_path = path.with_name(path.stem + '.pre_v1_5.sqlite')
    if backup_path.exists():
        return
    with sqlite3.connect(path) as source:
        if not source.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='nas'").fetchone():
            return
        already = source.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='vocabulary_entries'"
        ).fetchone()
        if already:
            return
        with sqlite3.connect(backup_path) as destination:
            source.backup(destination)


@contextmanager
def connect(path: str | Path = DB_DEFAULT) -> Iterator[sqlite3.Connection]:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, timeout=20)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def init_db(path: str | Path = DB_DEFAULT) -> None:
    _backup_before_migration(path)
    _backup_before_v14_migration(path)
    _backup_before_v15_migration(path)
    register_fields = ",\n".join(f'"{col}" TEXT' for col in REGISTER_COLUMNS if col != "register_id")
    nas_fields = ",\n".join(
        f'"{col}" {NAS_TYPES.get(col, "TEXT")}'
        for col in NAS_COLUMNS if col not in ("act_id", "register_id")
    )
    part_fields = ",\n".join(
        f'"{col}" {"INTEGER" if col == "sequence_no" else "TEXT"}'
        for col in PARTICIPANT_COLUMNS if col not in ("participant_id", "act_id")
    )
    with connect(path) as con:
        con.executescript(f'''
            CREATE TABLE IF NOT EXISTS registers (
                register_id TEXT PRIMARY KEY,
                {register_fields}
            );
            CREATE TABLE IF NOT EXISTS nas (
                act_id TEXT PRIMARY KEY,
                register_id TEXT NOT NULL REFERENCES registers(register_id),
                {nas_fields},
                capture_status TEXT NOT NULL DEFAULT 'draft'
                    CHECK (capture_status IN ('draft', 'complete')),
                UNIQUE(register_id, act_number_raw)
            );
            CREATE TABLE IF NOT EXISTS participants (
                participant_id TEXT PRIMARY KEY,
                act_id TEXT NOT NULL REFERENCES nas(act_id) ON DELETE CASCADE,
                {part_fields},
                UNIQUE(act_id, role, sequence_no),
                CHECK(sequence_no >= 1)
            );
            CREATE INDEX IF NOT EXISTS participants_act_idx ON participants(act_id);
            CREATE TABLE IF NOT EXISTS source_images (
                image_id INTEGER PRIMARY KEY AUTOINCREMENT,
                register_id TEXT NOT NULL REFERENCES registers(register_id),
                image_number_raw TEXT NOT NULL DEFAULT '',
                image_total_raw TEXT,
                familysearch_url TEXT NOT NULL DEFAULT '',
                UNIQUE(register_id, image_number_raw, familysearch_url)
            );
            CREATE TABLE IF NOT EXISTS act_images (
                act_id TEXT NOT NULL REFERENCES nas(act_id) ON DELETE CASCADE,
                image_id INTEGER NOT NULL REFERENCES source_images(image_id),
                sequence_no INTEGER NOT NULL CHECK(sequence_no >= 1),
                PRIMARY KEY(act_id, image_id),
                UNIQUE(act_id, sequence_no)
            );
            CREATE INDEX IF NOT EXISTS act_images_act_idx ON act_images(act_id);
            CREATE TABLE IF NOT EXISTS transcription_events (
                event_uid TEXT PRIMARY KEY,
                act_id TEXT NOT NULL REFERENCES nas(act_id) ON DELETE CASCADE,
                recorded_at_utc TEXT NOT NULL,
                actor_name TEXT,
                event_type TEXT NOT NULL CHECK(event_type IN ('create','update')),
                capture_status TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS transcription_events_act_idx
                ON transcription_events(act_id, recorded_at_utc);
            CREATE TABLE IF NOT EXISTS vocabulary_entries (
                kind TEXT NOT NULL CHECK(kind IN ('given_name','surname','profession')),
                value_raw TEXT NOT NULL,
                occurrence_count INTEGER NOT NULL CHECK(occurrence_count > 0),
                PRIMARY KEY(kind, value_raw)
            );
            CREATE VIEW IF NOT EXISTS vocabulary_given_names AS
                SELECT value_raw,occurrence_count FROM vocabulary_entries
                WHERE kind='given_name';
            CREATE VIEW IF NOT EXISTS vocabulary_surnames AS
                SELECT value_raw,occurrence_count FROM vocabulary_entries
                WHERE kind='surname';
            CREATE VIEW IF NOT EXISTS vocabulary_professions AS
                SELECT value_raw,occurrence_count FROM vocabulary_entries
                WHERE kind='profession';
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS id_counters (
                act_id TEXT PRIMARY KEY REFERENCES nas(act_id) ON DELETE CASCADE,
                last_ordinal INTEGER NOT NULL DEFAULT 0
            );
        ''')
        # Compatibility with pre-existing CtC databases if opened again.
        existing = {row["name"] for row in con.execute("PRAGMA table_info(nas)")}
        if "mother_relationship_to_declarant_raw" not in existing:
            con.execute("ALTER TABLE nas ADD COLUMN mother_relationship_to_declarant_raw TEXT")
        if "capture_status" not in existing:
            con.execute("ALTER TABLE nas ADD COLUMN capture_status TEXT NOT NULL DEFAULT 'draft'")
        for column, sql_type in NAS_TYPES.items():
            if column not in existing:
                con.execute(f'ALTER TABLE nas ADD COLUMN "{column}" {sql_type}')
        if not con.execute('SELECT 1 FROM vocabulary_entries LIMIT 1').fetchone():
            if con.execute("SELECT 1 FROM nas WHERE capture_status='complete' LIMIT 1").fetchone():
                refresh_vocabulary(con)
        # View is derived, not a second transcription of "in questo comune".
        # When a collective formula explicitly addresses two witnesses, it is
        # only resolved if two witness rows are actually present.
        con.execute("""
            CREATE VIEW IF NOT EXISTS witness_domicile_resolved AS
            WITH witnesses AS (
              SELECT p.participant_id, p.act_id, p.sequence_no,
                     p.domicile_raw, n.act_comune_raw,
                     n.witness_domicile_collective_raw,
                     COUNT(*) OVER (PARTITION BY p.act_id) AS witness_count,
                     LOWER(TRIM(COALESCE(p.domicile_raw, ''))) AS individual_term,
                     LOWER(COALESCE(n.witness_domicile_collective_raw, '')) AS collective_term
              FROM participants p JOIN nas n ON n.act_id=p.act_id
              WHERE p.role='witness'
            )
            SELECT participant_id,act_id,sequence_no,
                   CASE
                     WHEN individual_term NOT IN ('','x','in questo comune') THEN domicile_raw
                     WHEN individual_term='in questo comune'
                          AND TRIM(COALESCE(act_comune_raw,''))<>'' THEN act_comune_raw
                     WHEN collective_term LIKE '%in questo comune%'
                          AND TRIM(COALESCE(act_comune_raw,''))<>''
                          AND (collective_term NOT LIKE '%entrambi%' OR witness_count=2)
                          THEN act_comune_raw
                     ELSE NULL
                   END AS domicile_resolved,
                   CASE
                     WHEN individual_term NOT IN ('','x','in questo comune')
                          THEN 'explicit_individual_raw'
                     WHEN individual_term='in questo comune'
                          AND TRIM(COALESCE(act_comune_raw,''))<>''
                          THEN 'intra_act_individual_reference'
                     WHEN collective_term LIKE '%in questo comune%'
                          AND TRIM(COALESCE(act_comune_raw,''))<>''
                          AND (collective_term NOT LIKE '%entrambi%' OR witness_count=2)
                          THEN 'intra_act_collective_reference'
                     ELSE 'unresolved'
                   END AS resolution_basis
            FROM witnesses
        """)
        # A register-context suggestion is never silently copied into domicile_raw.
        # This view makes the resolved information and its provenance queryable.
        con.execute("""
            CREATE VIEW IF NOT EXISTS participant_domicile_resolved AS
            SELECT p.participant_id, p.act_id, p.role, p.sequence_no,
                   CASE WHEN TRIM(COALESCE(p.domicile_raw,'')) NOT IN ('','x')
                             THEN p.domicile_raw
                        WHEN p.role IN ('declarant','father')
                             AND TRIM(COALESCE(n.act_comune_raw,''))<>''
                             THEN n.act_comune_raw
                        ELSE NULL END AS domicile_resolved,
                   CASE WHEN TRIM(COALESCE(p.domicile_raw,'')) NOT IN ('','x')
                             THEN 'explicit_individual_raw'
                        WHEN p.role IN ('declarant','father')
                             AND TRIM(COALESCE(n.act_comune_raw,''))<>''
                             THEN 'suggested_from_act_comune'
                        ELSE 'unresolved' END AS resolution_basis
            FROM participants p JOIN nas n ON n.act_id=p.act_id
            WHERE p.role IN ('declarant','father')
        """)


def load_source_images(act_id: str, path: str | Path = DB_DEFAULT) -> list[dict[str, Any]]:
    """Sources shared by acts; an act can reference multiple images in order."""
    with connect(path) as con:
        return _dicts(con.execute('''
            SELECT i.image_id, i.register_id, i.image_number_raw, i.image_total_raw,
                   i.familysearch_url, a.sequence_no
            FROM act_images a JOIN source_images i ON a.image_id=i.image_id
            WHERE a.act_id=? ORDER BY a.sequence_no
        ''', (act_id,)))


def _persist_image(con: sqlite3.Connection, register_id: str, ref: dict[str, Any]) -> int:
    number = str(ref.get('image_number_raw') or '').strip()
    total = str(ref.get('image_total_raw') or '').strip() or None
    url = str(ref.get('familysearch_url') or '').strip()
    if not number and not url:
        raise ValueError('Aufnahme benötigt eine Nummer oder einen Quellenlink.')
    if url and not (url.startswith('https://') or url.startswith('http://')):
        raise ValueError('Quellenlink muss mit https:// oder http:// beginnen.')
    con.execute('''
        INSERT INTO source_images(register_id,image_number_raw,image_total_raw,familysearch_url)
        VALUES (?,?,?,?) ON CONFLICT(register_id,image_number_raw,familysearch_url)
        DO UPDATE SET image_total_raw=COALESCE(excluded.image_total_raw,source_images.image_total_raw)
    ''', (register_id,number,total,url))
    return con.execute('''
        SELECT image_id FROM source_images WHERE register_id=? AND image_number_raw=?
        AND familysearch_url=?
    ''', (register_id,number,url)).fetchone()[0]


def _save_act_images(con: sqlite3.Connection, act_id: str, register_id: str,
                     images: list[dict[str, Any]]) -> None:
    # First resolve all new links; a failed/invalid entry leaves the old set intact.
    image_ids = [_persist_image(con,register_id,ref) for ref in images]
    if len(set(image_ids)) != len(image_ids):
        raise ValueError('Dieselbe Aufnahme ist für diesen Akt mehrfach eingetragen.')
    con.execute('DELETE FROM act_images WHERE act_id=?', (act_id,))
    con.executemany('INSERT INTO act_images(act_id,image_id,sequence_no) VALUES (?,?,?)',
                    ((act_id,image_id,n) for n,image_id in enumerate(image_ids,1)))


def list_transcription_events(act_id: str, path: str | Path = DB_DEFAULT) -> list[dict[str, Any]]:
    with connect(path) as con:
        return _dicts(con.execute('''
            SELECT recorded_at_utc,actor_name,event_type,capture_status
            FROM transcription_events WHERE act_id=?
            ORDER BY rowid
        ''', (act_id,)))


def export_transcription_events(path: str | Path = DB_DEFAULT) -> list[dict[str, Any]]:
    with connect(path) as con:
        return _dicts(con.execute('''
            SELECT event_uid,act_id,recorded_at_utc,actor_name,event_type,capture_status
            FROM transcription_events ORDER BY recorded_at_utc,event_uid
        '''))


def export_image_rows(path: str | Path = DB_DEFAULT) -> tuple[list[dict], list[dict]]:
    with connect(path) as con:
        images=_dicts(con.execute('''
            SELECT image_id,register_id,image_number_raw,image_total_raw,familysearch_url
            FROM source_images ORDER BY image_id
        '''))
        acts=_dicts(con.execute('''
            SELECT act_id,image_id,sequence_no FROM act_images ORDER BY act_id,sequence_no
        '''))
        return images,acts


def _dicts(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
    return [dict(row) for row in cursor.fetchall()]


def list_registers(path: str | Path = DB_DEFAULT) -> list[dict[str, Any]]:
    with connect(path) as con:
        return _dicts(con.execute('SELECT * FROM registers ORDER BY year, comune, register_id'))


def create_register(register: dict[str, Any], path: str | Path = DB_DEFAULT) -> None:
    if not register.get("register_id") or not register.get("comune") or not str(register.get("year") or "").strip():
        raise ValueError("Register-ID, Comune und Jahr sind erforderlich.")
    if register.get("register_type") not in ("NAS", "MAT", "MOR"):
        raise ValueError("Registertyp muss NAS, MAT oder MOR sein.")
    with connect(path) as con:
        con.execute(
            'INSERT INTO registers (register_id, comune, register_type, year) VALUES (?,?,?,?)',
            [str(register.get(c) or "") for c in REGISTER_COLUMNS],
        )


def list_acts(path: str | Path = DB_DEFAULT) -> list[dict[str, Any]]:
    with connect(path) as con:
        return _dicts(con.execute('''
            SELECT nas.act_id, nas.register_id, nas.act_number_raw, nas.capture_status,
                   registers.comune, registers.year,
                   (SELECT given_name_title_raw FROM participants p
                     WHERE p.act_id = nas.act_id AND p.role = 'child' LIMIT 1) AS child_name
            FROM nas JOIN registers USING(register_id)
            ORDER BY registers.year, nas.act_id
        '''))


def last_transcriber(path: str | Path = DB_DEFAULT) -> str | None:
    with connect(path) as con:
        row = con.execute("SELECT value FROM app_settings WHERE key='last_transcriber'").fetchone()
        return row[0] if row else None


def resolved_witness_domiciles(act_id: str, path: str | Path = DB_DEFAULT) -> list[dict[str, Any]]:
    with connect(path) as con:
        return _dicts(con.execute(
            'SELECT * FROM witness_domicile_resolved WHERE act_id=? ORDER BY sequence_no', (act_id,)
        ))


def last_created_act_defaults(register_id: str, path: str | Path = DB_DEFAULT) -> dict[str, Any]:
    """Month and last referenced scan of the most recently CREATED act.

    Editing older acts must not alter the defaults for future new acts.
    """
    with connect(path) as con:
        row = con.execute('''
            SELECT act_id,act_month_raw FROM nas
            WHERE register_id=? ORDER BY rowid DESC LIMIT 1
        ''', (register_id,)).fetchone()
        if row is None:
            return {"act_month_raw": None, "source_image": None}
        refs = load_source_images(row["act_id"], path)
        return {"act_month_raw": row["act_month_raw"],
                "source_image": refs[-1] if refs else None}


def latest_sindaco(register_id: str, path: str | Path = DB_DEFAULT) -> dict[str, Any] | None:
    """Sindaco from the most recently *created* NAS act in this register.

    Source-bound spelling is suggested, never linked to a global identity.
    Uses the SQLite act insertion order. Save & Next instead explicitly copies
    the Sindaco of the just-saved act, even when an earlier act was edited.
    """
    with connect(path) as con:
        row = con.execute('''
            SELECT p.* FROM participants AS p
            JOIN nas AS n ON n.act_id = p.act_id
            WHERE n.register_id = ? AND p.role = 'sindaco'
            ORDER BY n.rowid DESC LIMIT 1
        ''', (register_id,)).fetchone()
        return dict(row) if row else None


def load_capture(act_id: str, path: str | Path = DB_DEFAULT) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    with connect(path) as con:
        nas = con.execute('SELECT * FROM nas WHERE act_id=?', (act_id,)).fetchone()
        if nas is None:
            raise KeyError(f"Akt nicht gefunden: {act_id}")
        participants = _dicts(con.execute('''
            SELECT * FROM participants WHERE act_id = ?
            ORDER BY CASE role WHEN 'child' THEN 0 WHEN 'sindaco' THEN 1
                WHEN 'declarant' THEN 2 WHEN 'mother' THEN 3 WHEN 'father' THEN 4 ELSE 5 END,
                sequence_no
        ''', (act_id,)))
        return dict(nas), participants


def _upsert(con: sqlite3.Connection, table: str, fields: list[str], values: dict[str, Any], pk: str) -> None:
    cols = ', '.join(f'"{c}"' for c in fields)
    qs = ', '.join('?' for _ in fields)
    updates = ', '.join(f'"{c}"=excluded."{c}"' for c in fields if c != pk)
    con.execute(
        f'INSERT INTO "{table}" ({cols}) VALUES ({qs}) ON CONFLICT("{pk}") DO UPDATE SET {updates}',
        [values.get(c) for c in fields],
    )


def save_capture(
    nas: dict[str, Any], participants: list[dict[str, Any]],
    path: str | Path = DB_DEFAULT, *, complete: bool = False,
    source_images: list[dict[str, Any]] | None = None,
) -> str:
    """Create/update act and participants in one transaction. Stable participant IDs."""
    nas = dict(nas)
    nas["capture_status"] = "complete" if complete else "draft"
    problems = validate_capture(nas, participants, complete=complete)
    if problems:
        raise ValueError(" | ".join(problems))
    with connect(path) as con:
        row = con.execute('SELECT * FROM registers WHERE register_id=?', (nas['register_id'],)).fetchone()
        if row is None:
            raise ValueError(f"Unbekanntes Register: {nas['register_id']}")
        register = dict(row)
        if register['register_type'] != 'NAS':
            raise ValueError("Der NAS-Prototyp kann nur NAS-Registern Akte zuordnen.")
        if not nas.get('act_id'):
            existing = {r[0] for r in con.execute('SELECT act_id FROM nas')}
            nas['act_id'] = make_act_id(register, str(nas['act_number_raw']), existing)
        act_id = str(nas['act_id'])
        nas['act_id'] = act_id
        # 1.2 save events: unchanged semantics; first persistence is immutable.
        # 1.4 capture timing: start on opening a NEW act, finish on FIRST complete
        # save. Draft saves and editing a completed act must NEVER change timing.
        # Legacy acts keep NULL timing fields even if someone edits them.
        prior = con.execute('''
            SELECT transcribed_at_utc, capture_started_at_utc,
                   capture_saved_at_utc, capture_duration_seconds
            FROM nas WHERE act_id=?
        ''' , (act_id,)).fetchone()
        now = _utc_now()
        if prior is None:
            nas['transcribed_at_utc'] = now
            started = nas.get('capture_started_at_utc')
            # Do not claim a capture start for API/import clients that did not
            # measure one. Reject invalid timestamps rather than fabricating.
            if started and _duration_seconds(started, now) is None:
                raise ValueError('Ungültiger Messbeginn; Datum muss UTC und nicht in der Zukunft sein.')
            nas['capture_started_at_utc'] = started or None
            if complete and started:
                nas['capture_saved_at_utc'] = now
                nas['capture_duration_seconds'] = _duration_seconds(started, now)
            else:
                nas['capture_saved_at_utc'] = None
                nas['capture_duration_seconds'] = None
        else:
            nas['transcribed_at_utc'] = prior['transcribed_at_utc']
            nas['capture_started_at_utc'] = prior['capture_started_at_utc']
            nas['capture_saved_at_utc'] = prior['capture_saved_at_utc']
            nas['capture_duration_seconds'] = prior['capture_duration_seconds']
            if complete and prior['capture_saved_at_utc'] is None and prior['capture_started_at_utc']:
                # First completion of a previously saved draft.
                nas['capture_saved_at_utc'] = now
                nas['capture_duration_seconds'] = _duration_seconds(
                    prior['capture_started_at_utc'], now)
        nas['updated_at_utc'] = now
        _upsert(con, "nas", NAS_COLUMNS + ["capture_status"], nas, "act_id")
        transcriber = str(nas.get('transcriber_name') or '').strip()
        if transcriber:
            con.execute("""INSERT INTO app_settings(key,value) VALUES('last_transcriber', ?)
                           ON CONFLICT(key) DO UPDATE SET value=excluded.value""", (transcriber,))
        old_ids = {r[0] for r in con.execute('SELECT participant_id FROM participants')}
        counter_row = con.execute(
            'SELECT last_ordinal FROM id_counters WHERE act_id=?', (act_id,)
        ).fetchone()
        previous_max = int(counter_row['last_ordinal']) if counter_row else 0
        # Reserve even retired IDs: a deleted person reference must not be reused.
        old_ids.update(f'{act_id}_{i:02d}' for i in range(1, previous_max + 1))
        assigned = assign_participant_ids(act_id, participants, old_ids)
        highest = previous_max
        for p in assigned:
            suffix = str(p['participant_id']).removeprefix(act_id + '_')
            if suffix.isdigit():
                highest = max(highest, int(suffix))
        con.execute(
            'INSERT INTO id_counters(act_id, last_ordinal) VALUES (?, ?) '
            'ON CONFLICT(act_id) DO UPDATE SET last_ordinal=MAX(last_ordinal, excluded.last_ordinal)',
            (act_id, highest),
        )
        new_ids = {p['participant_id'] for p in assigned}
        if len(new_ids) != len(assigned):
            raise ValueError("Doppelte participant_id im aktuellen Akt.")
        for p in assigned:
            existing_parent = con.execute(
                'SELECT act_id FROM participants WHERE participant_id=?', (p['participant_id'],)
            ).fetchone()
            if existing_parent and existing_parent['act_id'] != act_id:
                raise ValueError(f"participant_id gehört zu anderem Akt: {p['participant_id']}")
        # Delete absent participants only while saving an explicitly edited act.
        if new_ids:
            placeholders = ','.join('?' for _ in new_ids)
            con.execute(f'DELETE FROM participants WHERE act_id=? AND participant_id NOT IN ({placeholders})',
                        [act_id, *sorted(new_ids)])
        else:
            con.execute('DELETE FROM participants WHERE act_id=?', (act_id,))
        # Reordering is safe with a temporary sequence to avoid transient UNIQUE conflicts.
        con.execute('UPDATE participants SET sequence_no = sequence_no + 100000 WHERE act_id=?', (act_id,))
        for p in assigned:
            _upsert(con, "participants", PARTICIPANT_COLUMNS, p, "participant_id")
        refresh_vocabulary(con)
        if source_images is not None:
            _save_act_images(con,act_id,nas['register_id'],source_images)
        # Immutable save event: audit survives corrections to "transcriber_name".
        con.execute('''
            INSERT INTO transcription_events
                (event_uid,act_id,recorded_at_utc,actor_name,event_type,capture_status)
            VALUES (?,?,?,?,?,?)
        ''', (uuid4().hex,act_id,nas['updated_at_utc'],
              transcriber or None, 'create' if prior is None else 'update', nas['capture_status']))
    return act_id


def import_rows(
    registers: list[dict[str, Any]], nas_rows: list[dict[str, Any]],
    participants: list[dict[str, Any]], path: str | Path = DB_DEFAULT,
    *, images: list[dict[str, Any]] | None = None,
    image_links: list[dict[str, Any]] | None = None,
    transcription_events: list[dict[str, Any]] | None = None,
    source_refs: dict[str, list[dict[str, Any]]] | None = None,
) -> tuple[int, int, int]:
    """Atomic upsert import. Does not delete unrelated rows or existing participants."""
    with connect(path) as con:
        for r in registers:
            _upsert(con, "registers", REGISTER_COLUMNS, r, "register_id")
        for act in nas_rows:
            if act.get('capture_status') not in ('draft', 'complete'):
                act['capture_status'] = 'draft'
            # Old Excel exports may lack provenance/time fields. Reimport must
            # not erase immutable timestamps already stored in SQLite.
            prior = con.execute('SELECT * FROM nas WHERE act_id=?', (act.get('act_id'),)).fetchone()
            if prior:
                for field in NAS_TYPES:
                    if act.get(field) is None:
                        act[field] = prior[field]
                for field in V14_NAS_TYPES:
                    if prior[field] is not None:
                        act[field] = prior[field]
            _upsert(con, "nas", NAS_COLUMNS + ["capture_status"], act, "act_id")
        high_water: dict[str, int] = {}
        for p in participants:
            _upsert(con, "participants", PARTICIPANT_COLUMNS, p, "participant_id")
            act_id = str(p['act_id'])
            suffix = str(p['participant_id']).removeprefix(act_id + '_')
            if suffix.isdigit():
                high_water[act_id] = max(high_water.get(act_id, 0), int(suffix))
        if images is not None or image_links is not None:
            mapping = {}
            for im in (images or []):
                old = int(im['image_id'])
                mapping[old] = _persist_image(con, im['register_id'], im)
            for link in (image_links or []):
                original_id = int(link['image_id'])
                if original_id not in mapping:
                    raise ValueError(f'Bildreferenz {original_id} fehlt im Excel-Blatt SourceImages.')
                act_id = link['act_id']
                new_id = mapping[original_id]
                sequence = int(link['sequence_no'])
                # Import does not remove previously existing image links.
                con.execute('''
                    INSERT INTO act_images(act_id,image_id,sequence_no) VALUES (?,?,?)
                    ON CONFLICT(act_id,image_id) DO UPDATE SET sequence_no=excluded.sequence_no
                ''', (act_id,new_id,sequence))
        if source_refs is not None:
            for act_id, refs in source_refs.items():
                found = con.execute('SELECT register_id FROM nas WHERE act_id=?', (act_id,)).fetchone()
                if not found:
                    raise ValueError(f'Quellenreferenz zu unbekanntem Akt: {act_id}')
                _save_act_images(con, act_id, found['register_id'], refs)
        for event in (transcription_events or []):
            con.execute('''
                INSERT OR IGNORE INTO transcription_events
                    (event_uid,act_id,recorded_at_utc,actor_name,event_type,capture_status)
                VALUES (?,?,?,?,?,?)
            ''', tuple(event.get(c) for c in (
                'event_uid','act_id','recorded_at_utc','actor_name','event_type','capture_status'
            )))
        for act_id, maximum in high_water.items():
            con.execute(
                'INSERT INTO id_counters(act_id, last_ordinal) VALUES (?, ?) '
                'ON CONFLICT(act_id) DO UPDATE SET last_ordinal=MAX(last_ordinal, excluded.last_ordinal)',
                (act_id, maximum),
            )
        refresh_vocabulary(con)
    return len(registers), len(nas_rows), len(participants)


def export_rows(path: str | Path = DB_DEFAULT) -> tuple[list[dict], list[dict], list[dict]]:
    with connect(path) as con:
        return (
            _dicts(con.execute('SELECT * FROM registers ORDER BY register_id')),
            _dicts(con.execute('SELECT * FROM nas ORDER BY act_id')),
            _dicts(con.execute('SELECT * FROM participants ORDER BY act_id, role, sequence_no')),
        )

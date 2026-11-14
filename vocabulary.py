"""CtC v1.5: source-faithful vocabulary suggestions derived from completed acts.

The vocabulary is an index, NOT a normalization dictionary or a claim of identity.
Every accepted suggestion is still manually checked against the source. A corrected
participant automatically removes its old word from this materialized index.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

VOCAB_KINDS = ('given_name', 'surname', 'profession')
SOURCE_FIELDS = {
    'given_name': ('given_name_raw', 'given_name_title_raw'),
    'surname': ('surname_raw', 'surname_title_raw'),
    'profession': ('profession_raw',),
}
FIELD_TO_KIND = {
    'given_name_raw': 'given_name',
    'given_name_title_raw': 'given_name',
    'surname_raw': 'surname',
    'surname_title_raw': 'surname',
    'profession_raw': 'profession',
}


def eligible_vocabulary_value(value: Any) -> bool:
    """Exclude missing codes and uncertain/editorial readings from suggestions.

    This does not remove or modify such values in the historical source tables.
    """
    if not isinstance(value, str):
        return False
    text = value.strip()
    if not text or text.casefold() in {'x', 'q'}:
        return False
    # CtC transcription notation: (…), […], ? indicate uncertain/added text.
    if any(char in text for char in ('(', ')', '[', ']', '?', '…')):
        return False
    return True


def refresh_vocabulary(con: sqlite3.Connection) -> None:
    """Rebuild all three vocabularies transactionally from completed source PRIs.

    UNION deduplicates the same spelling on a participant's title and body.
    Spellings are kept distinct and never standardized. This stays consistent
    across additions, deletions, draft/complete transitions and corrections.
    """
    available = {row[1] for row in con.execute('PRAGMA table_info(participants)')}
    clauses = []
    for kind, columns in SOURCE_FIELDS.items():
        for column in columns:
            if column not in available:
                continue
            clauses.append(
                f"SELECT p.participant_id, '{kind}' AS kind, TRIM(p.{column}) AS value_raw "
                "FROM participants p JOIN nas n ON n.act_id=p.act_id "
                f"WHERE n.capture_status='complete' AND p.{column} IS NOT NULL"
            )
    candidates = con.execute(' UNION '.join(clauses)).fetchall() if clauses else []
    counts: dict[tuple[str, str], int] = {}
    for _participant_id, kind, value in candidates:
        if eligible_vocabulary_value(value):
            counts[(kind, value)] = counts.get((kind, value), 0) + 1
    con.execute('DELETE FROM vocabulary_entries')
    if counts:
        con.executemany('''
            INSERT INTO vocabulary_entries(kind,value_raw,occurrence_count)
            VALUES (?,?,?)
        ''', [(kind, value, count) for (kind, value), count in sorted(counts.items())])


def list_vocabulary(kind: str, path: str | Path, *, limit: int = 3000) -> list[dict[str, Any]]:
    """Frequency-first suggestions (global corpus; contextual ranking can follow)."""
    if kind not in VOCAB_KINDS:
        raise ValueError(f'Unbekannte Wörterbuchkategorie: {kind}')
    if limit < 1:
        return []
    with sqlite3.connect(path) as con:
        return [dict(value_raw=row[0], occurrence_count=row[1]) for row in con.execute('''
            SELECT value_raw,occurrence_count FROM vocabulary_entries
            WHERE kind=? ORDER BY occurrence_count DESC, value_raw COLLATE NOCASE, value_raw
            LIMIT ?
        ''', (kind, limit))]


def vocabulary_counts(path: str | Path) -> dict[str, int]:
    with sqlite3.connect(path) as con:
        found = dict(con.execute('SELECT kind, COUNT(*) FROM vocabulary_entries GROUP BY kind'))
    return {kind: found.get(kind, 0) for kind in VOCAB_KINDS}

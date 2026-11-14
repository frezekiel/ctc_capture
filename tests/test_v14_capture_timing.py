"""CtC 1.4: measured time to first completion, legacy preservation and Excel roundtrip."""
from datetime import datetime, timezone
from io import BytesIO
import sqlite3

import pandas as pd
import pytest

from database import (
    _duration_seconds, connect, create_register, export_rows, init_db, load_capture,
    save_capture,
)
from models import new_capture, selected_participants
from excel_io import export_excel, import_excel


def make_register(path):
    create_register({'register_id': 'R1875', 'comune': 'Girifalco',
                     'register_type': 'NAS', 'year': '1875'}, path)


def make_act(number='1'):
    draft = new_capture('R1875')
    draft['nas']['act_number_raw'] = number
    draft['nas']['capture_started_at_utc'] = '2026-11-14T12:00:00+00:00'
    for p in draft['participants']:
        if p['role'] in ('child', 'mother', 'declarant'):
            p['given_name_raw'] = p['role']
    return draft


def test_seconds_precision_and_invalid_clock():
    assert _duration_seconds('2026-11-14T12:00:00+00:00',
                             '2026-11-14T12:05:00+00:00') == 300
    assert _duration_seconds('2026-11-14T13:00:00+01:00',
                             '2026-11-14T12:05:00+00:00') == 300
    assert _duration_seconds(None, '2026-11-14T12:05:00+00:00') is None
    assert _duration_seconds('2026-11-14T12:06:00+00:00',
                             '2026-11-14T12:05:00+00:00') is None
    assert _duration_seconds('malformed', '2026-11-14T12:05:00+00:00') is None
    assert _duration_seconds('2026-11-14T12:00:00',
                             '2026-11-14T12:05:00+00:00') is None


def test_first_complete_save_records_300_seconds_and_edits_do_not_overwrite(db_path, monkeypatch):
    make_register(db_path)
    import database
    monkeypatch.setattr(database, '_utc_now', lambda: '2026-11-14T12:05:00+00:00')
    draft = make_act()
    act_id = save_capture(draft['nas'], selected_participants(draft), db_path, complete=True)
    act, ppl = load_capture(act_id, db_path)
    assert act['capture_started_at_utc'] == '2026-11-14T12:00:00+00:00'
    assert act['capture_saved_at_utc'] == '2026-11-14T12:05:00+00:00'
    assert act['capture_duration_seconds'] == 300
    assert act['capture_status'] == 'complete'
    monkeypatch.setattr(database, '_utc_now', lambda: '2026-11-15T17:00:00+00:00')
    act.update(capture_started_at_utc='2026-11-15T16:50:00+00:00',
               capture_saved_at_utc='2026-11-15T17:00:00+00:00',
               capture_duration_seconds=600,
               transcription_note='Spätere Korrektur')
    save_capture(act, ppl, db_path, complete=True)
    updated, _ = load_capture(act_id, db_path)
    assert updated['capture_started_at_utc'] == '2026-11-14T12:00:00+00:00'
    assert updated['capture_saved_at_utc'] == '2026-11-14T12:05:00+00:00'
    assert updated['capture_duration_seconds'] == 300
    assert updated['transcription_note'] == 'Spätere Korrektur'
    assert updated['updated_at_utc'] == '2026-11-15T17:00:00+00:00'


def test_draft_not_counted_as_complete_until_first_completion(db_path, monkeypatch):
    make_register(db_path)
    import database
    monkeypatch.setattr(database, '_utc_now', lambda: '2026-11-14T12:02:00+00:00')
    draft = make_act()
    act_id = save_capture(draft['nas'], selected_participants(draft), db_path, complete=False)
    act, ppl = load_capture(act_id, db_path)
    assert act['transcribed_at_utc'] == '2026-11-14T12:02:00+00:00'
    assert act['capture_started_at_utc'] == '2026-11-14T12:00:00+00:00'
    assert act['capture_saved_at_utc'] is None
    assert act['capture_duration_seconds'] is None
    monkeypatch.setattr(database, '_utc_now', lambda: '2026-11-14T12:05:00+00:00')
    save_capture(act, ppl, db_path, complete=True)
    act, ppl = load_capture(act_id, db_path)
    assert act['capture_saved_at_utc'] == '2026-11-14T12:05:00+00:00'
    assert act['capture_duration_seconds'] == 300
    # Saving as draft later does not discard the measured duration.
    monkeypatch.setattr(database, '_utc_now', lambda: '2026-11-16T16:00:00+00:00')
    save_capture(act, ppl, db_path, complete=False)
    after, _ = load_capture(act_id, db_path)
    assert after['capture_saved_at_utc'] == '2026-11-14T12:05:00+00:00'
    assert after['capture_duration_seconds'] == 300


def test_legacy_act_not_given_invented_capture_duration_on_update(db_path, monkeypatch):
    make_register(db_path)
    import database
    monkeypatch.setattr(database, '_utc_now', lambda: '2026-11-14T12:05:00+00:00')
    draft = make_act()
    draft['nas']['capture_started_at_utc'] = None
    act_id = save_capture(draft['nas'], selected_participants(draft), db_path, complete=True)
    act, ppl = load_capture(act_id, db_path)
    assert act['capture_started_at_utc'] is None
    assert act['capture_saved_at_utc'] is None
    assert act['capture_duration_seconds'] is None
    act['capture_started_at_utc'] = '2026-11-14T12:00:00+00:00'
    save_capture(act, ppl, db_path, complete=True)
    updated, _ = load_capture(act_id, db_path)
    assert all(updated[k] is None for k in (
        'capture_started_at_utc', 'capture_saved_at_utc', 'capture_duration_seconds'))


def test_invalid_future_start_rejected_and_leaves_no_act(db_path, monkeypatch):
    make_register(db_path)
    import database
    monkeypatch.setattr(database, '_utc_now', lambda: '2026-11-14T12:05:00+00:00')
    draft = make_act()
    draft['nas']['capture_started_at_utc'] = '2026-11-14T12:08:00+00:00'
    with pytest.raises(ValueError, match='Messbeginn'):
        save_capture(draft['nas'], selected_participants(draft), db_path, complete=True)
    assert export_rows(db_path)[1] == []


def test_excel_roundtrip_preserves_measured_timing(db_path, tmp_path, monkeypatch):
    make_register(db_path)
    import database
    monkeypatch.setattr(database, '_utc_now', lambda: '2026-11-14T12:05:00+00:00')
    draft = make_act()
    act_id = save_capture(draft['nas'], selected_participants(draft), db_path, complete=True)
    excel = export_excel(db_path)
    sheets = pd.read_excel(BytesIO(excel), sheet_name=None, dtype=str, keep_default_na=False)
    assert sheets['NAS'].loc[0, 'capture_started_at_utc'] == '2026-11-14T12:00:00+00:00'
    assert sheets['NAS'].loc[0, 'capture_saved_at_utc'] == '2026-11-14T12:05:00+00:00'
    assert sheets['NAS'].loc[0, 'capture_duration_seconds'] == '300'
    recreated = tmp_path / 'restored.sqlite'
    init_db(recreated)
    assert import_excel(excel, recreated) == (1, 1, 6)
    row, _ = load_capture(act_id, recreated)
    assert row['capture_duration_seconds'] == 300
    # Reimport old workbook without 1.4 columns: must NOT erase timing.
    old_like = BytesIO()
    with pd.ExcelWriter(old_like, engine='openpyxl') as writer:
        for sheet, frame in sheets.items():
            if sheet == 'NAS':
                frame = frame.drop(columns=['capture_started_at_utc',
                                            'capture_saved_at_utc', 'capture_duration_seconds'])
            frame.to_excel(writer, sheet_name=sheet, index=False)
    import_excel(old_like.getvalue(), recreated)
    updated, _ = load_capture(act_id, recreated)
    assert updated['capture_duration_seconds'] == 300


def test_v13_to_v14_sqlite_backup_and_idempotent_upgrade(tmp_path):
    """Simulated old NAS schema: no new columns, existing original act retained."""
    path = tmp_path / 'ctc.sqlite'
    from shutil import copyfile
    from pathlib import Path
    # Bundled genuine v1.3 schema: unlike a build-specific path, works on Windows.
    source = Path(__file__).parent / 'fixtures' / 'ctc_v13_synthetic.sqlite'
    copyfile(source, path)
    with sqlite3.connect(path) as con:
        cols = {r[1] for r in con.execute('PRAGMA table_info(nas)')}
        assert 'capture_started_at_utc' not in cols
    init_db(path)
    backup = tmp_path / 'ctc.pre_v1_4.sqlite'
    assert backup.exists()
    with sqlite3.connect(backup) as con:
        assert 'capture_started_at_utc' not in {r[1] for r in con.execute('PRAGMA table_info(nas)')}
        assert con.execute('SELECT COUNT(*) FROM nas').fetchone()[0] == 1
    with connect(path) as con:
        cols = {r[1] for r in con.execute('PRAGMA table_info(nas)')}
        assert {'capture_started_at_utc','capture_saved_at_utc','capture_duration_seconds'} <= cols
        assert con.execute('SELECT COUNT(*) FROM nas').fetchone()[0] == 1
        assert con.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert con.execute('PRAGMA foreign_key_check').fetchall() == []
    init_db(path)
    assert backup.exists()

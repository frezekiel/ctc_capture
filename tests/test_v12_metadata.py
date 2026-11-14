"""CtC 1.2: provenance metadata, safe migration, source-bound residence resolution."""
from pathlib import Path
import sqlite3
from copy import deepcopy

import pytest

import database
from capture_defaults import prepare_new_capture
from database import (
    init_db, create_register, load_capture, save_capture, list_acts, last_transcriber,
    resolved_witness_domiciles, connect, export_rows,
)
from excel_io import export_excel, import_excel, parse_workbook
from models import selected_participants
from validation import validate_capture


def make_reg(db_path):
    create_register(dict(register_id="R1", comune="Girifalco", register_type="NAS", year="1875"), db_path)


def make_draft(num="1"):
    draft=prepare_new_capture("R1", comune="Girifalco")
    draft["nas"]["act_number_raw"]=num
    return draft


def test_new_capture_metadata_and_profile_are_persistent(db_path, monkeypatch):
    make_reg(db_path)
    d=make_draft()
    d['nas'].update(transcriber_name='D. Test', source_legibility_1_5='4',
                    transcription_note='Schreiber setzt Alter an falsche Stelle.',
                    session_note='Lupe verwendet.')
    monkeypatch.setattr(database, '_utc_now', lambda: '2026-11-14T10:00:00+00:00')
    act=save_capture(d['nas'], selected_participants(d),db_path)
    saved,ppl=load_capture(act,db_path)
    assert saved['transcriber_name']=='D. Test'
    assert saved['source_legibility_1_5']==4
    assert saved['transcribed_at_utc']=='2026-11-14T10:00:00+00:00'
    assert saved['updated_at_utc']==saved['transcribed_at_utc']
    assert saved['transcription_note'].startswith('Schreiber')
    assert saved['session_note']=='Lupe verwendet.'
    assert last_transcriber(db_path)=='D. Test'
    fresh=prepare_new_capture('R1', comune='Girifalco',transcriber_name=last_transcriber(db_path))
    assert fresh['nas']['transcriber_name']=='D. Test'
    assert fresh['nas']['transcribed_at_utc'] is None
    monkeypatch.setattr(database, '_utc_now', lambda: '2026-11-15T11:00:00+00:00')
    saved['transcription_note']='Korrektur nach Quellenvergleich'
    save_capture(saved,ppl,db_path)
    updated,_=load_capture(act,db_path)
    assert updated['transcribed_at_utc']=='2026-11-14T10:00:00+00:00'
    assert updated['updated_at_utc']=='2026-11-15T11:00:00+00:00'
    assert updated['transcription_note']=='Korrektur nach Quellenvergleich'


def test_legibility_validation_and_database_constraint(db_path):
    make_reg(db_path)
    d=make_draft()
    d['nas']['source_legibility_1_5']='6'
    assert any('Lesbarkeit' in p for p in validate_capture(d['nas'],selected_participants(d)))
    with pytest.raises(ValueError,match='Lesbarkeit'):
        save_capture(d['nas'],selected_participants(d),db_path)
    d['nas']['source_legibility_1_5']='3'
    aid=save_capture(d['nas'],selected_participants(d),db_path)
    with pytest.raises(sqlite3.IntegrityError):
        with connect(db_path) as con:
            con.execute('UPDATE nas SET source_legibility_1_5=8 WHERE act_id=?',(aid,))


def test_witness_intra_act_reference_and_explicit_override(db_path):
    make_reg(db_path)
    d=make_draft()
    d['nas']['act_comune_raw']='Cortale'  # overrides register default
    d['nas']['witness_domicile_collective_raw']='entrambi residenti in questo comune'
    witnesses=[p for p in d['participants'] if p['role']=='witness']
    assert all(p['domicile_raw'] is None for p in witnesses)
    act=save_capture(d['nas'],selected_participants(d),db_path)
    resolved=resolved_witness_domiciles(act,db_path)
    assert len(resolved)==2
    assert [x['domicile_resolved'] for x in resolved]==['Cortale','Cortale']
    assert all(x['resolution_basis']=='intra_act_collective_reference' for x in resolved)
    stored,people=load_capture(act,db_path)
    assert all(x['domicile_raw'] is None for x in people if x['role']=='witness')
    witnesses=[p for p in people if p['role']=='witness']
    witnesses[1]['domicile_raw']='Lamezia'
    save_capture(stored,people,db_path)
    resolved=resolved_witness_domiciles(act,db_path)
    assert [x['domicile_resolved'] for x in resolved]==['Cortale','Lamezia']
    assert [x['resolution_basis'] for x in resolved]==[
        'intra_act_collective_reference','explicit_individual_raw']


def test_entrambi_cannot_describe_three_witnesses(db_path):
    from models import new_participant
    make_reg(db_path)
    d=make_draft()
    d['nas']['witness_domicile_collective_raw']='entrambi residenti in questo comune'
    d['participants'].append(new_participant('witness', 3))
    aid=save_capture(d['nas'], selected_participants(d),db_path)
    assert all(r['domicile_resolved'] is None for r in resolved_witness_domiciles(aid,db_path))


def test_old_export_import_preserves_existing_provenance(db_path):
    make_reg(db_path)
    d=make_draft()
    d['nas'].update(transcriber_name='D. Test',source_legibility_1_5='2')
    aid=save_capture(d['nas'],selected_participants(d),db_path)
    from pathlib import Path
    old_spreadsheet=Path(__file__).resolve().parents[1]/'samples'/'ctc_capture_test.xlsx'
    # Its 1.0-era columns lack the new metadata. Reimport must not NULL them.
    import_excel(old_spreadsheet,db_path)
    now,_=load_capture(aid,db_path)
    assert now['transcriber_name']=='D. Test'
    assert now['source_legibility_1_5']==2
    assert now['transcribed_at_utc'] is not None
    exported=export_excel(db_path)
    r,n,p=parse_workbook(exported)
    assert n[0]['transcriber_name']=='D. Test'
    assert n[0]['source_legibility_1_5']=='2'
    assert n[0]['transcription_note'] is None


def test_migrate_v11_database_in_place_and_create_consistent_backup(tmp_path):
    path=tmp_path/'ctc.sqlite'
    # Representative old schema: metadata columns do not yet exist.
    with sqlite3.connect(path) as con:
        con.executescript('''
            CREATE TABLE registers (register_id TEXT PRIMARY KEY, comune TEXT, register_type TEXT, year TEXT);
            CREATE TABLE nas (act_id TEXT PRIMARY KEY, register_id TEXT NOT NULL REFERENCES registers(register_id),
                act_number_raw TEXT, act_comune_raw TEXT, witness_domicile_collective_raw TEXT,
                capture_status TEXT NOT NULL DEFAULT 'draft', mother_relationship_to_declarant_raw TEXT);
            CREATE TABLE participants (participant_id TEXT PRIMARY KEY, act_id TEXT REFERENCES nas(act_id),
                role TEXT, sequence_no INTEGER, domicile_raw TEXT);
            INSERT INTO registers VALUES ('R1','Girifalco','NAS','1875');
            INSERT INTO nas VALUES ('NAS1875_003','R1','3','Girifalco',
                'entrambi residenti in questo comune','complete',NULL);
            INSERT INTO participants VALUES ('NAS1875_003_01','NAS1875_003','witness',1,NULL);
            INSERT INTO participants VALUES ('NAS1875_003_02','NAS1875_003','witness',2,NULL);
        ''')
    init_db(path)
    backup=tmp_path/'ctc.pre_v1_2.sqlite'
    assert backup.exists()
    with sqlite3.connect(backup) as c:
        assert len(c.execute('PRAGMA table_info(nas)').fetchall())==7
        assert c.execute('SELECT COUNT(*) FROM participants').fetchone()[0]==2
    with connect(path) as c:
        assert c.execute('SELECT COUNT(*) FROM nas').fetchone()[0]==1
        assert c.execute('SELECT COUNT(*) FROM participants').fetchone()[0]==2
        row=c.execute('SELECT * FROM nas').fetchone()
        assert row['transcriber_name'] is None
        assert row['transcribed_at_utc'] is None
        assert row['source_legibility_1_5'] is None
    assert [r['domicile_resolved'] for r in resolved_witness_domiciles('NAS1875_003',path)]==['Girifalco','Girifalco']
    init_db(path)
    assert backup.exists()  # second invocation is idempotent


def test_audit_events_preserve_attribution_across_edits(db_path, monkeypatch):
    from database import export_transcription_events
    make_reg(db_path)
    d=make_draft()
    d['nas']['transcriber_name']='Erste Person'
    monkeypatch.setattr(database,'_utc_now',lambda:'2026-11-14T08:00:00+00:00')
    aid=save_capture(d['nas'],selected_participants(d),db_path)
    nas,people=load_capture(aid,db_path)
    nas['transcriber_name']='Zweite Person'
    nas['transcription_note']='Ergänzung'
    monkeypatch.setattr(database,'_utc_now',lambda:'2026-11-15T09:00:00+00:00')
    save_capture(nas,people,db_path)
    events=export_transcription_events(db_path)
    assert len(events)==2
    assert [e['actor_name'] for e in events]==['Erste Person','Zweite Person']
    assert [e['event_type'] for e in events]==['create','update']
    assert len({e['event_uid'] for e in events})==2
    out=export_excel(db_path)
    target=db_path.with_name('imported.sqlite')
    database.init_db(target)
    assert import_excel(out,target)==(1,1,6)
    imported=export_transcription_events(target)
    assert [(e['actor_name'],e['event_type']) for e in imported]==[
        ('Erste Person','create'),('Zweite Person','update')]
    import_excel(out,target)
    assert len(export_transcription_events(target))==2

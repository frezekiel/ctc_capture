"""CtC 1.3: editable defaults, source provenance, round-trip compatibility."""
from io import BytesIO
from pathlib import Path
import sqlite3

import pandas as pd
import pytest

from capture_defaults import expand_meridian, prepare_new_capture
from database import (
    init_db, create_register, save_capture, load_capture, list_acts,
    export_image_rows, load_source_images, export_rows,
    last_created_act_defaults, connect,
)
from excel_io import export_excel, import_excel
from models import selected_participants
from validation import completion_gaps


def make_register(path, ident='REG1875', year='1875', comune='Girifalco'):
    create_register(dict(register_id=ident, comune=comune, register_type='NAS', year=year), path)


def make_act(path, num, month='Gennajo', image='238', count='1548', url='https://familysearch.org/ark:/scan238'):
    draft = prepare_new_capture('REG1875', comune='Girifalco', register_year='1875',
                                previous_act_month=month)
    draft['nas']['act_number_raw'] = str(num)
    draft['nas']['act_month_raw'] = month
    draft['nas']['act_day_raw'] = str(num)
    draft['nas']['transcriber_name'] = 'D. Researcher'
    for p in draft['participants']:
        if p['role'] in {'child','declarant','mother'}:
            p['given_name_raw'] = p['role']
    images = [dict(image_number_raw=image, image_total_raw=count, familysearch_url=url)] if image else []
    aid = save_capture(draft['nas'], selected_participants(draft), path,
                       source_images=images, complete=False)
    return aid


def test_short_meridian_does_not_rewrite_other_paleography():
    assert [expand_meridian(x) for x in ('a','A','p','P','ante','po','post','ante?','')] == [
        'ante','ante','po','po','ante','po','post','ante?','']


def test_register_year_and_latest_created_month_avoids_edits(tmp_path):
    db = tmp_path/'ctc.sqlite'; init_db(db);make_register(db)
    aid1=make_act(db,1,'Gennajo')
    aid2=make_act(db,2,'Febbrajo', image='239',url='https://familysearch.org/ark:/scan239')
    older,people = load_capture(aid1,db)
    older['act_month_raw']='Dicembre'
    save_capture(older,people,db) # old act edited; does not change the latest-created act
    got=last_created_act_defaults('REG1875',db)
    assert got['act_month_raw']=='Febbrajo'
    assert got['source_image']['image_number_raw']=='239'
    fresh=prepare_new_capture('REG1875',comune='Girifalco',register_year='1875',
                              previous_act_month=got['act_month_raw'],previous_source_image=got['source_image'])
    assert fresh['nas']['act_year_raw']=='1875'
    assert fresh['nas']['act_month_raw']=='Febbrajo'
    assert fresh['source_images'][0]['image_number_raw']=='239'
    assert fresh['participants'][2]['age_unit_raw']=='anni'
    assert fresh['nas']['act_day_raw'] is None
    make_register(db,'REG1876','1876','Cortale')
    assert last_created_act_defaults('REG1876',db)=={'act_month_raw':None,'source_image':None}


def test_db_resolved_locality_keeps_raw_empty(tmp_path):
    db=tmp_path/'ctc.sqlite';init_db(db);make_register(db)
    draft=prepare_new_capture('REG1875',comune='Girifalco')
    draft['nas'].update(act_number_raw='9', act_comune_raw='Cortale')
    aid=save_capture(draft['nas'],selected_participants(draft),db)
    with connect(db) as con:
        declarant=con.execute("""SELECT p.domicile_raw,r.domicile_resolved,r.resolution_basis
            FROM participants p JOIN participant_domicile_resolved r USING(participant_id)
            WHERE p.act_id=? AND p.role='declarant'""", (aid,)).fetchone()
        assert declarant['domicile_raw'] is None
        assert declarant['domicile_resolved']=='Cortale'
        assert declarant['resolution_basis']=='suggested_from_act_comune'
    nas, people=load_capture(aid,db)
    d=next(p for p in people if p['role']=='declarant')
    d['domicile_raw']='Lamezia'
    save_capture(nas,people,db)
    with connect(db) as con:
        domicile=con.execute("""SELECT domicile_resolved,resolution_basis FROM participant_domicile_resolved
            WHERE act_id=? AND role='declarant'""",(aid,)).fetchone()
    assert domicile['domicile_resolved']=='Lamezia'
    assert domicile['resolution_basis']=='explicit_individual_raw'


def test_one_image_shared_excel_flatten_and_no_empty_image_sheets(tmp_path):
    db=tmp_path/'ctc.sqlite';init_db(db);make_register(db)
    make_act(db,1);make_act(db,2)
    out=export_excel(db)
    pages=pd.read_excel(BytesIO(out),sheet_name=None,dtype=str,keep_default_na=False)
    assert set(pages)=={'Registers','NAS','Participants','TranscriptionEvents'}
    assert 'SourceImages' not in pages and 'ActImages' not in pages
    assert list(pages['NAS']['image_number'])==['238','238']
    assert list(pages['NAS']['image_total'])==['1548','1548']
    assert all(pages['NAS']['source_url'].str.startswith('https:'))
    assert 'domicile_resolved' in pages['Participants']
    assert 'domicile_resolution_basis' in pages['Participants']
    migrated=tmp_path/'migrated.sqlite';init_db(migrated)
    assert import_excel(out,migrated)==(1,2,12)
    assert len(export_image_rows(migrated)[0])==1
    assert len(export_image_rows(migrated)[1])==2
    assert import_excel(out,migrated)==(1,2,12)
    assert len(export_image_rows(migrated)[1])==2


def test_multi_image_act_roundtrip_and_extra_sheet(tmp_path):
    db=tmp_path/'ctc.sqlite';init_db(db);make_register(db)
    aid=make_act(db,1)
    nas, people=load_capture(aid,db)
    original=load_source_images(aid,db)
    original.append(dict(image_number_raw='239',image_total_raw='1548',
                         familysearch_url='https://familysearch.org/ark:/scan239'))
    save_capture(nas,people,db,source_images=original)
    data=export_excel(db)
    sheets=pd.read_excel(BytesIO(data),sheet_name=None,dtype=str,keep_default_na=False)
    assert 'AdditionalImages' in sheets
    assert list(sheets['AdditionalImages']['sequence_no'])==['2']
    target=tmp_path/'t.sqlite';init_db(target)
    assert import_excel(data,target)==(1,1,6)
    refs=load_source_images(aid,target)
    assert [r['image_number_raw'] for r in refs]==['238','239']
    assert len(export_image_rows(target)[0])==2


def test_flat_excel_zero_ref_clears_only_intended_act(tmp_path):
    db=tmp_path/'ctc.sqlite';init_db(db);make_register(db)
    a=make_act(db,1); b=make_act(db,2)
    data=export_excel(db)
    frames=pd.read_excel(BytesIO(data),sheet_name=None,dtype=str,keep_default_na=False)
    frames['NAS'].loc[frames['NAS']['act_id']==a,['source_url','image_number','image_total']]=''
    out=BytesIO()
    with pd.ExcelWriter(out,engine='openpyxl') as wr:
        for sheet,frame in frames.items():frame.to_excel(wr,sheet_name=sheet,index=False)
    import_excel(out.getvalue(),db)
    assert load_source_images(a,db)==[]
    assert len(load_source_images(b,db))==1


def test_optional_fields_are_not_completion_gaps():
    draft=prepare_new_capture('REG1875',comune='Girifalco',register_year='1875')
    draft['nas'].update(act_day_raw='1',act_month_raw='Gennajo',birth_day_raw='1',birth_month_raw='corrente')
    p=next(p for p in draft['participants'] if p['role']=='child')
    p.update(given_name_raw='Anna',sex_raw='femminile')
    assert completion_gaps(draft['nas'], selected_participants(draft))==[]
    assert p['honorific_title_raw'] is None

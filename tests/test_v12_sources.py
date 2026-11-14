"""CtC 1.2: image-to-act mapping, workbook preservation, and atomicity."""
from pathlib import Path
import sqlite3
import pytest

from capture_defaults import prepare_new_capture
from database import (create_register, connect, export_image_rows, load_capture,
                      load_source_images, save_capture, resolved_witness_domiciles)
from excel_io import export_excel, import_excel, parse_workbook
from models import selected_participants


def reg(p):
    create_register(dict(register_id='R1',comune='Girifalco',year='1875',register_type='NAS'),p)


def save_act(p,num,imgs=None):
    d=prepare_new_capture('R1',comune='Girifalco')
    d['nas']['act_number_raw']=str(num)
    return save_capture(d['nas'],selected_participants(d),p,source_images=imgs)


def img(n='228',tot='1536',url='https://www.familysearch.org/ark:/61903/3:1:example'):
    return dict(image_number_raw=n,image_total_raw=tot,familysearch_url=url)


def test_same_image_multiple_acts_and_multi_image_act(db_path):
    reg(db_path)
    a=save_act(db_path,1,[img()])
    b=save_act(db_path,2,[img()])
    c=save_act(db_path,3,[img(),img('229')])
    imgs,links=export_image_rows(db_path)
    assert len(imgs)==2
    assert len(links)==4
    assert len({x['image_id'] for x in links if x['act_id'] in (a,b)})==1
    assert [x['image_number_raw'] for x in load_source_images(c,db_path)]==['228','229']
    assert [x['sequence_no'] for x in load_source_images(c,db_path)]==[1,2]
    # Editing a single act does not delete/reassign shared scans for other acts.
    nas,people=load_capture(a,db_path)
    nas['transcription_note']='Quelle verglichen.'
    save_capture(nas,people,db_path,source_images=[])
    assert load_source_images(a,db_path)==[]
    assert len(load_source_images(b,db_path))==1
    assert len(load_source_images(c,db_path))==2


def test_image_excel_export_import_preserves_relationships(tmp_path):
    p=tmp_path/'a.sqlite'
    from database import init_db
    init_db(p);reg(p)
    save_act(p,1,[img()]);save_act(p,2,[img()]);save_act(p,3,[img(),img('229')])
    data=export_excel(p)
    assert data[:2]==b'PK'
    r,n,people=parse_workbook(data)
    assert len(n)==3 and len(people)==18
    target=tmp_path/'b.sqlite'
    init_db(target)
    assert import_excel(data,target)==(1,3,18)
    imgs,links=export_image_rows(target)
    assert len(imgs)==2 and len(links)==4
    assert import_excel(data,target)==(1,3,18)  # idempotent
    assert len(export_image_rows(target)[1])==4


def test_invalid_image_rolls_back_act_and_participants(db_path):
    reg(db_path)
    with pytest.raises(ValueError,match='Quellenlink'):
        save_act(db_path,1,[img(url='not-a-url')])
    with connect(db_path) as con:
        assert con.execute('SELECT COUNT(*) FROM nas').fetchone()[0]==0
        assert con.execute('SELECT COUNT(*) FROM participants').fetchone()[0]==0
        assert con.execute('SELECT COUNT(*) FROM source_images').fetchone()[0]==0


def test_source_image_duplicate_reference_for_one_act_is_rejected(db_path):
    reg(db_path)
    with pytest.raises(ValueError,match='mehrfach'):
        save_act(db_path,1,[img(),img()])
    with connect(db_path) as con:
        assert con.execute('SELECT COUNT(*) FROM nas').fetchone()[0]==0


def test_legacy_spreadsheet_with_no_source_sheets_still_imports(db_path):
    sample=Path(__file__).resolve().parents[1]/'samples'/'ctc_capture_test.xlsx'
    assert import_excel(sample,db_path)==(1,1,6)
    assert export_image_rows(db_path)==([],[])

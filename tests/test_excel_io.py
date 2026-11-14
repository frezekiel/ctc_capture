from pathlib import Path
import pandas as pd
import pytest
from io import BytesIO
from database import export_rows, load_capture
from excel_io import parse_workbook, import_excel, export_excel

SAMPLE = Path(__file__).resolve().parents[1] / 'samples' / 'ctc_capture_test.xlsx'


def test_real_uploaded_workbook_parses():
    registers,nas,ppl=parse_workbook(SAMPLE)
    assert len(registers)==1 and len(nas)==1 and len(ppl)==6
    assert registers[0]['register_id']=='REG1875'
    assert nas[0]['birth_address_nr_raw']=='x'
    assert nas[0]['birth_month_raw']=='corrente'
    assert nas[0]['act_time_type_raw']=='po'
    assert nas[0]['mother_relationship_to_declarant_raw'] is None
    assert ppl[4]['surname_raw'].startswith('Ba(r)ile')
    assert ppl[0]['age_raw']=='x'


def test_import_stable_twice(db_path):
    counts=import_excel(SAMPLE,db_path)
    assert counts==(1,1,6)
    assert import_excel(SAMPLE,db_path)==counts
    regs,nas,ppl=export_rows(db_path)
    assert len(regs)==1 and len(nas)==1 and len(ppl)==6
    assert nas[0]['capture_status']=='draft'


def test_excel_roundtrip_preserves_raw_and_empty(db_path):
    import_excel(SAMPLE,db_path)
    payload=export_excel(db_path)
    assert payload[:2]==b'PK'
    r,n,p=parse_workbook(payload)
    assert len(p)==6
    assert n[0]['birth_address_nr_raw']=='x'
    assert n[0]['mother_relationship_to_declarant_raw'] is None
    assert p[4]['surname_raw'].startswith('Ba(r)ile')
    assert next(q for q in p if q['role']=='declarant')['given_name_raw']=='Giuseppe'
    assert next(q for q in p if q['role']=='declarant')['age_unit_raw']=='anni'
    assert n[0]['act_time_type_raw']=='po'


def test_literal_blank_and_x_remain_distinct(db_path):
    import_excel(SAMPLE,db_path)
    raw = load_capture('NAS1875_001',db_path)
    assert raw[0]['birth_address_nr_raw']=='x'
    assert raw[0]['mother_relationship_to_declarant_raw'] is None
    assert raw[1][0]['honorific_title_raw']=='x'


def test_missing_sheet_does_not_modify_database(db_path):
    data=BytesIO()
    with pd.ExcelWriter(data,engine='openpyxl') as writer:
        pd.DataFrame({'id':[1]}).to_excel(writer,sheet_name='Only',index=False)
    with pytest.raises(ValueError,match='Fehlende Excel-Blätter'):
        import_excel(data.getvalue(),db_path)
    assert export_rows(db_path)==([],[],[])


def test_import_foreign_key_error_atomic(db_path):
    data=pd.read_excel(SAMPLE,sheet_name=None,dtype=str,keep_default_na=False)
    data['Participants'].loc[0,'act_id']='NAS9999_999'
    out=BytesIO()
    with pd.ExcelWriter(out,engine='openpyxl') as writer:
        for name,df in data.items(): df.to_excel(writer,sheet_name=name,index=False)
    import sqlite3
    with pytest.raises(sqlite3.IntegrityError):
        import_excel(out.getvalue(),db_path)
    assert export_rows(db_path)==([],[],[])

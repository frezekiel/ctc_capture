import sqlite3
import pytest

from database import connect, create_register, export_rows, list_acts, load_capture, save_capture
from models import new_capture, new_participant, selected_participants, make_act_id, new_register_id


def sample_register(path):
    create_register(dict(register_id='REG1875', comune='Girifalco', register_type='NAS', year='1875'), path)


def sample_capture():
    d = new_capture('REG1875')
    d['nas'].update(act_number_raw='1', act_year_raw='1875', act_day_raw='quattro',
        act_month_raw='Gennajo', act_hour_raw='quattro', act_time_type_raw='po',
        birth_day_raw='tre', birth_month_raw='corrente', birth_address_nr_raw='x',
        mother_relationship_to_declarant_raw='sua moglie seco lui convivente',
        declarant_is_father='yes', father_mentioned='no')
    names = {
        'child': ('Catarina','Catalano'), 'sindaco':('Bonaventura','Antelitano'),
        'declarant':('Giuseppe','Catalano'),'mother':('Maria','Fodaro'),
    }
    for p in d['participants']:
        if p['role'] in names:
            p['given_name_raw'],p['surname_raw'] = names[p['role']]
        if p['role']=='child':
            p['given_name_title_raw']='Catarina';p['surname_title_raw']='Catalano'
    witnesses=[p for p in d['participants'] if p['role']=='witness']
    witnesses[0]['given_name_raw']='Rocco'; witnesses[0]['surname_raw']='Ba(r)ile'
    witnesses[1]['given_name_raw']='Domenico'; witnesses[1]['surname_raw']='Catalano'
    return d


def test_register_creation(db_path):
    sample_register(db_path)
    regs, nas, participants = export_rows(db_path)
    assert regs == [dict(register_id='REG1875', comune='Girifalco',register_type='NAS',year='1875')]
    assert nas == [] and participants == []


def test_capture_persists_six_participants(db_path):
    sample_register(db_path)
    d=sample_capture()
    act_id=save_capture(d['nas'], selected_participants(d), db_path, complete=True)
    assert act_id=='NAS1875_001'
    nas, ppl = load_capture(act_id,db_path)
    assert nas['birth_address_nr_raw']=='x'
    assert nas['mother_relationship_to_declarant_raw']=='sua moglie seco lui convivente'
    assert nas['capture_status']=='complete'
    assert len(ppl)==6
    assert [p['participant_id'] for p in ppl]==[f'{act_id}_{i:02d}' for i in range(1,7)]
    assert [p['role'] for p in ppl].count('witness')==2
    assert ppl[4]['surname_raw']=='Ba(r)ile'


def test_no_duplicate_declarant_as_father(db_path):
    sample_register(db_path)
    d=sample_capture()
    assert len(selected_participants(d))==6
    assert not any(p['role']=='father' for p in selected_participants(d))
    save_capture(d['nas'],selected_participants(d),db_path)
    assert len(load_capture('NAS1875_001',db_path)[1])==6


def test_conditional_father(db_path):
    d=sample_capture()
    father=new_participant('father')
    father.update(given_name_raw='Mario',surname_raw='Test')
    d['participants'].append(father)
    assert len(selected_participants(d))==6  # currently declarant=father
    d['nas']['declarant_is_father']='no'
    d['nas']['father_mentioned']='yes'
    assert len(selected_participants(d))==7
    assert selected_participants(d)[-1]['role']=='father'


def test_edit_same_ids_after_reopen(db_path):
    sample_register(db_path)
    d=sample_capture()
    act_id=save_capture(d['nas'], selected_participants(d), db_path)
    nas, ppl=load_capture(act_id,db_path)
    ids={p['participant_id'] for p in ppl}
    ppl[2]['profession_raw']='contadino'
    save_capture(nas,ppl,db_path)
    nas2,ppl2=load_capture(act_id,db_path)
    assert {p['participant_id'] for p in ppl2}==ids
    assert ppl2[2]['profession_raw']=='contadino'
    assert len(list_acts(db_path))==1


def test_add_witness_stable_ids(db_path):
    sample_register(db_path)
    d=sample_capture()
    aid=save_capture(d['nas'],selected_participants(d),db_path)
    nas,ppl=load_capture(aid,db_path)
    ids_before=[p['participant_id'] for p in ppl]
    w=new_participant('witness',3)
    w.update(given_name_raw='Paolo',surname_raw='Verdi')
    ppl.append(w)
    save_capture(nas,ppl,db_path)
    _,after=load_capture(aid,db_path)
    assert len(after)==7
    assert {p['participant_id'] for p in after}==set(ids_before)|{aid+'_07'}


def test_remove_witness_preserves_remaining_id(db_path):
    sample_register(db_path)
    d=sample_capture()
    aid=save_capture(d['nas'],selected_participants(d),db_path)
    nas,ppl=load_capture(aid,db_path)
    ppl=[p for p in ppl if p['participant_id']!=aid+'_05']
    for p in ppl:
        if p['participant_id']==aid+'_06': p['sequence_no']=1
    save_capture(nas,ppl,db_path)
    _,after=load_capture(aid,db_path)
    witnesses=[p for p in after if p['role']=='witness']
    assert len(witnesses)==1 and witnesses[0]['participant_id']==aid+'_06' and witnesses[0]['sequence_no']==1


def test_bad_sequence_does_not_modify_db(db_path):
    sample_register(db_path)
    d=sample_capture()
    aid=save_capture(d['nas'],selected_participants(d),db_path)
    nas,ppl=load_capture(aid,db_path)
    ppl[-1]['sequence_no']=1
    with pytest.raises(ValueError,match='Doppelte Positionen'):
        save_capture(nas,ppl,db_path)
    assert len(load_capture(aid,db_path)[1])==6


def test_sqlite_foreign_keys_enforced(db_path):
    with pytest.raises(sqlite3.IntegrityError):
        with connect(db_path) as con:
            con.execute('INSERT INTO nas(act_id,register_id,act_number_raw) VALUES (?,?,?)',
                        ('NAS1900_001','NOT_EXIST','1'))


def test_id_fallback_and_register_id():
    assert make_act_id(dict(year='1875',register_id='REG1875'),'1',set())=='NAS1875_001'
    assert make_act_id(dict(year='1875',register_id='REG1875_02'),'1',{'NAS1875_001'})=='NAS1875_001_REG1875_02'
    assert new_register_id('1875',{'REG1875'})=='REG1875_02'


def test_incomplete_draft_vs_complete(db_path):
    sample_register(db_path)
    d=new_capture('REG1875')
    d['nas']['act_number_raw']='9'
    aid=save_capture(d['nas'],selected_participants(d),db_path,complete=False)
    assert load_capture(aid,db_path)[0]['capture_status']=='draft'
    with pytest.raises(ValueError,match='Vorname'):
        save_capture(load_capture(aid,db_path)[0],load_capture(aid,db_path)[1],db_path,complete=True)


def test_rollback_when_invalid_participant_id_reassigned(db_path):
    sample_register(db_path)
    d=sample_capture()
    first=save_capture(d['nas'], selected_participants(d), db_path)
    second=new_capture('REG1875')
    second['nas']['act_number_raw']='2'
    second['participants'][0]['participant_id']=first+'_01'
    with pytest.raises(ValueError,match='anderem Akt'):
        save_capture(second['nas'],selected_participants(second),db_path)
    assert len(list_acts(db_path))==1  # nas INSERT rolled back as well


def test_deleted_identifier_is_not_reused(db_path):
    sample_register(db_path)
    d=sample_capture()
    aid=save_capture(d['nas'], selected_participants(d), db_path)
    nas,ppl=load_capture(aid,db_path)
    extra=new_participant('witness',3)
    extra['given_name_raw']='Paolo'
    ppl.append(extra)
    save_capture(nas,ppl,db_path)
    nas,ppl=load_capture(aid,db_path)
    ppl=[p for p in ppl if p['participant_id'] != aid+'_07']
    save_capture(nas,ppl,db_path)
    nas,ppl=load_capture(aid,db_path)
    replacement=new_participant('witness',3)
    replacement['given_name_raw']='Carlo'
    ppl.append(replacement)
    save_capture(nas,ppl,db_path)
    assert any(p['participant_id']==aid+'_08' for p in load_capture(aid,db_path)[1])

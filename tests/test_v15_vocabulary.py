"""CtC 1.5: historical vocabularies, corrections and schema migrations."""
from pathlib import Path
from shutil import copyfile
import sqlite3

import pytest
from database import (connect, init_db, create_register, save_capture, load_capture,
                      export_rows)
from models import new_capture, selected_participants
from vocabulary import eligible_vocabulary_value, list_vocabulary, vocabulary_counts
from excel_io import export_excel, import_excel


def make_register(path):
    create_register({'register_id':'R1875','comune':'Girifalco',
                     'register_type':'NAS','year':'1875'},path)


def make_act(number):
    draft=new_capture('R1875');draft['nas']['act_number_raw']=str(number)
    declarant=next(p for p in draft['participants'] if p['role']=='declarant')
    declarant.update(given_name_raw='Giuseppe',surname_raw='Catalano',profession_raw='contadino')
    child=next(p for p in draft['participants'] if p['role']=='child')
    child.update(given_name_title_raw='Giuseppe',given_name_raw='Giuseppe',
                 surname_title_raw='Catalano',surname_raw='Catalano')
    mother=next(p for p in draft['participants'] if p['role']=='mother')
    mother.update(given_name_raw='Maria',surname_raw='Fodaro')
    return draft


def values(kind,path):
    return {x['value_raw']:x['occurrence_count'] for x in list_vocabulary(kind,path)}


def test_empty_lists_and_views(db_path):
    assert vocabulary_counts(db_path)=={'given_name':0,'surname':0,'profession':0}
    with connect(db_path) as con:
        for table in ('vocabulary_given_names','vocabulary_surnames','vocabulary_professions'):
            assert con.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]==0


def test_completed_acts_build_frequency_lists_and_deduplicate_title(db_path):
    make_register(db_path)
    for n in (1,2):
        draft=make_act(n)
        save_capture(draft['nas'],selected_participants(draft),db_path,complete=True)
    assert values('given_name',db_path)['Giuseppe']==4
    assert values('surname',db_path)['Catalano']==4
    assert values('profession',db_path)['contadino']==2
    assert list_vocabulary('given_name',db_path)[0]['value_raw']=='Giuseppe'


def test_draft_does_not_pollute_and_completion_enables_words(db_path):
    make_register(db_path)
    draft=make_act(1)
    act_id=save_capture(draft['nas'],selected_participants(draft),db_path,complete=False)
    assert vocabulary_counts(db_path)['given_name']==0
    saved,people=load_capture(act_id,db_path)
    save_capture(saved,people,db_path,complete=True)
    assert values('given_name',db_path)['Giuseppe']==2


def test_corrected_name_and_occupation_remove_old_vocabulary(db_path):
    make_register(db_path)
    draft=make_act(1)
    act_id=save_capture(draft['nas'],selected_participants(draft),db_path,complete=True)
    saved,people=load_capture(act_id,db_path)
    declarant=next(p for p in people if p['role']=='declarant')
    declarant.update(given_name_raw='Gio.',surname_raw='Marinaro',profession_raw='bovaro')
    save_capture(saved,people,db_path,complete=True)
    assert 'contadino' not in values('profession',db_path)
    assert values('profession',db_path)['bovaro']==1
    assert values('given_name',db_path)['Gio.']==1
    assert values('given_name',db_path)['Giuseppe']==1
    assert values('surname',db_path)['Catalano']==1
    assert values('surname',db_path)['Marinaro']==1


def test_uncertainty_and_placeholders_not_in_vocab(db_path):
    make_register(db_path); draft=make_act(1)
    ppl=selected_participants(draft)
    mother=next(p for p in ppl if p['role']=='mother')
    mother.update(surname_raw='Ba(r)ile',given_name_raw='[Maria]',profession_raw='x')
    sindaco=next(p for p in ppl if p['role']=='sindaco')
    sindaco.update(surname_raw='(Stremer)bo',profession_raw=' q ')
    save_capture(draft['nas'],ppl,db_path,complete=True)
    assert 'Ba(r)ile' not in values('surname',db_path)
    assert '(Stremer)bo' not in values('surname',db_path)
    assert '[Maria]' not in values('given_name',db_path)
    assert 'x' not in values('profession',db_path)
    assert 'q' not in values('profession',db_path)
    assert eligible_vocabulary_value('Gio.')


def test_different_historical_spellings_remain_distinct(db_path):
    make_register(db_path);draft=make_act(1)
    ppl=selected_participants(draft)
    child=next(p for p in ppl if p['role']=='child')
    child['given_name_raw']='Gio.'
    child['given_name_title_raw']='Giovanni'
    save_capture(draft['nas'],ppl,db_path,complete=True)
    names=values('given_name',db_path)
    assert 'Gio.' in names and 'Giovanni' in names


def test_excel_import_rebuilds_lists(db_path,tmp_path):
    make_register(db_path);draft=make_act(1)
    save_capture(draft['nas'],selected_participants(draft),db_path,complete=True)
    excel=export_excel(db_path)
    dest=tmp_path/'restored.sqlite'
    init_db(dest)
    assert import_excel(excel,dest)==(1,1,6)
    assert values('profession',dest)==values('profession',db_path)
    assert export_rows(dest)[2]==export_rows(db_path)[2]


def test_migration_v14_to_v15_preserves_data_and_makes_backup(tmp_path):
    path=tmp_path/'ctc.sqlite'
    copyfile(Path(__file__).parent/'fixtures'/'ctc_v14_synthetic.sqlite',path)
    with sqlite3.connect(path) as con:
        assert con.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='vocabulary_entries'").fetchone()[0]==0
        original=con.execute('SELECT COUNT(*) FROM participants').fetchone()[0]
    init_db(path)
    assert (tmp_path/'ctc.pre_v1_5.sqlite').exists()
    with connect(path) as con:
        assert con.execute('SELECT COUNT(*) FROM participants').fetchone()[0]==original
        assert con.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert con.execute('PRAGMA foreign_key_check').fetchall()==[]
    assert values('surname',path)['Barile']==3  # child + two witnesses
    assert values('profession',path)['contadino']==1
    init_db(path)
    assert values('surname',path)['Barile']==3


def test_reject_unknown_vocabulary_kind(db_path):
    with pytest.raises(ValueError):
        list_vocabulary('unknown',db_path)
    assert list_vocabulary('surname',db_path,limit=0)==[]

"""Regression: displayed historical formula must be a real stored default."""
from io import BytesIO
from capture_defaults import prepare_new_capture
from database import create_register, init_db, load_capture, save_capture
from excel_io import export_excel, parse_workbook
from models import rehydrate_capture, selected_participants

EXPECTED = "sua moglie seco lui convivente"


def test_new_act_formula_is_a_persisted_value_even_when_not_edited(tmp_path):
    db = tmp_path / "ctc.sqlite"
    init_db(db)
    create_register(dict(register_id="REG1875", comune="Girifalco",
                         register_type="NAS", year="1875"), db)
    draft = prepare_new_capture("REG1875", comune="Girifalco", register_year="1875")
    nas = draft["nas"]
    assert nas["mother_relationship_to_declarant_raw"] == EXPECTED
    nas["act_number_raw"] = "12"
    act_id = save_capture(nas, selected_participants(draft), db)
    stored, persons = load_capture(act_id, db)
    assert stored["mother_relationship_to_declarant_raw"] == EXPECTED
    registers, acts, participants = parse_workbook(export_excel(db))
    assert acts[0]["mother_relationship_to_declarant_raw"] == EXPECTED


def test_user_override_and_explicit_empty_remain_untouched(tmp_path):
    db=tmp_path/"ctc.sqlite"
    init_db(db)
    create_register(dict(register_id="REG1875", comune="Girifalco",
                         register_type="NAS", year="1875"), db)
    draft=prepare_new_capture("REG1875", comune="Girifalco")
    draft["nas"]["act_number_raw"]="13"
    draft["nas"]["mother_relationship_to_declarant_raw"]="sua moglie filatrice seco lui convivente"
    act_id=save_capture(draft["nas"],selected_participants(draft),db)
    previous,people=load_capture(act_id,db)
    assert previous["mother_relationship_to_declarant_raw"]=="sua moglie filatrice seco lui convivente"
    previous["mother_relationship_to_declarant_raw"] = None
    save_capture(previous,people,db)
    loaded,people=load_capture(act_id,db)
    assert loaded["mother_relationship_to_declarant_raw"] is None
    reopened=rehydrate_capture(loaded, people)
    assert reopened["nas"]["mother_relationship_to_declarant_raw"] is None

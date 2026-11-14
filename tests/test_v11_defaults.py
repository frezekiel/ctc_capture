"""CtC 1.1 regression tests for provenance-respecting defaults."""
from datetime import datetime

from capture_defaults import prepare_new_capture, PRINTED_WITNESS_RESIDENCE
from database import create_register, latest_sindaco, load_capture, save_capture
from excel_io import export_filename, export_excel, parse_workbook
from models import rehydrate_capture, selected_participants


def _sindaco(d):
    return next(p for p in d["participants"] if p["role"] == "sindaco")


def test_printed_witness_default_and_register_comune():
    d = prepare_new_capture("R1", comune="Girifalco")
    assert d["nas"]["register_id"] == "R1"
    assert d["nas"]["act_comune_raw"] == "Girifalco"
    assert d["nas"]["witness_domicile_collective_raw"] == PRINTED_WITNESS_RESIDENCE
    witnesses = [p for p in d["participants"] if p["role"] == "witness"]
    assert len(witnesses) == 2
    assert all(p["age_unit_raw"] == "anni" for p in witnesses)
    assert all(p["father_name_raw"] is None for p in witnesses)


def test_prefill_sindaco_only_namings_not_linked_identity():
    prior = {
        "participant_id": "NAS1875_001_02", "given_name_raw": "Bonaventura",
        "surname_raw": "Anteletano", "honorific_title_raw": "Don",
        "father_name_raw": "Non kopieren", "age_raw": "60",
    }
    d = prepare_new_capture("R1", comune="Girifalco", previous_sindaco=prior)
    assert all(_sindaco(d)[k] == prior[k] for k in (
        "honorific_title_raw", "given_name_raw", "surname_raw"
    ))
    assert _sindaco(d)["participant_id"] is None
    assert _sindaco(d)["father_name_raw"] is None
    assert _sindaco(d)["age_raw"] is None
    # Source-specific spelling can always be corrected in the next act.
    _sindaco(d)["surname_raw"] = "Antelitano"
    assert prior["surname_raw"] == "Anteletano"


def test_no_global_comune_or_sindaco_default():
    d = prepare_new_capture("R2", comune="Cortale")
    assert d["nas"]["act_comune_raw"] == "Cortale"
    assert _sindaco(d)["given_name_raw"] is None


def test_latest_sindaco_stays_with_register(db_path):
    for reg, comune in (("R1", "Girifalco"), ("R2", "Cortale")):
        create_register(dict(register_id=reg, comune=comune, register_type="NAS", year="1875"), db_path)
    assert latest_sindaco("R1", db_path) is None
    for reg, surname in (("R1", "Prima"), ("R2", "Altro"), ("R1", "Dopo")):
        d = prepare_new_capture(reg)
        # act number increment within the same register
        d["nas"]["act_number_raw"] = "2" if surname == "Dopo" else "1"
        _sindaco(d)["given_name_raw"] = "A"
        _sindaco(d)["surname_raw"] = surname
        save_capture(d["nas"], selected_participants(d), db_path)
    assert latest_sindaco("R1", db_path)["surname_raw"] == "Dopo"
    assert latest_sindaco("R2", db_path)["surname_raw"] == "Altro"


def test_existing_act_is_not_backfilled_with_printed_defaults(db_path):
    create_register(dict(register_id="R1", comune="Girifalco", register_type="NAS", year="1875"), db_path)
    d = prepare_new_capture("R1", comune="Girifalco")
    d["nas"]["act_number_raw"] = "1"
    d["nas"]["witness_domicile_collective_raw"] = None
    d["nas"]["act_comune_raw"] = "in detta Università"
    aid = save_capture(d["nas"], selected_participants(d), db_path)
    nas, people = load_capture(aid, db_path)
    reopened = rehydrate_capture(nas, people)
    assert reopened["nas"]["witness_domicile_collective_raw"] is None
    assert reopened["nas"]["act_comune_raw"] == "in detta Università"


def test_export_file_name_and_excel_preservation(db_path):
    assert export_filename(datetime(2026, 11, 14, 11, 5, 32)) == "ctc_capture_2026-11-14_110532.xlsx"
    create_register(dict(register_id="R1", comune="Girifalco", register_type="NAS", year="1875"), db_path)
    d = prepare_new_capture("R1", comune="Girifalco")
    d["nas"]["act_number_raw"] = "1"
    save_capture(d["nas"], selected_participants(d), db_path)
    registers, acts, participants = parse_workbook(export_excel(db_path))
    assert acts[0]["act_comune_raw"] == "Girifalco"
    assert acts[0]["witness_domicile_collective_raw"] == PRINTED_WITNESS_RESIDENCE
    assert sum(p["role"] == "witness" and p["age_unit_raw"] == "anni" for p in participants) == 2

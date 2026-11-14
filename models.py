"""CtC capture model. RAW strings remain source evidence, not normalized facts."""
from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import uuid4
import re

REGISTER_COLUMNS = ["register_id", "comune", "register_type", "year"]
NAS_COLUMNS = [
    "act_id", "register_id", "act_number_raw", "act_year_raw", "act_month_raw",
    "act_day_raw", "act_time_type_raw", "act_hour_raw", "act_minutes_raw",
    "act_comune_raw", "birth_day_raw", "birth_month_raw", "birth_time_type_raw",
    "birth_hour_raw", "birth_minutes_raw", "birth_address_raw", "birth_address_nr_raw",
    "declarant_is_father", "father_mentioned", "father_explicitly_unknown",
    "legitimate_marriage", "child_status_raw", "title_sidenote_raw",
    "witness_domicile_collective_raw", "mother_relationship_to_declarant_raw",
    "transcriber_name", "transcribed_at_utc", "updated_at_utc",
    "source_legibility_1_5", "transcription_note", "session_note",
    "capture_started_at_utc", "capture_saved_at_utc", "capture_duration_seconds",
]
PARTICIPANT_COLUMNS = [
    "participant_id", "act_id", "role", "sequence_no", "honorific_title_raw",
    "given_name_title_raw", "surname_title_raw", "given_name_raw", "surname_raw",
    "father_marker_raw", "father_name_raw", "age_unit_raw", "age_raw", "sex_raw",
    "profession_raw", "birthplace_raw", "domicile_raw",
]
ROLES = ("child", "sindaco", "declarant", "mother", "father", "witness")
YES_NO_FIELDS = (
    "declarant_is_father", "father_mentioned", "father_explicitly_unknown",
    "legitimate_marriage",
)


def new_participant(role: str, sequence_no: int = 1, *, participant_id: str | None = None) -> dict[str, Any]:
    if role not in ROLES:
        raise ValueError(f"Unbekannte Rolle: {role}")
    p = dict.fromkeys(PARTICIPANT_COLUMNS)
    p.update(participant_id=participant_id, role=role, sequence_no=sequence_no)
    p["_uid"] = uuid4().hex[:12]  # UI only; never written to database.
    if role in {"declarant", "witness"}:
        p["age_unit_raw"] = "anni"  # Printed on the NAS form; editable.
    return p


def new_capture(register_id: str | None) -> dict[str, Any]:
    nas = dict.fromkeys(NAS_COLUMNS)
    nas["register_id"] = register_id
    participants = [new_participant(role) for role in ("child", "sindaco", "declarant", "mother")]
    participants.extend([new_participant("witness", 1), new_participant("witness", 2)])
    return {"nas": nas, "participants": participants, "source_images": [], "capture_status": "draft"}


def rehydrate_capture(nas: dict[str, Any], participants: list[dict[str, Any]],
                      source_images: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    draft = new_capture(nas["register_id"])
    draft["nas"].update({c: nas.get(c) for c in NAS_COLUMNS})
    draft["capture_status"] = nas.get("capture_status", "draft")
    by_role = {(p["role"], int(p["sequence_no"])): p for p in participants}
    incoming: list[dict[str, Any]] = []
    for role in ("child", "sindaco", "declarant", "mother"):
        p = by_role.pop((role, 1), None)
        new = new_participant(role)
        if p:
            new.update({c: p.get(c) for c in PARTICIPANT_COLUMNS})
        incoming.append(new)
    for (role, _seq), p in sorted(by_role.items(), key=lambda x: (x[0][0], x[0][1])):
        new = new_participant(role)
        new.update({c: p.get(c) for c in PARTICIPANT_COLUMNS})
        incoming.append(new)
    # Make sure the witness UI is available even for very old/partial records.
    if not any(p["role"] == "witness" for p in incoming):
        incoming.extend([new_participant("witness", 1), new_participant("witness", 2)])
    draft["participants"] = incoming
    draft["source_images"] = [dict(ref, _uid=uuid4().hex[:12]) for ref in (source_images or [])]
    return draft


def selected_participants(draft: dict[str, Any]) -> list[dict[str, Any]]:
    nas = draft["nas"]
    use_father = nas.get("declarant_is_father") == "no" and nas.get("father_mentioned") == "yes"
    out = []
    for p in draft["participants"]:
        if p["role"] == "father" and not use_father:
            continue
        out.append(deepcopy(p))
    for index, p in enumerate((p for p in out if p["role"] == "witness"), start=1):
        p["sequence_no"] = index
    return out


def new_register_id(year: str, existing: set[str]) -> str:
    year = str(year).strip()
    if not re.fullmatch(r"\d{4}", year):
        raise ValueError("Registerjahr muss vierstellig sein (z. B. 1875).")
    candidate = f"REG{year}"
    if candidate not in existing:
        return candidate
    i = 2
    while f"{candidate}_{i:02d}" in existing:
        i += 1
    return f"{candidate}_{i:02d}"


def make_act_id(register: dict[str, Any], number: str, existing: set[str]) -> str:
    """Readable IDs when possible; avoid collisions across communes/registers."""
    num = str(number).strip()
    if not num:
        raise ValueError("Die Aktnummer fehlt.")
    year = str(register["year"]).strip()
    base_num = f"{int(num):03d}" if num.isdigit() else re.sub(r"[^A-Za-z0-9]+", "_", num).strip("_")
    if not base_num:
        raise ValueError("Ungültige Aktnummer.")
    candidate = f"NAS{year}_{base_num}"
    if candidate not in existing:
        return candidate
    return f"{candidate}_{register['register_id']}"


def assign_participant_ids(act_id: str, records: list[dict[str, Any]], used_ids: set[str]) -> list[dict[str, Any]]:
    """Preserves existing IDs; never renumbers them after removing/reordering a witness."""
    copy_records = deepcopy(records)
    maximum = 0
    for pid in used_ids:
        if pid.startswith(f"{act_id}_"):
            suffix = pid[len(act_id) + 1:]
            if suffix.isdigit():
                maximum = max(maximum, int(suffix))
    for p in copy_records:
        if not p.get("participant_id"):
            maximum += 1
            p["participant_id"] = f"{act_id}_{maximum:02d}"
        p["act_id"] = act_id
        p.pop("_uid", None)
    return copy_records

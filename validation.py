"""Structural validation, separate from interpretation of historical sources."""
from __future__ import annotations
from collections import Counter
from typing import Any

from models import ROLES, YES_NO_FIELDS


def validate_capture(nas: dict[str, Any], participants: list[dict[str, Any]], *, complete: bool = False) -> list[str]:
    problems: list[str] = []
    if not nas.get("register_id"):
        problems.append("Kein Register ausgewählt.")
    if not str(nas.get("act_number_raw") or "").strip():
        problems.append("Aktnummer fehlt.")
    keys: list[tuple[str, int]] = []
    for p in participants:
        role = p.get("role")
        if role not in ROLES:
            problems.append(f"Unbekannte Rolle: {role!r}.")
        try:
            sequence = int(p.get("sequence_no") or 0)
            if sequence < 1:
                raise ValueError()
            keys.append((str(role), sequence))
        except (TypeError, ValueError):
            problems.append(f"Ungültige Positionsnummer für {role}.")
    duplicate = [f"{role} #{i}" for (role, i), count in Counter(keys).items() if count > 1]
    if duplicate:
        problems.append("Doppelte Positionen: " + ", ".join(duplicate))
    for field in YES_NO_FIELDS:
        if nas.get(field) not in (None, "", "yes", "no"):
            problems.append(f"Ungültige Angabe bei {field}: erwartet Ja/Nein/offen.")
    score = nas.get("source_legibility_1_5")
    if score not in (None, "", 1, 2, 3, 4, 5, "1", "2", "3", "4", "5"):
        problems.append("Lesbarkeit muss zwischen 1 und 5 liegen oder leer bleiben.")
    if nas.get("declarant_is_father") == "yes" and nas.get("father_mentioned") == "yes":
        problems.append("Vater ist Declarant, aber zugleich als separat erwähnt markiert: bitte prüfen.")
    if complete:
        present_roles = {p["role"] for p in participants}
        for role in ("child", "sindaco", "declarant", "mother"):
            if role not in present_roles:
                problems.append(f"Position {role} fehlt.")
        for role in ("child", "declarant", "mother"):
            p = next((x for x in participants if x["role"] == role), None)
            if p and not str(p.get("given_name_raw") or "").strip():
                problems.append(f"{role}: Vorname noch nicht bearbeitet.")
    return problems


def foreign_key_report(registers_df: Any, nas_df: Any, participants_df: Any) -> dict[str, Any]:
    """Pandas-only optional diagnostics for exported/current capture tables."""
    unlinked_acts = nas_df.loc[~nas_df["register_id"].isin(registers_df["register_id"])]
    unlinked_participants = participants_df.loc[~participants_df["act_id"].isin(nas_df["act_id"])]
    role_counts = participants_df.groupby(["act_id", "role"]).size().reset_index(name="count")
    return {"invalid_registers": unlinked_acts, "invalid_acts": unlinked_participants, "role_counts": role_counts}


def completion_gaps(nas: dict[str, Any], participants: list[dict[str, Any]]) -> list[str]:
    """Nonblocking review hints for frequently expected NAS information.

    Optional headings, father references, personal residences etc. are never
    counted as gaps. An empty draft is not automatically filled with 'x'.
    """
    items = (
        ('act_year_raw', 'Jahr der Beurkundung'),
        ('act_month_raw', 'Monat der Beurkundung'),
        ('act_day_raw', 'Tag der Beurkundung'),
        ('birth_day_raw', 'Geburtstag'),
        ('birth_month_raw', 'Monatsbezug der Geburt'),
    )
    gaps = [label for key, label in items if not str(nas.get(key) or '').strip()]
    child = next((p for p in participants if p.get('role') == 'child'), None)
    if child and not str(child.get('sex_raw') or '').strip():
        gaps.append('Geschlechtsangabe des Kindes')
    if child and not (str(child.get('given_name_raw') or '').strip()
                      or str(child.get('given_name_title_raw') or '').strip()):
        gaps.append('Name des Kindes')
    return gaps

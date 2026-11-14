"""Editable defaults for a NEW NAS act; stored records are never backfilled.

Raw source text and intra-act resolved context are deliberately distinguished.
"""
from __future__ import annotations
from typing import Any
from uuid import uuid4
from models import new_capture

SINDACO_SUGGESTION_FIELDS = (
    "honorific_title_raw", "given_name_raw", "surname_raw",
)
PRINTED_WITNESS_RESIDENCE = "entrambi residenti in questo comune"
PRINTED_MOTHER_RELATION = "sua moglie seco lui convivente"


def expand_meridian(value: str | None) -> str:
    """Expand only a one-character input; preserve all other source readings."""
    text = str(value or "").strip()
    if text.lower() == "a":
        return "ante"
    if text.lower() == "p":
        return "po"
    return text


def prepare_new_capture(
    register_id: str,
    *,
    comune: str | None = None,
    register_year: str | None = None,
    previous_act_month: str | None = None,
    previous_source_image: dict[str, Any] | None = None,
    previous_sindaco: dict[str, Any] | None = None,
    transcriber_name: str | None = None,
) -> dict[str, Any]:
    """Create a new act with editable, register-local suggestions.

    Avoid calling this when loading a stored act: we must not invent missing
    historical information or silently change a prior transcription.
    """
    draft = new_capture(register_id)
    nas = draft["nas"]
    nas["act_comune_raw"] = comune or None
    nas["act_year_raw"] = register_year or None
    nas["act_month_raw"] = previous_act_month or None
    nas["transcriber_name"] = transcriber_name or None
    nas["witness_domicile_collective_raw"] = PRINTED_WITNESS_RESIDENCE
    # Real editable source-template default, NOT a placeholder in the widget.
    # Only apply to newly opened acts; never overwrite historical stored blanks.
    nas["mother_relationship_to_declarant_raw"] = PRINTED_MOTHER_RELATION
    if previous_sindaco:
        sindaco = next(p for p in draft["participants"] if p["role"] == "sindaco")
        for field in SINDACO_SUGGESTION_FIELDS:
            sindaco[field] = previous_sindaco.get(field)
    if previous_source_image:
        draft["source_images"] = [{
            "image_number_raw": previous_source_image.get("image_number_raw") or "",
            "image_total_raw": previous_source_image.get("image_total_raw") or "",
            "familysearch_url": previous_source_image.get("familysearch_url") or "",
            "_uid": uuid4().hex[:12],
        }]
    return draft

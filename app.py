"""CtC Capture: manual NAS capture interface.

Run in this directory with: python -m streamlit run app.py
No OCR/AI, normalization, record linkage, or integrated scan viewer.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any

import pandas as pd
import streamlit as st

from database import (
    DB_DEFAULT, create_register, init_db, list_registers, list_acts,
    load_capture, save_capture, export_rows, latest_sindaco, last_transcriber,
    load_source_images, list_transcription_events, last_created_act_defaults,
)
from models import new_capture, new_participant, new_register_id, rehydrate_capture, selected_participants
from excel_io import import_excel, export_excel, export_filename
from capture_defaults import prepare_new_capture, expand_meridian
from validation import validate_capture, foreign_key_report, completion_gaps
from vocabulary import FIELD_TO_KIND, VOCAB_KINDS, list_vocabulary, vocabulary_counts
from autocomplete import autocomplete_field, scroll_to_new_act

st.set_page_config(page_title="CtC Capture · Quellenerschliessung", page_icon="📜", layout="wide")
st.markdown('''
<style>
    .block-container { max-width: 1240px; padding-top: 1.35rem; }
    .stTextInput label, .stSelectbox label, .stRadio label {font-size: .91rem;}
    div[data-testid="stVerticalBlockBorderWrapper"] {border-color: rgba(120,140,160,.24);}
    h3 {padding-top: .4rem;}
</style>
''', unsafe_allow_html=True)

init_db()


def init_state() -> None:
    if "draft_rev" not in st.session_state:
        st.session_state["draft_rev"] = 0
    if "draft" not in st.session_state:
        st.session_state["draft"] = new_capture(None)


def replace_draft(draft: dict[str, Any]) -> None:
    # The capture clock begins ONLY when a new form is opened. It stays stable
    # across all Streamlit reruns and is not reset when editing an existing act.
    nas = draft.get('nas', {})
    if not nas.get('act_id') and not nas.get('capture_started_at_utc'):
        nas['capture_started_at_utc'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
    st.session_state["draft_rev"] += 1  # fresh widget keys, no stale values on reopening
    st.session_state["draft"] = draft


def next_capture(register_id: str, *, just_saved_sindaco: dict[str, Any] | None = None) -> dict[str, Any]:
    """Editable defaults apply to new acts, not to existing stored transcriptions."""
    register = next((r for r in list_registers() if r["register_id"] == register_id), None)
    if register is None:
        return new_capture(register_id)
    preceding = just_saved_sindaco if just_saved_sindaco is not None else latest_sindaco(register_id)
    prior_act = last_created_act_defaults(register_id)
    return prepare_new_capture(
        register_id, comune=register["comune"], register_year=register["year"],
        previous_act_month=prior_act["act_month_raw"],
        previous_source_image=prior_act["source_image"],
        previous_sindaco=preceding, transcriber_name=last_transcriber(),
    )


def _expand_meridian_in_widget(key: str) -> None:
    # Streamlit executes on_change before rerendering. Tab triggers the blur.
    st.session_state[key] = expand_meridian(st.session_state.get(key))


def text_field(label: str, column: str, data: dict[str, Any], scope: str, *,
               help_text: str | None = None, placeholder: str = "",
               meridian: bool = False) -> None:
    key = f"rev{st.session_state['draft_rev']}_{scope}_{column}"
    initial = data.get(column)
    if column in FIELD_TO_KIND and scope.startswith('p_'):
        category = FIELD_TO_KIND[column]
        data[column] = autocomplete_field(
            label, initial, key, st.session_state.get('vocab_options', {}).get(category, []),
        )
    else:
        data[column] = st.text_input(
            label, value="" if initial is None else str(initial), key=key,
            help=help_text, placeholder=placeholder,
            on_change=_expand_meridian_in_widget if meridian else None,
            args=(key,) if meridian else None,
        )


def context_domicile(p: dict[str, Any], act_comune: str | None) -> None:
    """Show an editable locality suggestion but don't mislabel it as raw text.

    Only an explicit override is put in domicile_raw. An unchanged contextual
    suggestion is resolved by participant_domicile_resolved, not copied to raw.
    """
    suggestion = str(act_comune or "")
    existing_raw = str(p.get("domicile_raw") or "")
    key = f"rev{st.session_state['draft_rev']}_p_{p['_uid']}_domicile_context"
    default_key = key + "_last_default"
    former_default = st.session_state.get(default_key)
    if not existing_raw and former_default is not None and former_default != suggestion:
        if st.session_state.get(key, "") == former_default:
            st.session_state[key] = suggestion
    st.session_state[default_key] = suggestion
    entered = st.text_input(
        "Wohnort (Vorschlag aus Gemeinde im Akt)",
        value=existing_raw or suggestion, key=key,
        help="Vorgeschlagene Gemeinde ist eine aufgelöste Ortszuordnung. "
             "Nur individuelle Abweichungen werden in domicile_raw gespeichert.",
    )
    # Preserve any explicitly transcribed existing value unchanged.
    if existing_raw and entered == existing_raw:
        p["domicile_raw"] = existing_raw
    elif entered.strip() == suggestion.strip():
        p["domicile_raw"] = None
    else:
        p["domicile_raw"] = entered.strip() or None


def text_row(data: dict[str, Any], scope: str, labels: list[tuple[str, str]],
             ratios: list[float] | None = None) -> None:
    columns = st.columns(ratios if ratios else len(labels), gap="small")
    for col, (field, label) in zip(columns, labels):
        with col:
            text_field(label, field, data, scope)


def yesno(label: str, column: str, nas: dict[str, Any], *, help_text: str = "") -> None:
    values = ["", "yes", "no"]
    current = nas.get(column) or ""
    key = f"rev{st.session_state['draft_rev']}_yn_{column}"
    selected = st.radio(
        label, values, index=values.index(current) if current in values else 0,
        horizontal=True, format_func=lambda v: {"": "Noch offen", "yes": "Ja", "no": "Nein"}[v],
        help=help_text or None, key=key,
    )
    nas[column] = selected or None


def p_row(p: dict[str, Any], fields: list[tuple[str, str]], widths: list[float] | None = None) -> None:
    text_row(p, f"p_{p['_uid']}", fields, widths)


def person_name(p: dict[str, Any]) -> None:
    p_row(p, [("honorific_title_raw", "Ehrentitel (raw)"),
              ("given_name_raw", "Vorname (raw)"), ("surname_raw", "Nachname (raw)")], [1,2,2])


def person_father_ref(p: dict[str, Any]) -> None:
    p_row(p, [("father_marker_raw", "di / fu (raw)"),
              ("father_name_raw", "Name des genannten Vaters (raw)")], [1,3])


def person_more(p: dict[str, Any], *, age: bool = False, occupation: bool = False,
                domicile: bool = False) -> None:
    if age:
        p_row(p, [("age_unit_raw", "Alterseinheit (raw)"), ("age_raw", "Alter (raw)")], [1,2])
    if occupation and domicile:
        p_row(p, [("profession_raw", "Beruf (raw)"), ("domicile_raw", "Wohnort (raw)")], [2,2])
    elif occupation:
        p_row(p, [("profession_raw", "Beruf (raw)")])
    elif domicile:
        p_row(p, [("domicile_raw", "Wohnort (raw)")])


def participant(draft: dict[str, Any], role: str, sequence: int = 1) -> dict[str, Any]:
    for p in draft["participants"]:
        if p["role"] == role and int(p["sequence_no"]) == sequence:
            return p
    p = new_participant(role, sequence)
    draft["participants"].append(p)
    return p


def add_witness() -> None:
    draft = st.session_state["draft"]
    witnesses = [p for p in draft["participants"] if p["role"] == "witness"]
    draft["participants"].append(new_participant("witness", len(witnesses) + 1))


def remove_witness(uid: str) -> None:
    draft = st.session_state["draft"]
    draft["participants"] = [p for p in draft["participants"] if p["_uid"] != uid]
    number = 0
    for p in draft["participants"]:
        if p["role"] == "witness":
            number += 1
            p["sequence_no"] = number


def add_source_image() -> None:
    st.session_state['draft']['source_images'].append(dict(
        image_number_raw='', image_total_raw='', familysearch_url='', _uid=uuid4().hex[:12],
    ))


def remove_source_image(uid: str) -> None:
    draft = st.session_state['draft']
    draft['source_images'] = [r for r in draft['source_images'] if r['_uid'] != uid]


def create_register_sidebar() -> None:
    with st.sidebar.expander("Neues Register anlegen"):
        with st.form("register_form", clear_on_submit=True):
            comune = st.text_input("Comune", placeholder="Girifalco")
            year = st.text_input("Jahr", placeholder="1875")
            typ = st.selectbox("Registertyp", ["NAS"], index=0)
            clicked = st.form_submit_button("Register erstellen", use_container_width=True)
        if clicked:
            try:
                existing = {r["register_id"] for r in list_registers()}
                register_id = new_register_id(year, existing)
                create_register(dict(register_id=register_id, comune=comune.strip(), year=year.strip(), register_type=typ))
                replace_draft(next_capture(register_id))
                st.session_state["flash"] = f"Register {register_id} angelegt."
                st.rerun()
            except (ValueError, sqlite3.IntegrityError) as exc:
                st.error(str(exc))


def side_panel() -> list[dict[str, Any]]:
    st.sidebar.title("CtC Capture")
    st.sidebar.caption("From Code to Code · NAS Capture · v1.5.1")
    create_register_sidebar()
    registers = list_registers()
    if not registers:
        st.sidebar.info("Bitte zuerst ein Register anlegen oder Excel importieren.")
    else:
        by_id = {r["register_id"]: r for r in registers}
        ids = list(by_id)
        st.sidebar.selectbox("Aktives Register für neue Akte", ids,
                             format_func=lambda rid: f"{rid} · {by_id[rid]['comune']} · {by_id[rid]['year']}",
                             key="active_register_id")
        if st.sidebar.button("Neuer NAS-Akt", use_container_width=True):
            replace_draft(next_capture(st.session_state["active_register_id"]))
            st.rerun()
    acts = list_acts()
    if acts:
        st.sidebar.divider()
        act_by_id = {a['act_id']: a for a in acts}
        st.sidebar.selectbox("Gespeicherten Akt auswählen", list(act_by_id),
                             format_func=lambda aid: f"{aid} · {act_by_id[aid]['child_name'] or 'ohne Titelname'}",
                             key="open_act_id")
        if st.sidebar.button("Ausgewählten Akt öffnen", use_container_width=True):
            nas, people = load_capture(st.session_state["open_act_id"])
            replace_draft(rehydrate_capture(nas, people, load_source_images(nas['act_id'])))
            st.rerun()
    st.sidebar.divider()
    with st.sidebar.expander("Excel · Import / Export"):
        st.caption("Importiert eine Excel-Arbeitsmappe in SQLite oder erstellt eine Excel-Kopie der gespeicherten Daten. Die laufende Erfassung wird direkt in SQLite gespeichert.")
        upload = st.file_uploader("CtC-Arbeitsmappe (.xlsx)", type=["xlsx"], key="excel_upload")
        if st.button("Excel importieren", disabled=upload is None, use_container_width=True):
            try:
                counts = import_excel(upload.getvalue())
                st.session_state["flash"] = f"Import: {counts[0]} Register · {counts[1]} Akte · {counts[2]} Positionen"
                replace_draft(next_capture(list_registers()[0]["register_id"]))
                st.rerun()
            except (ValueError, sqlite3.Error, KeyError) as exc:
                st.error(f"Import fehlgeschlagen (keine Teilübernahme): {exc}")
        if st.button("Excel-Kopie vorbereiten", use_container_width=True):
            st.session_state["excel_export_bytes"] = export_excel()
            st.session_state["excel_export_filename"] = export_filename()
        if st.session_state.get("excel_export_bytes"):
            st.download_button("Excel-Kopie herunterladen", data=st.session_state["excel_export_bytes"],
                               file_name=st.session_state.get("excel_export_filename", "ctc_capture.xlsx"),
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               use_container_width=True)
    with st.sidebar.expander("Wörterbücher (Vorschläge)"):
        counts = vocabulary_counts(DB_DEFAULT)
        st.caption("Automatisch aus vollständig gespeicherten Akten. "
                   "Historische Rohschreibweisen bleiben getrennt; Vorschläge werden nie ungefragt übernommen.")
        titles = {"given_name": "Vornamen", "surname": "Nachnamen", "profession": "Berufe"}
        for kind, title in titles.items():
            st.write(f"{title}: **{counts[kind]}** Einträge")
        st.caption("Tippen → ↑/↓ wählen → Tab übernehmen und weiter. "
                   "Tab ohne Pfeiltaste übernimmt die eigene Eingabe.")
        if any(counts.values()):
            selected_kind = st.selectbox(
                "Wörterbuch ansehen", list(titles), format_func=lambda k: titles[k],
                key="vocabulary_inspect_kind",
            )
            rows = list_vocabulary(selected_kind, DB_DEFAULT)
            st.dataframe(pd.DataFrame(rows).rename(columns={
                "value_raw": "Quellenwortlaut", "occurrence_count": "Vorkommen",
            }), hide_index=True, height=190, use_container_width=True)
    with st.sidebar.expander("Datenkontrolle (Pandas)"):
        if st.button("Verbindungen prüfen", use_container_width=True):
            rows = export_rows()
            regs = pd.DataFrame(rows[0], columns=["register_id"])
            nas = pd.DataFrame(rows[1], columns=["act_id", "register_id"])
            ppl = pd.DataFrame(rows[2], columns=["act_id", "role"])
            report = foreign_key_report(regs, nas, ppl)
            st.write(f"Akte mit ungültigem Register: {len(report['invalid_registers'])}")
            st.write(f"Personenpositionen mit ungültigem Akt: {len(report['invalid_acts'])}")
            st.dataframe(report["role_counts"], hide_index=True)
    return registers


def display_capture() -> None:
    draft = st.session_state["draft"]
    nas = draft["nas"]
    participants = draft["participants"]
    st.title("Atto di Nascita", anchor=False)
    registers = list_registers()
    by_id = {r["register_id"]: r for r in registers}
    current = nas.get("register_id")
    if not current or current not in by_id:
        if registers:
            replace_draft(next_capture(st.session_state.get("active_register_id") or registers[0]["register_id"]))
            st.rerun()
        st.info("Links ein Register anlegen oder die vorhandene Excel-Datei importieren.")
        return
    reg = by_id[current]
    st.caption(f"**{reg['comune']}** · {reg['year']} · {current} · "+
               (f"Bearbeiten: {nas['act_id']}" if nas.get("act_id") else "Neuer Akt"))
    st.caption("Quellenwortlaut bewahren (`Gennajo`, `Ba(r)ile`). Optionale Felder dürfen leer bleiben; "
               "bei Entwürfen kann leer auch 'noch nicht geprüft' bedeuten. "
               "`a`/`p` wird in den Zeitfeldern zu `ante`/`po` ergänzt.")

    child = participant(draft, "child")
    sindaco = participant(draft, "sindaco")
    declarant = participant(draft, "declarant")
    mother = participant(draft, "mother")

    st.subheader("1 · Titel und Aktennummer", anchor=False)
    text_row(nas, "nas", [("act_number_raw", "Numero (raw)"),
                         ("title_sidenote_raw", "Randnotiz / Seitenvermerk (raw)")], [1, 3])
    p_row(child, [("honorific_title_raw", "Ehrentitel im Titel"),
                  ("given_name_title_raw", "Vorname im Titel"),
                  ("surname_title_raw", "Nachname im Titel")], [1, 2, 2])

    st.subheader("2 · Beurkundung", anchor=False)
    text_row(nas, "nas", [("act_year_raw", "Jahr (raw)"), ("act_day_raw", "Tag (raw)"),
                         ("act_month_raw", "Monat (raw)")], [1, 1, 2])
    time_cols = st.columns(3, gap="small")
    with time_cols[0]:
        text_field("ante / po (a / p genügt)", "act_time_type_raw", nas, "nas", meridian=True)
    with time_cols[1]:
        text_field("Stunde (raw)", "act_hour_raw", nas, "nas")
    with time_cols[2]:
        text_field("Minuten (raw)", "act_minutes_raw", nas, "nas")

    st.subheader("3 · Sindaco / Uffiziale", anchor=False)
    person_name(sindaco)
    with st.expander("Weitere Sindaco-Angaben", expanded=False):
        person_father_ref(sindaco)
        person_more(sindaco, age=True, occupation=True, domicile=True)
    # Historical text: Avanti di me [Sindaco], Uffiziale dello stato civile
    # del Comune di [comune], e comparso [declarant] ...
    text_field("Comune im Akt (raw)", "act_comune_raw", nas, "nas")

    st.subheader("4 · Dichiarante", anchor=False)
    person_name(declarant)
    if not declarant.get("age_unit_raw"):
        declarant["age_unit_raw"] = "anni"  # Printed in this NAS form.
    d_cols = st.columns(3, gap="small")
    with d_cols[0]:
        text_field("Alter (anni; raw)", "age_raw", declarant, f"p_{declarant['_uid']}")
    with d_cols[1]:
        text_field("Beruf (raw)", "profession_raw", declarant, f"p_{declarant['_uid']}")
    with d_cols[2]:
        context_domicile(declarant, nas.get("act_comune_raw"))
    with st.expander("Weitere Angaben zum Dichiarante (di/fu, Vater, Alterseinheit)", expanded=False):
        person_father_ref(declarant)
        p_row(declarant, [("age_unit_raw", "Alterseinheit (raw; Vordruck: anni)")])

    st.subheader("5 · Geburt", anchor=False)
    # Source order: alle ore ... e minuti ..., del di ... del ... mese.
    birth_time_cols = st.columns(3, gap="small")
    with birth_time_cols[0]:
        text_field("ante / po (a / p genügt)", "birth_time_type_raw", nas, "nas", meridian=True)
    with birth_time_cols[1]:
        text_field("Stunde (raw)", "birth_hour_raw", nas, "nas")
    with birth_time_cols[2]:
        text_field("Minuten (raw)", "birth_minutes_raw", nas, "nas")
    text_row(nas, "nas", [("birth_day_raw", "Geburtstag (raw)"),
                         ("birth_month_raw", "Monatsbezug (raw; corrente / passato …)")], [1, 2])
    text_row(nas, "nas", [("birth_address_raw", "Strasse / Geburtsadresse (raw)"),
                         ("birth_address_nr_raw", "Hausnummer (raw)")], [3, 1])

    st.subheader("6 · Mutter und familiäre Angaben", anchor=False)
    person_name(mother)
    with st.expander("Weitere Angaben zur Mutter", expanded=False):
        person_father_ref(mother)
        person_more(mother, age=True, occupation=True, domicile=True)
        p_row(mother, [("birthplace_raw", "Geburtsort (raw)")])
    text_field("Beziehung zum Declarant (Wortlaut)", "mother_relationship_to_declarant_raw", nas, "nas",
               help_text="Editierbarer Vorschlag aus der Druckvorlage. Bei Abweichung ändern oder löschen.")
    yesno("Ist der Declarant der Vater (quellenbasierte Zuordnung)?", "declarant_is_father", nas,
          help_text="Keine automatische Identitätsverknüpfung zu anderen Akten.")
    if nas.get("declarant_is_father") == "no":
        yesno("Ist der Vater separat genannt?", "father_mentioned", nas)
        if nas.get("father_mentioned") == "yes":
            father = participant(draft, "father")
            st.markdown("**Separat erwähnter Vater**")
            person_name(father)
            person_father_ref(father)
            p_row(father, [("age_raw", "Alter (raw)"), ("profession_raw", "Beruf (raw)")], [1,2])
            context_domicile(father, nas.get("act_comune_raw"))
            with st.expander("Weitere Vater-Angaben", expanded=False):
                p_row(father, [("age_unit_raw", "Alterseinheit (raw)")])
        elif nas.get("father_mentioned") == "no":
            yesno("Vater ausdrücklich unbekannt?", "father_explicitly_unknown", nas)
    yesno("Ehelicher Kontext im Akt belegt?", "legitimate_marriage", nas,
          help_text="Nur aus tatsächlich belegter Quellenangabe; keine automatische Statusableitung.")
    text_field("Statusformulierung des Kindes (raw)", "child_status_raw", nas, "nas")

    st.subheader("7 · Kind im Haupttext", anchor=False)
    p_row(child, [("sex_raw", "Geschlechtsangabe (raw)"),
                  ("given_name_raw", "Vorname im Haupttext"),
                  ("surname_raw", "Nachname im Haupttext (nur wenn genannt)")], [1, 2, 2])
    with st.expander("Weitere Kind-Angaben (falls ausdrücklich vorhanden)"):
        person_father_ref(child)
        person_more(child, age=True, occupation=True, domicile=True)
        p_row(child, [("birthplace_raw", "Geburtsort (raw)")])

    st.subheader("8 · Testimoni", anchor=False)
    witnesses = [p for p in participants if p["role"] == "witness"]
    for i, w in enumerate(witnesses, start=1):
        w["sequence_no"] = i
        with st.container(border=True):
            head, remove_col = st.columns([5,1])
            head.markdown(f"**Zeuge {i}**")
            if remove_col.button("Entfernen", key=f"remove_{st.session_state['draft_rev']}_{w['_uid']}",
                                 help=f"Zeuge {i} entfernen"):
                remove_witness(w["_uid"])
                st.rerun()
            person_name(w)
            # "di anni" is preprinted in the relevant NAS template.
            # Preserve the field in the model, but don't require a tab stop.
            if not w.get("age_unit_raw"):
                w["age_unit_raw"] = "anni"
            p_row(w, [("age_raw", "Alter (anni; Wortlaut raw)"),
                      ("profession_raw", "Beruf (raw)")], [1, 1])
            # The collective printed witness domicile remains act-level raw text.
            # Individual deviations are editable inside the optional expander.
            with st.expander("Weitere Zeugenangaben (di/fu, Vatername, Wohnort)", expanded=False):
                person_father_ref(w)
                source_clause = str(nas.get("witness_domicile_collective_raw") or "").lower()
                original_term = str(w.get("domicile_raw") or "").strip().lower()
                reference_exists = ("in questo comune" in source_clause or original_term == "in questo comune")
                derived = (nas.get("act_comune_raw") or "") if reference_exists else ""
                # Show the resolved comune as an EDITABLE default without silently
                # saving an inferred name as a literal source transcription.
                existing_explicit = w.get("domicile_raw")
                legacy_reference = original_term in ("x", "in questo comune") and bool(derived)
                shown_value = derived if legacy_reference or existing_explicit is None else existing_explicit
                widget_key = f"rev{st.session_state['draft_rev']}_w_{w['_uid']}_domicile_override"
                edited = st.text_input(
                    "Wohnort (aus gemeinsamer Angabe, bei Abweichung überschreibbar)",
                    value=str(shown_value or ""),
                    key=widget_key,
                    help="Standard aus 'in questo comune' → Comune im Akt. "
                         "Nur eine individuelle Abweichung wird als domicile_raw gespeichert.",
                )
                if edited == str(derived) and (existing_explicit is None or legacy_reference):
                    # Keep any legacy literal ("x" / "in questo comune") as it was.
                    w["domicile_raw"] = existing_explicit
                else:
                    w["domicile_raw"] = edited or None
                st.caption("Quelle der Vorbelegung: Akten-Gemeinde, nicht ein zweites Rohtranskript.")
    st.button("+ Zeugen hinzufügen", on_click=add_witness, use_container_width=False)
    text_field("Gemeinsamer Wohnort-Hinweis der Zeugen (raw)",
               "witness_domicile_collective_raw", nas, "nas",
               placeholder="entrambi residenti in questo comune")
    if len(witnesses) != 2 and nas.get("witness_domicile_collective_raw") == "entrambi residenti in questo comune":
        st.warning("Die vorbelegte Druckformel 'entrambi' bezieht sich auf zwei Zeugen. Bitte den Wortlaut für diesen Akt prüfen.")

    st.divider()
    st.subheader("9 · Quellenreferenz (FamilySearch)", anchor=False)
    st.caption("Nur URL und Position im Bildviewer (keine Bilddateien). "
               "Eine Aufnahme kann mehrere Akte zeigen; ein Akt kann mehrere Aufnahmen benötigen.")
    if not draft["source_images"]:
        draft["source_images"].append(dict(
            image_number_raw="", image_total_raw="", familysearch_url="", _uid=uuid4().hex[:12]))
    first = draft["source_images"][0]
    text_field("URL der Aufnahme", "familysearch_url", first, f"src_{first['_uid']}",
               placeholder="https://www.familysearch.org/ark:/...")
    text_row(first, f"src_{first['_uid']}", [
        ("image_number_raw", "Aufnahme Nr."),
        ("image_total_raw", "Aufnahmen insgesamt"),
    ], [1, 1])
    if len(draft["source_images"]) > 1:
        with st.expander(f"Weitere Aufnahmen ({len(draft['source_images'])-1})", expanded=False):
            for i, ref in enumerate(draft["source_images"][1:], start=2):
                st.markdown(f"**Weitere Aufnahme {i}**")
                text_field("URL der Aufnahme", "familysearch_url", ref, f"src_{ref['_uid']}")
                text_row(ref, f"src_{ref['_uid']}", [
                    ("image_number_raw", "Aufnahme Nr."),
                    ("image_total_raw", "Aufnahmen insgesamt")], [1, 1])
                if st.button("Diese zusätzliche Aufnahme entfernen",
                             key=f"src_remove_{st.session_state['draft_rev']}_{ref['_uid']}"):
                    remove_source_image(ref["_uid"])
                    st.rerun()
    if st.button("+ Weitere Aufnahme (nur falls Akt über mehrere Bilder geht)"):
        add_source_image()
        st.rerun()

    st.divider()
    st.subheader("10 · Transkriptionsmetadaten und Quellenkritik", anchor=False)
    col_author, col_readability = st.columns([2, 1])
    with col_author:
        text_field("Transkribiert von", "transcriber_name", nas, "nas",
                   help_text="Wird bei neuen Akten aus der letzten gespeicherten Transkription vorgeschlagen.")
    with col_readability:
        choices = ["", "1", "2", "3", "4", "5"]
        current_score = str(nas.get("source_legibility_1_5") or "")
        nas["source_legibility_1_5"] = st.selectbox(
            "Lesbarkeit der Handschrift (1–5)", choices,
            index=choices.index(current_score) if current_score in choices else 0,
            format_func=lambda v: v or "Noch nicht bewertet",
            key=f"rev{st.session_state['draft_rev']}_nas_source_legibility_1_5",
        ) or None
    st.caption("Skala: 1 = sehr gut lesbar · 2 = gut · 3 = mittel · 4 = schwierig · 5 = sehr schwierig / weitgehend unleserlich. "
               "Bewertung dieses Akts, nicht automatisch des ganzen Registers.")
    for field, label, note in (
        ("transcription_note", "Quellenkritische Bemerkungen / editorische Notiz",
         "Beispiel: Schreibversehen, versetzter Eintrag, ungewöhnliche Formulierung. Quelle und Interpretation unterscheiden."),
        ("session_note", "Sitzungsnotiz (optional)",
         "Hinweise zum Erfassungsvorgang; nicht mit dem historischen Quellenwortlaut verwechseln."),
    ):
        key = f"rev{st.session_state['draft_rev']}_nas_{field}"
        nas[field] = st.text_area(label, value=str(nas.get(field) or ""),
                                  key=key, help=note, height=100)
    st.caption("Erste Speicherung in CtC (UTC): " + str(nas.get("transcribed_at_utc") or "für diesen Akt unbekannt")
               + " · Letzte Speicherung (UTC): " + str(nas.get("updated_at_utc") or "noch nicht protokolliert")
               + ". Alte Akte erhalten rückwirkend keine erfundenen Erfassungszeiten.")
    st.markdown("**Zeitmessung der Erfassung (Version 1.4)**")
    if not nas.get('act_id'):
        started = nas.get('capture_started_at_utc')
        st.caption(f"Erfassungsbeginn (UTC): {started or 'noch nicht gestartet'} · "
                   "Zeit bis zur ersten vollständigen Speicherung. Recherche und Pausen zählen mit.")
    else:
        duration = nas.get('capture_duration_seconds')
        display_duration = (f"{int(duration)//60} Min. {int(duration)%60} Sek."
                            if duration is not None else 'nicht gemessen')
        st.caption(f"Erfassungsbeginn (UTC): {nas.get('capture_started_at_utc') or 'unbekannt'} · "
                   f"Erster Abschluss (UTC): {nas.get('capture_saved_at_utc') or 'noch offen / Altbestand'} · "
                   f"Dauer: {display_duration}")
    st.caption("Die Messung ist verstrichene Zeit (Wall-Clock), keine reine Tippzeit. "
               "Entwürfe haben zunächst keine Abschlussdauer. Alte Akte erhalten keine geschätzte Messung.")
    if nas.get('act_id'):
        with st.expander("Bearbeitungsprotokoll (gespeicherte Versionen)", expanded=False):
            history = list_transcription_events(nas['act_id'])
            if history:
                st.dataframe(history, hide_index=True, use_container_width=True)
            else:
                st.caption("Noch keine Speicherereignisse protokolliert (Altbestand).")

    st.divider()
    st.subheader("In SQLite speichern", anchor=False)
    preview = selected_participants(draft)
    errors = validate_capture(nas, preview, complete=False)
    for err in errors:
        st.warning(err)
    st.caption("Ein Speichervorgang schreibt den Akt und sämtliche Personenpositionen gemeinsam in SQLite. "
               "Optionale Felder dürfen leer bleiben; als Entwurf gespeicherte Akte dürfen unvollständig sein.")
    gaps = completion_gaps(nas, preview)
    if gaps:
        with st.expander(f"Prüfhilfe: {len(gaps)} noch leere erwartete Angaben", expanded=False):
            st.caption("Hinweise, keine automatische Ergänzung mit 'x'. "
                       "Die Druckvorlage kann berechtigte Ausnahmen enthalten.")
            for gap in gaps:
                st.write("• " + gap)
    col1, col2, col3 = st.columns(3)
    clicked_draft = col1.button("Entwurf speichern", use_container_width=True, type="secondary")
    clicked_complete = col2.button("Als vollständig speichern", use_container_width=True)
    clicked_next = col3.button("Speichern & nächster Akt", use_container_width=True, type="primary")
    if clicked_draft or clicked_complete or clicked_next:
        try:
            complete = clicked_complete or clicked_next
            # A one-letter meridian is normalized even if the last field has not blurred.
            for col in ("act_time_type_raw", "birth_time_type_raw"):
                nas[col] = expand_meridian(nas.get(col)) or None
            active_sources = [ref for ref in draft.get("source_images", [])
                              if any(str(ref.get(k) or "").strip()
                                     for k in ("image_number_raw", "image_total_raw", "familysearch_url"))]
            act_id = save_capture(nas, preview, complete=complete,
                                  source_images=active_sources)
            saved_nas, saved_people = load_capture(act_id)
            if clicked_next:
                saved_sindaco = next((p for p in saved_people if p["role"] == "sindaco"), None)
                next_act = next_capture(saved_nas['register_id'], just_saved_sindaco=saved_sindaco)
                # Save & Next follows the just-read act, even when it was older.
                next_act['nas']['act_month_raw'] = saved_nas.get('act_month_raw')
                refs = load_source_images(act_id)
                if refs:
                    latest = refs[-1]
                    next_act['source_images'] = [dict(
                        image_number_raw=latest.get('image_number_raw') or '',
                        image_total_raw=latest.get('image_total_raw') or '',
                        familysearch_url=latest.get('familysearch_url') or '',
                        _uid=uuid4().hex[:12],
                    )]
                last_no = str(saved_nas.get('act_number_raw') or '')
                if last_no.isdigit():
                    next_act['nas']['act_number_raw'] = str(int(last_no) + 1)
                replace_draft(next_act)
                st.session_state['scroll_to_new_act'] = True
                st.session_state["flash"] = f"{act_id} gespeichert; nächster Akt vorbereitet."
            else:
                replace_draft(rehydrate_capture(saved_nas, saved_people,
                                                load_source_images(act_id)))
                st.session_state["flash"] = f"{act_id} gespeichert ({'vollständig' if complete else 'Entwurf'})."
            st.rerun()
        except (ValueError, sqlite3.Error) as exc:
            st.error(f"Nicht gespeichert: {exc}")


init_state()
# Three growing suggestion lists, materialized in SQLite and indexed by raw form.
st.session_state['vocab_options'] = {
    kind: list_vocabulary(kind, DB_DEFAULT) for kind in VOCAB_KINDS
}
side_panel()
if st.session_state.get("flash"):
    st.success(st.session_state.pop("flash"))
display_capture()
if st.session_state.pop('scroll_to_new_act', False):
    scroll_to_new_act(st.session_state['draft_rev'])

"""Excel import/export of source-facing CtC capture data, without normalization."""
from __future__ import annotations
from io import BytesIO
from datetime import datetime
from pathlib import Path
from typing import Any
import pandas as pd

from models import NAS_COLUMNS, PARTICIPANT_COLUMNS, REGISTER_COLUMNS, ROLES, YES_NO_FIELDS
from database import (export_rows, import_rows, export_image_rows,
                      export_transcription_events, DB_DEFAULT, connect)

SHEETS = ("Registers", "NAS", "Participants")


def _decode_value(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    result = str(value)
    return result if result != "" else None


def _from_frame(frame: pd.DataFrame, fields: list[str], *, kind: str) -> list[dict[str, Any]]:
    result = []
    for index, raw in frame.iterrows():
        if all(_decode_value(raw.get(c)) is None for c in fields):
            continue
        row = {col: _decode_value(raw.get(col)) for col in fields}
        if kind == 'NAS':
            # Backwards compatibility with the researcher's original worksheet.
            if not row.get('father_mentioned') and 'father_separately_mentioned' in frame:
                row['father_mentioned'] = _decode_value(raw.get('father_separately_mentioned'))
            for c in YES_NO_FIELDS:
                if row.get(c):
                    converted = {'ja':'yes','nein':'no','true':'yes','false':'no'}
                    row[c] = converted.get(row[c].strip().lower(), row[c].strip().lower())
            status = _decode_value(raw.get('capture_status'))
            row['capture_status'] = status if status in ('draft', 'complete') else 'draft'
        elif kind == 'Participants':
            seq = row.get('sequence_no')
            try:
                row['sequence_no'] = int(float(seq))
            except (ValueError, TypeError):
                raise ValueError(f'Participants, Excel-Zeile {index+2}: Positionsnummer fehlt/ist ungültig.')
            if row['role'] not in ROLES:
                raise ValueError(f'Participants, Excel-Zeile {index+2}: unbekannte Rolle {row["role"]!r}')
        result.append(row)
    return result


def parse_workbook(file: str | Path | BytesIO | bytes) -> tuple[list[dict], list[dict], list[dict]]:
    if isinstance(file, bytes):
        file = BytesIO(file)
    frames = pd.read_excel(
        file, sheet_name=None, dtype=str, keep_default_na=False,
        engine='openpyxl',
    )
    missing = [sheet for sheet in SHEETS if sheet not in frames]
    if missing:
        raise ValueError('Fehlende Excel-Blätter: ' + ', '.join(missing))
    requirements = {
        'Registers': ('register_id', 'comune', 'register_type', 'year'),
        'NAS': ('act_id', 'register_id', 'act_number_raw'),
        'Participants': ('participant_id', 'act_id', 'role', 'sequence_no'),
    }
    for sheet, required in requirements.items():
        missing_cols = [c for c in required if c not in frames[sheet].columns]
        if missing_cols:
            raise ValueError(f'Fehlende Spalten in {sheet}: {", ".join(missing_cols)}')
    return (
        _from_frame(frames['Registers'], REGISTER_COLUMNS, kind='Registers'),
        _from_frame(frames['NAS'], NAS_COLUMNS, kind='NAS'),
        _from_frame(frames['Participants'], PARTICIPANT_COLUMNS, kind='Participants'),
    )


def import_excel(file: str | Path | BytesIO | bytes, path: str | Path = DB_DEFAULT) -> tuple[int, int, int]:
    # Read/validate all sheets before starting the atomic SQLite transaction.
    r, n, p = parse_workbook(file)
    if isinstance(file, bytes):
        file = BytesIO(file)
    elif hasattr(file, 'seek'):
        file.seek(0)
    frames = pd.read_excel(file, sheet_name=None, dtype=str,
                           keep_default_na=False, engine='openpyxl')
    present = set(frames).intersection({'SourceImages','ActImages'})
    if present and present != {'SourceImages','ActImages'}:
        raise ValueError('SourceImages und ActImages müssen beide vorhanden sein.')
    images = links = None
    if present:
        image_cols = ['image_id','register_id','image_number_raw','image_total_raw','familysearch_url']
        link_cols = ['act_id','image_id','sequence_no']
        for name, columns in (('SourceImages',image_cols),('ActImages',link_cols)):
            missing = [c for c in columns if c not in frames[name].columns]
            if missing:
                raise ValueError(f'Fehlende Spalten in {name}: {", ".join(missing)}')
        images = _from_frame(frames['SourceImages'], image_cols, kind='SourceImages')
        links = _from_frame(frames['ActImages'], link_cols, kind='ActImages')
        # Do not accidentally feed a half-formed image reference into SQLite.
        for i, row in enumerate(images, 2):
            if not row.get('image_id') or not row.get('register_id'):
                raise ValueError(f'SourceImages, Excel-Zeile {i}: ID oder Register fehlt.')
        for i, row in enumerate(links, 2):
            if not all(row.get(c) for c in link_cols):
                raise ValueError(f'ActImages, Excel-Zeile {i}: Referenz unvollständig.')
    events = None
    if 'TranscriptionEvents' in frames:
        event_cols = ['event_uid','act_id','recorded_at_utc',
                      'actor_name','event_type','capture_status']
        missing = [c for c in event_cols if c not in frames['TranscriptionEvents'].columns]
        if missing:
            raise ValueError(f'Fehlende Spalten in TranscriptionEvents: {", ".join(missing)}')
        events = _from_frame(frames['TranscriptionEvents'], event_cols, kind='TranscriptionEvents')
        for i, ev in enumerate(events,2):
            if not all(ev.get(c) for c in ('event_uid','act_id','recorded_at_utc',
                                          'event_type','capture_status')):
                raise ValueError(f'TranscriptionEvents, Excel-Zeile {i}: Ereignis unvollständig.')
    # 1.3 human-facing export: scan details live directly in NAS.
    flat_fields = ('source_url', 'image_number', 'image_total')
    has_flat = all(c in frames['NAS'].columns for c in flat_fields)
    if any(c in frames['NAS'].columns for c in flat_fields) and not has_flat:
        raise ValueError('NAS: Die drei Quellenfelder source_url, image_number, image_total gehören zusammen.')
    if has_flat and present:
        raise ValueError('Legacy-Bildblätter und flache NAS-Quellenfelder dürfen nicht gemeinsam importiert werden.')
    if 'AdditionalImages' in frames and not has_flat:
        raise ValueError('AdditionalImages erfordert die drei Quellenfelder im NAS-Blatt.')
    source_refs = None
    if has_flat:
        source_refs = {}
        for _index, raw in frames['NAS'].iterrows():
            act_id = _decode_value(raw.get('act_id'))
            if not act_id:
                continue
            vals = {name: _decode_value(raw.get(name)) for name in flat_fields}
            if any(vals.values()):
                source_refs[act_id] = [dict(
                    familysearch_url=vals['source_url'] or '',
                    image_number_raw=vals['image_number'] or '',
                    image_total_raw=vals['image_total'] or '',
                )]
            else:
                source_refs[act_id] = []
        if 'AdditionalImages' in frames:
            extras = frames['AdditionalImages']
            required = ('act_id', 'sequence_no', *flat_fields)
            missing = [c for c in required if c not in extras.columns]
            if missing:
                raise ValueError('AdditionalImages: Fehlende Spalten: ' + ', '.join(missing))
            pending: dict[str, dict[int, dict[str, str]]] = {}
            for index, row in extras.iterrows():
                act_id = _decode_value(row.get('act_id'))
                seq_value = _decode_value(row.get('sequence_no'))
                if not act_id and not seq_value:
                    continue
                if act_id not in source_refs or not source_refs[act_id]:
                    raise ValueError(f'AdditionalImages, Zeile {index+2}: primäre Aufnahme fehlt.')
                try:
                    seq = int(seq_value or '0')
                except ValueError:
                    raise ValueError(f'AdditionalImages, Zeile {index+2}: ungültige Positionsnummer.')
                if seq < 2 or seq in pending.setdefault(act_id, {}):
                    raise ValueError(f'AdditionalImages, Zeile {index+2}: doppelte/ungültige Reihenfolge.')
                vals = {name: _decode_value(row.get(name)) for name in flat_fields}
                if not vals['source_url'] and not vals['image_number']:
                    raise ValueError(f'AdditionalImages, Zeile {index+2}: URL oder Aufnahme fehlt.')
                pending[act_id][seq] = dict(
                    familysearch_url=vals['source_url'] or '',
                    image_number_raw=vals['image_number'] or '',
                    image_total_raw=vals['image_total'] or '',
                )
            for act_id, numbered in pending.items():
                if sorted(numbered) != list(range(2, len(numbered)+2)):
                    raise ValueError(f'AdditionalImages: Positionsnummern bei {act_id} nicht fortlaufend.')
                source_refs[act_id].extend(numbered[k] for k in sorted(numbered))
    return import_rows(r, n, p, path, images=images, image_links=links,
                       transcription_events=events, source_refs=source_refs)


def _source_display_rows(nas: list[dict], images: list[dict], links: list[dict]):
    """Human-readable first image per act, plus optional extra-image rows."""
    by_id = {int(img['image_id']): img for img in images}
    grouped: dict[str, list[dict]] = {}
    for link in sorted(links, key=lambda l: (l['act_id'], int(l['sequence_no']))):
        img = by_id[int(link['image_id'])]
        grouped.setdefault(link['act_id'], []).append({
            'act_id': link['act_id'], 'sequence_no': int(link['sequence_no']),
            'source_url': img['familysearch_url'],
            'image_number': img['image_number_raw'],
            'image_total': img['image_total_raw'],
        })
    enriched = []
    extras = []
    for act in nas:
        row = dict(act)
        refs = grouped.get(act['act_id'], [])
        first = refs[0] if refs else {}
        row.update({key: first.get(key) for key in ('source_url','image_number','image_total')})
        enriched.append(row)
        extras.extend(refs[1:])
    return enriched, extras


def _participant_display_rows(people: list[dict], path: str | Path):
    """Expose resolved town and its basis WITHOUT modifying domicile_raw."""
    with connect(path) as con:
        resolved = {r['participant_id']: dict(r) for r in con.execute('''
            SELECT participant_id, domicile_resolved, resolution_basis
            FROM witness_domicile_resolved
            UNION ALL
            SELECT participant_id, domicile_resolved, resolution_basis
            FROM participant_domicile_resolved
        ''')}
    out = []
    for p in people:
        r = dict(p)
        match = resolved.get(p['participant_id'], {})
        r['domicile_resolved'] = match.get('domicile_resolved')
        r['domicile_resolution_basis'] = match.get('resolution_basis')
        out.append(r)
    return out


def export_excel(path: str | Path = DB_DEFAULT) -> bytes:
    registers, nas, participants = export_rows(path)
    images, image_links = export_image_rows(path)
    events = export_transcription_events(path)
    nas_display, extra_images = _source_display_rows(nas, images, image_links)
    ppl_display = _participant_display_rows(participants, path)
    output = BytesIO()
    sheet_contents = [
        ('Registers', registers, REGISTER_COLUMNS),
        ('NAS', nas_display, NAS_COLUMNS + ['capture_status',
                                           'source_url','image_number','image_total']),
        ('Participants', ppl_display, PARTICIPANT_COLUMNS + [
            'domicile_resolved','domicile_resolution_basis']),
        ('TranscriptionEvents', events, ['event_uid','act_id','recorded_at_utc',
                                        'actor_name','event_type','capture_status']),
    ]
    if extra_images:
        sheet_contents.append(('AdditionalImages', extra_images,
                               ['act_id','sequence_no','source_url','image_number','image_total']))
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        for sheet, rows, columns in sheet_contents:
            frame = pd.DataFrame(rows).reindex(columns=columns)
            frame.to_excel(writer, sheet_name=sheet, index=False)
            ws = writer.sheets[sheet]
            ws.freeze_panes = 'C2' if sheet != 'Registers' else 'A2'
            ws.auto_filter.ref = ws.dimensions
            from openpyxl.styles import Font, PatternFill
            for cell in ws[1]:
                cell.fill = PatternFill('solid', fgColor='1D3557')
                cell.font = Font(bold=True, color='FFFFFF')
                ws.column_dimensions[cell.column_letter].width = min(
                    34, max(13, len(str(cell.value or '')) + 2)
                )
    return output.getvalue()


def export_filename(when: datetime | None = None) -> str:
    """Timestamp a prepared workbook once; keep name stable during download."""
    when = when or datetime.now()
    return f"ctc_capture_{when:%Y-%m-%d_%H%M%S}.xlsx"

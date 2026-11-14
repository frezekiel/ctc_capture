"""Keyboard-first CtC autocomplete for Streamlit 1.58+.

This uses the supported Components v2 API (no fragile patching of native
Streamlit widgets). A suggestion is NEVER silently substituted: the user must
select it with an arrow key before Tab can accept it.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

from vocabulary import FIELD_TO_KIND

AUTOCOMPLETE_HTML = '''
<div class="ctc-combo">
  <label class="ctc-label" for="ctc-text"></label>
  <input id="ctc-text" class="ctc-input" type="text" autocomplete="off"
         role="combobox" aria-autocomplete="list" aria-expanded="false" />
  <div class="ctc-suggestions" role="listbox" hidden></div>
</div>
'''

AUTOCOMPLETE_CSS = '''
.ctc-combo { position:relative; width:100%; font:inherit; color:var(--st-text-color); }
.ctc-label { display:block; font-size:.91rem; margin-bottom:.45rem; }
.ctc-input { box-sizing:border-box; width:100%; height:50px; padding:0 .85rem;
  font:inherit; font-size:1rem; color:var(--st-text-color);
  background:var(--st-secondary-background-color); border:1px solid var(--st-border-color);
  border-radius:.55rem; outline:none; }
.ctc-input:focus { border-color:var(--st-primary-color); box-shadow:0 0 0 1px var(--st-primary-color); }
.ctc-suggestions { position:absolute; z-index:1000; top:100%; left:0; right:0;
  background:var(--st-background-color); color:var(--st-text-color);
  border:1px solid var(--st-border-color); border-radius:.5rem;
  box-shadow:0 6px 20px rgba(0,0,0,.16); max-height:240px; overflow-y:auto; }
.ctc-suggestions[hidden] { display:none; }
.ctc-option { padding:.45rem .7rem; cursor:pointer; display:flex; justify-content:space-between; gap:1rem; }
.ctc-option.active, .ctc-option:hover { background:var(--st-secondary-background-color); }
.ctc-count { opacity:.55; font-size:.8rem; }
'''

AUTOCOMPLETE_JS = '''
export default function(component) {
  const {parentElement, data, setStateValue} = component;
  const label = parentElement.querySelector('.ctc-label');
  const input = parentElement.querySelector('.ctc-input');
  const list = parentElement.querySelector('.ctc-suggestions');
  label.textContent = data.label;
  const id = 'ctc_' + String(data.control_id).replace(/[^a-zA-Z0-9_-]/g, '_');
  input.id = id;
  label.htmlFor = id;
  input.setAttribute('aria-label', data.label);
  list.id = id + '_list';
  input.setAttribute('aria-controls', list.id);

  // Preserve a value that is being edited in the browser between reruns.
  // A new capture gets a new component key and therefore a fresh initial value.
  if (document.activeElement !== input && input.value !== (data.value ?? '')) {
    input.value = data.value ?? '';
  }
  const all = Array.isArray(data.options) ? data.options : [];
  let matches = [];
  let active = -1; // NEVER select a suggestion without an explicit arrow/click.

  function close() {
    list.hidden = true;
    list.replaceChildren();
    matches = [];
    active = -1;
    input.setAttribute('aria-expanded', 'false');
    input.removeAttribute('aria-activedescendant');
  }
  function select(index) {
    if (index < 0 || index >= matches.length) return;
    input.value = matches[index].value_raw;
    close();
  }
  function draw() {
    list.replaceChildren();
    matches.forEach((item, index) => {
      const option = document.createElement('div');
      option.className = 'ctc-option' + (index === active ? ' active' : '');
      option.id = id + '_option_' + index;
      option.setAttribute('role','option');
      option.setAttribute('aria-selected', index === active ? 'true' : 'false');
      const name = document.createElement('span');
      name.textContent = item.value_raw;
      const count = document.createElement('span');
      count.className = 'ctc-count';
      count.textContent = String(item.occurrence_count ?? 1) + '×';
      option.append(name, count);
      option.onmousedown = e => e.preventDefault();
      option.onclick = () => { select(index); input.focus(); setStateValue('value', input.value); };
      list.append(option);
    });
    list.hidden = matches.length === 0;
    input.setAttribute('aria-expanded', String(matches.length > 0));
    if (active >= 0) {
      input.setAttribute('aria-activedescendant', id + '_option_' + active);
      list.children[active]?.scrollIntoView({block:'nearest'});
    } else {
      input.removeAttribute('aria-activedescendant');
    }
  }
  function refresh() {
    const query = input.value.trim().toLocaleLowerCase('it');
    active = -1;
    if (!query) { close(); return; }
    const prefix = [];
    const contains = [];
    for (const item of all) {
      const word = String(item.value_raw ?? '');
      const lower = word.toLocaleLowerCase('it');
      if (lower.startsWith(query)) prefix.push(item);
      else if (lower.includes(query)) contains.push(item);
      if (prefix.length >= 12) break;
    }
    matches = prefix.concat(contains).slice(0, 8);
    draw();
  }
  input.onfocus = () => { if (input.value.trim()) refresh(); };
  input.oninput = refresh;
  input.onkeydown = e => {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      if (list.hidden) refresh();
      if (matches.length) {
        e.preventDefault();
        active = e.key === 'ArrowDown'
          ? (active + 1) % matches.length
          : (active - 1 + matches.length) % matches.length;
        draw();
      }
    } else if (e.key === 'Tab') {
      // Do not preventDefault: standard Tab moves directly to the next input.
      if (active >= 0) select(active);
      // onblur below commits the exact chosen (or freely typed) raw value.
    } else if (e.key === 'Enter') {
      if (active >= 0) { e.preventDefault(); select(active); setStateValue('value', input.value); }
    } else if (e.key === 'Escape') {
      close();
    }
  };
  input.onblur = () => {
    setStateValue('value', input.value);
    close();
  };
  return () => { input.oninput = input.onkeydown = input.onblur = input.onfocus = null; };
}
'''


@st.cache_resource
def _component():
    return st.components.v2.component(
        name='ctc_historical_autocomplete',
        html=AUTOCOMPLETE_HTML,
        css=AUTOCOMPLETE_CSS,
        js=AUTOCOMPLETE_JS,
    )


def autocomplete_field(label: str, value: str | None, key: str,
                       options: list[dict[str, Any]]) -> str:
    """Return the typed value, or a consciously arrow-selected suggestion."""
    initial = '' if value is None else str(value)
    remembered = st.session_state.get(key)
    current = remembered.get('value', initial) if isinstance(remembered, dict) else initial
    renderer = _component()
    result = renderer(
        key=key,
        data={'label': label, 'value': current, 'control_id': key, 'options': options},
        default={'value': current},
        on_value_change=lambda: None,
        height=83,
    )
    returned = result.value
    return current if returned is None else returned


SCROLL_HTML = '<div aria-hidden="true" style="height:0;width:0"></div>'
SCROLL_JS = '''
export default function(component) {
  // Called only following a successful Save & Next. Use the new form's DOM.
  const run = () => {
    const heading = [...document.querySelectorAll('h3')]
      .find(h => h.textContent && h.textContent.includes('1 · Titel und Aktennummer'));
    heading?.scrollIntoView({block:'start', behavior:'instant'});
    const input = document.querySelector('input[aria-label="Numero (raw)"]');
    input?.focus({preventScroll:true});
    if (!heading) window.scrollTo({top:0, behavior:'instant'});
  };
  const id = setTimeout(() => requestAnimationFrame(() => requestAnimationFrame(run)), 90);
  return () => clearTimeout(id);
}
'''


@st.cache_resource
def _scroll_component():
    return st.components.v2.component(
        name='ctc_scroll_to_new_act', html=SCROLL_HTML, js=SCROLL_JS,
    )


def scroll_to_new_act(token: int) -> None:
    _scroll_component()(key=f'ctc_scroll_once_{token}', height=0)

# GitHub setup for CtC Capture 1.5.1

- Target repository: `frezekiel/ctc-capture` (separate from `frezekiel/codetocode`).
- Start with a **private** repository while reviewing code and source provenance.
- Do not include any local `data/ctc.sqlite`, SQLite backups, real Excel exports, scans, account credentials, or `.venv` directories.
- Included SQLite fixtures are explicitly synthetic and are only used for regression tests.
- The workbook under `samples/` is a small example dataset used by tests, **not** the user's active 2026 research export.
- Run the tests with `python -m pytest -q`; start with `python -m streamlit run app.py`.
- Software: **CtC Capture**, version **1.5.1**. This is a standalone Streamlit-based research capture tool.
- Changes from versions 1.0–1.5.1 are described in `CHANGELOG.md` and `UPGRADE_*.md`.
- No software license has been selected; add one deliberately before making the repo public.

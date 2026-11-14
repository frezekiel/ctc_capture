from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from database import init_db

@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / 'ctc.sqlite'
    init_db(path)
    return path

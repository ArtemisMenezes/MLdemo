import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session", autouse=True)
def ensure_data():
    """Gera banco e modelo se ainda não existirem (determinístico)."""
    if not (ROOT / "data" / "leads.db").exists():
        subprocess.run([sys.executable, "-m", "backend.generate_data"], cwd=ROOT, check=True)
    if not (ROOT / "data" / "model_metrics.json").exists():
        subprocess.run([sys.executable, "-m", "ml.lookalike"], cwd=ROOT, check=True)

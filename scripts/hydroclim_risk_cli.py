"""Thin entry point for hydroclim_risk.cli, matching this project's
convention (see scripts/00_check_environment.py etc.) of a manual
sys.path insert rather than an editable package install.

Usage:
    python scripts\\hydroclim_risk_cli.py check-env
    python scripts\\hydroclim_risk_cli.py download-data --only population,livestock
    python scripts\\hydroclim_risk_cli.py generate-risk --periods June,JJAS
    python scripts\\hydroclim_risk_cli.py validate --directory outputs/risk
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from hydroclim_risk.cli import app  # noqa: E402

if __name__ == "__main__":
    app()

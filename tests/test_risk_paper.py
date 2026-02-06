from __future__ import annotations

from datetime import date
from pathlib import Path
import sys

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = PROJECT_ROOT / "src"
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from neon_alpha.paper import run_paper_simulation  # noqa: E402
from neon_alpha.risk import RiskLimits, select_targets  # noqa: E402
from neon_alpha.signal_io import SignalRow  # noqa: E402


def test_select_targets_respects_max_positions_and_weight_cap() -> None:
    scores = {"AAPL": 0.9, "MSFT": 0.8, "NVDA": 0.7, "AMZN": 0.6}
    limits = RiskLimits(max_positions=2, min_score=0.65, max_weight_per_symbol=0.4, max_daily_turnover=1.0)

    targets = select_targets(scores, current_holdings=set(), limits=limits)

    assert set(targets.keys()) == {"AAPL", "MSFT"}
    assert all(weight == 0.4 for weight in targets.values())


def test_select_targets_respects_turnover_limit() -> None:
    scores = {"AAPL": 0.1, "MSFT": 0.2, "NVDA": 0.9}
    limits = RiskLimits(max_positions=1, min_score=-1.0, max_weight_per_symbol=1.0, max_daily_turnover=0.0)

    targets = select_targets(scores, current_holdings={"AAPL"}, limits=limits)

    assert set(targets.keys()) == {"AAPL"}


def test_paper_simulation_runs_and_returns_metrics() -> None:
    signal_rows = [
        SignalRow(signal_date=date(2025, 1, 2), symbol="AAPL", score=0.9),
        SignalRow(signal_date=date(2025, 1, 2), symbol="MSFT", score=0.7),
        SignalRow(signal_date=date(2025, 1, 3), symbol="AAPL", score=0.2),
        SignalRow(signal_date=date(2025, 1, 3), symbol="MSFT", score=0.8),
    ]
    prices = pd.DataFrame(
        [
            {"date": "2025-01-02", "symbol": "AAPL", "close": 100.0},
            {"date": "2025-01-02", "symbol": "MSFT", "close": 200.0},
            {"date": "2025-01-03", "symbol": "AAPL", "close": 101.0},
            {"date": "2025-01-03", "symbol": "MSFT", "close": 202.0},
            {"date": "2025-01-06", "symbol": "AAPL", "close": 102.0},
            {"date": "2025-01-06", "symbol": "MSFT", "close": 204.0},
        ]
    )
    limits = RiskLimits(max_positions=1, min_score=-1.0, max_weight_per_symbol=1.0, max_daily_turnover=1.0)

    result = run_paper_simulation(signal_rows, prices, limits)

    assert result.end_equity > 1.0
    assert result.max_drawdown >= 0.0

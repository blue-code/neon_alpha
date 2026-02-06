from __future__ import annotations

from datetime import date
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = PROJECT_ROOT / "src"
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from neon_alpha.signal_io import SignalRow, index_signals_by_day, read_signals, write_signals  # noqa: E402


def test_write_and_read_signals_round_trip(tmp_path: Path) -> None:
    rows = [
        SignalRow(signal_date=date(2025, 1, 2), symbol="AAPL", score=0.92),
        SignalRow(signal_date=date(2025, 1, 2), symbol="MSFT", score=0.77),
    ]
    path = tmp_path / "signals.csv"

    write_signals(path, rows)
    loaded = read_signals(path)

    assert loaded == rows


def test_index_signals_by_day() -> None:
    rows = [
        SignalRow(signal_date=date(2025, 1, 2), symbol="AAPL", score=0.92),
        SignalRow(signal_date=date(2025, 1, 2), symbol="MSFT", score=0.77),
        SignalRow(signal_date=date(2025, 1, 3), symbol="AAPL", score=0.50),
    ]

    indexed = index_signals_by_day(rows)

    assert set(indexed.keys()) == {"2025-01-02", "2025-01-03"}
    assert indexed["2025-01-02"]["AAPL"] == 0.92
    assert indexed["2025-01-03"]["AAPL"] == 0.50

from __future__ import annotations

from collections.abc import Iterable
import csv
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path


DATE_FORMAT: str = "%Y-%m-%d"


@dataclass(frozen=True)
class SignalRow:
    signal_date: date
    symbol: str
    score: float


def parse_signal_date(value: str) -> date:
    return datetime.strptime(value, DATE_FORMAT).date()


def read_signals(path: str | Path) -> list[SignalRow]:
    signal_path: Path = Path(path)
    rows: list[SignalRow] = []

    with signal_path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        required = {"date", "symbol", "score"}
        if reader.fieldnames is None or not required.issubset(set(reader.fieldnames)):
            raise ValueError("Signal CSV must contain columns: date,symbol,score")

        for row in reader:
            rows.append(
                SignalRow(
                    signal_date=parse_signal_date(row["date"]),
                    symbol=row["symbol"].strip().upper(),
                    score=float(row["score"]),
                )
            )

    return rows


def write_signals(path: str | Path, rows: Iterable[SignalRow]) -> None:
    signal_path: Path = Path(path)
    signal_path.parent.mkdir(parents=True, exist_ok=True)

    with signal_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["date", "symbol", "score"])
        for row in rows:
            writer.writerow([row.signal_date.strftime(DATE_FORMAT), row.symbol, f"{row.score:.10f}"])


def index_signals_by_day(rows: Iterable[SignalRow]) -> dict[str, dict[str, float]]:
    by_day: dict[str, dict[str, float]] = {}
    for row in rows:
        day_key: str = row.signal_date.strftime(DATE_FORMAT)
        if day_key not in by_day:
            by_day[day_key] = {}
        by_day[day_key][row.symbol] = row.score
    return by_day

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import csv

import pandas as pd

from .risk import RiskLimits, select_targets
from .signal_io import index_signals_by_day, SignalRow


@dataclass
class PaperResult:
    total_return: float
    cagr: float
    max_drawdown: float
    trades: int
    start_equity: float
    end_equity: float


def load_price_csv(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = {"date", "symbol", "close"}
    if not required.issubset(set(df.columns)):
        raise ValueError("Price CSV must contain columns: date,symbol,close")

    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    df["symbol"] = df["symbol"].str.upper()
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df = df.dropna(subset=["close"])
    return df


def run_paper_simulation(
    signal_rows: list[SignalRow],
    price_df: pd.DataFrame,
    limits: RiskLimits,
) -> PaperResult:
    by_day = index_signals_by_day(signal_rows)
    price_pivot = price_df.pivot(index="date", columns="symbol", values="close").sort_index()
    trading_days = list(price_pivot.index)

    if len(trading_days) < 2:
        raise RuntimeError("Need at least two price dates for paper simulation.")

    equity = 1.0
    peak = equity
    max_drawdown = 0.0
    trades = 0

    current_holdings: set[str] = set()
    daily_returns: list[float] = []

    for index in range(len(trading_days) - 1):
        day = trading_days[index]
        next_day = trading_days[index + 1]

        day_scores = by_day.get(day, {})
        targets = select_targets(day_scores, current_holdings, limits)
        target_symbols = set(targets.keys())

        if target_symbols != current_holdings:
            trades += 1
        current_holdings = target_symbols

        if not targets:
            daily_returns.append(0.0)
            continue

        day_prices = price_pivot.loc[day]
        next_prices = price_pivot.loc[next_day]

        day_return = 0.0
        used_weight = 0.0
        for symbol, weight in targets.items():
            if symbol not in day_prices or symbol not in next_prices:
                continue
            p0 = day_prices[symbol]
            p1 = next_prices[symbol]
            if pd.isna(p0) or pd.isna(p1) or p0 <= 0:
                continue
            asset_return = (p1 / p0) - 1.0
            day_return += weight * asset_return
            used_weight += weight

        # 남는 비중은 현금(수익률 0)으로 처리
        if used_weight < 1.0:
            day_return += 0.0

        equity *= 1.0 + day_return
        peak = max(peak, equity)
        drawdown = (peak - equity) / peak if peak > 0 else 0.0
        max_drawdown = max(max_drawdown, drawdown)
        daily_returns.append(day_return)

    periods = max(len(daily_returns), 1)
    annual_factor = 252 / periods
    cagr = (equity ** annual_factor) - 1.0 if equity > 0 else -1.0

    return PaperResult(
        total_return=equity - 1.0,
        cagr=cagr,
        max_drawdown=max_drawdown,
        trades=trades,
        start_equity=1.0,
        end_equity=equity,
    )


def save_result_csv(path: str | Path, result: PaperResult) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["metric", "value"])
        writer.writerow(["start_equity", f"{result.start_equity:.8f}"])
        writer.writerow(["end_equity", f"{result.end_equity:.8f}"])
        writer.writerow(["total_return", f"{result.total_return:.8f}"])
        writer.writerow(["cagr", f"{result.cagr:.8f}"])
        writer.writerow(["max_drawdown", f"{result.max_drawdown:.8f}"])
        writer.writerow(["trades", str(result.trades)])

# ruff: noqa: F403,F405
from AlgorithmImports import *

import csv
from datetime import datetime
from pathlib import Path


class HybridQlibLeanAlgorithm(QCAlgorithm):
    """
    Qlib-generated daily signals -> LEAN execution bridge.
    Signal CSV format: date,symbol,score
    """

    def initialize(self) -> None:
        self.set_start_date(2024, 1, 1)
        self.set_end_date(2025, 12, 31)
        self.set_cash(100000)

        self.universe = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "SPY"]
        self.symbol_map = {ticker: self.add_equity(ticker, Resolution.DAILY).symbol for ticker in self.universe}

        self.long_count = int(self.get_parameter("long_count") or 3)
        self.max_positions = int(self.get_parameter("max_positions") or self.long_count)
        self.min_score = float(self.get_parameter("min_score") or -1e9)
        self.max_weight_per_symbol = float(self.get_parameter("max_weight_per_symbol") or 0.5)
        self.max_daily_turnover = float(self.get_parameter("max_daily_turnover") or 1.0)
        self.signal_csv = self.get_parameter("signal_csv") or "data/signals.csv"

        self.signal_by_day = self._load_signals(self.signal_csv)
        self.current_holdings: set[str] = set()

        benchmark = self.add_equity("SPY", Resolution.DAILY).symbol
        self.schedule.on(
            self.date_rules.every_day(benchmark),
            self.time_rules.after_market_open(benchmark, 5),
            self.rebalance,
        )

    def rebalance(self) -> None:
        day_key = self.time.strftime("%Y-%m-%d")
        day_scores = self.signal_by_day.get(day_key)
        if not day_scores:
            self.debug(f"[{day_key}] no signal rows")
            return

        filtered = [(symbol, score) for symbol, score in day_scores.items() if score >= self.min_score]
        if not filtered:
            self.debug(f"[{day_key}] all scores filtered by min_score={self.min_score}")
            return

        ranked = sorted(filtered, key=lambda item: item[1], reverse=True)[: self.max_positions]
        selected = {symbol for symbol, _ in ranked}

        if self.current_holdings:
            entries = len(selected - self.current_holdings)
            exits = len(self.current_holdings - selected)
            turnover = (entries + exits) / max(len(self.current_holdings), 1)
            if turnover > self.max_daily_turnover:
                self.debug(
                    f"[{day_key}] turnover {turnover:.4f} > limit {self.max_daily_turnover:.4f}, keep holdings"
                )
                selected = set(self.current_holdings)

        if not selected:
            return

        equal_weight = 1.0 / len(selected)
        target_weight = min(equal_weight, self.max_weight_per_symbol)

        for ticker in list(self.current_holdings):
            if ticker not in selected and ticker in self.symbol_map:
                self.set_holdings(self.symbol_map[ticker], 0)
                self.current_holdings.remove(ticker)

        for ticker in selected:
            symbol = self.symbol_map.get(ticker)
            if symbol is None:
                continue
            self.set_holdings(symbol, target_weight)
            self.current_holdings.add(ticker)

    def _load_signals(self, csv_path: str) -> dict[str, dict[str, float]]:
        path = Path(csv_path)
        if not path.exists():
            self.error(f"Signal CSV not found: {csv_path}")
            return {}

        signal_by_day: dict[str, dict[str, float]] = {}
        with path.open("r", encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file)
            for row in reader:
                day_key = datetime.strptime(row["date"], "%Y-%m-%d").strftime("%Y-%m-%d")
                ticker = row["symbol"].upper()
                score = float(row["score"])

                if day_key not in signal_by_day:
                    signal_by_day[day_key] = {}
                signal_by_day[day_key][ticker] = score

        self.debug(f"Loaded signals: {sum(len(item) for item in signal_by_day.values())} rows")
        return signal_by_day

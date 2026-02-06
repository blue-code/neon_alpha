from __future__ import annotations

from dataclasses import dataclass
from math import inf


@dataclass
class RiskLimits:
    """
    vnpy risk_manager 아이디어를 단순화한 신호 레벨 리스크 한도.
    """

    max_positions: int = 3
    min_score: float = -inf
    max_weight_per_symbol: float = 0.5
    max_daily_turnover: float = 1.0


def _turnover_ratio(current: set[str], target: set[str]) -> float:
    if not current:
        return 1.0 if target else 0.0
    entries = len(target - current)
    exits = len(current - target)
    return (entries + exits) / len(current)


def select_targets(
    day_scores: dict[str, float],
    current_holdings: set[str],
    limits: RiskLimits,
) -> dict[str, float]:
    ranked = sorted(
        ((symbol, score) for symbol, score in day_scores.items() if score >= limits.min_score),
        key=lambda item: item[1],
        reverse=True,
    )

    if not ranked:
        return {}

    selected_symbols = [symbol for symbol, _ in ranked[: limits.max_positions]]
    target_set = set(selected_symbols)

    if limits.max_daily_turnover < inf:
        turnover = _turnover_ratio(current_holdings, target_set)
        if turnover > limits.max_daily_turnover and current_holdings:
            # 한도 초과 시 기존 보유를 유지하고 겹치는 종목만 남긴다.
            overlap = [symbol for symbol in selected_symbols if symbol in current_holdings]
            if overlap:
                selected_symbols = overlap
                target_set = set(overlap)
            else:
                selected_symbols = list(current_holdings)
                target_set = set(selected_symbols)

    if not selected_symbols:
        return {}

    equal_weight = 1.0 / len(selected_symbols)
    capped_weight = min(equal_weight, limits.max_weight_per_symbol)

    return {symbol: capped_weight for symbol in target_set}

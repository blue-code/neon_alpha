from __future__ import annotations

from datetime import date
import pandas as pd

from .signal_io import SignalRow


def load_close_prices(
    provider_uri: str,
    symbols: list[str],
    start: str,
    end: str,
) -> pd.DataFrame:
    try:
        import qlib
        from qlib.constant import REG_US
        from qlib.data import D
    except Exception as error:  # pragma: no cover
        raise RuntimeError(
            "Qlib import failed. Install pyqlib and prepare US data before running this command."
        ) from error

    qlib.init(provider_uri=provider_uri, region=REG_US)

    raw = D.features(
        instruments=symbols,
        fields=["$close"],
        start_time=start,
        end_time=end,
        freq="day",
    )

    if raw.empty:
        raise RuntimeError("No data returned from Qlib. Check provider path, symbols, and date range.")

    normalized = raw.reset_index()
    columns = [str(column).lower() for column in normalized.columns]
    normalized.columns = columns

    symbol_col = "instrument" if "instrument" in columns else "symbol"
    date_col = "datetime"
    close_col = "$close" if "$close" in columns else "close"

    if symbol_col not in normalized or date_col not in normalized or close_col not in normalized:
        raise RuntimeError(f"Unexpected Qlib dataframe columns: {normalized.columns.tolist()}")

    close_df = normalized[[date_col, symbol_col, close_col]].rename(
        columns={date_col: "date", symbol_col: "symbol", close_col: "close"}
    )
    close_df["date"] = pd.to_datetime(close_df["date"]).dt.date
    close_df["symbol"] = close_df["symbol"].str.upper()
    close_df = close_df.sort_values(["symbol", "date"])
    return close_df


def build_signal_rows(close_df: pd.DataFrame) -> list[SignalRow]:
    df = close_df.copy()
    grouped = df.groupby("symbol", group_keys=False)

    momentum_20 = grouped["close"].pct_change(20)
    reversal_5 = grouped["close"].pct_change(5)
    df["score"] = momentum_20 - reversal_5
    df = df.dropna(subset=["score"])

    rows: list[SignalRow] = []
    for item in df.itertuples(index=False):
        rows.append(
            SignalRow(
                signal_date=item.date if isinstance(item.date, date) else pd.to_datetime(item.date).date(),
                symbol=item.symbol,
                score=float(item.score),
            )
        )
    return rows


def generate_signals_with_qlib(
    provider_uri: str,
    symbols: list[str],
    start: str,
    end: str,
) -> list[SignalRow]:
    close_df = load_close_prices(
        provider_uri=provider_uri,
        symbols=[symbol.upper() for symbol in symbols],
        start=start,
        end=end,
    )
    return build_signal_rows(close_df)

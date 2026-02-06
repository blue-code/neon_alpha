from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import threading

from .event_bus import create_event_bus, stop_event_bus
from .generator import generate_signals_with_qlib
from .paper import load_price_csv, run_paper_simulation, save_result_csv
from .risk import RiskLimits
from .signal_io import SignalRow, read_signals, write_signals


DEFAULT_SYMBOLS: list[str] = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "SPY"]
PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
EVENT_SIGNAL_REQUESTED = "eSignalRequested"
EVENT_SIGNAL_GENERATED = "eSignalGenerated"
EVENT_SIGNAL_VALIDATED = "eSignalValidated"
EVENT_PIPELINE_DONE = "ePipelineDone"


def _default_generated_csv() -> str:
    return str(PROJECT_ROOT / "data" / "generated_signals.csv")


def _default_sample_csv() -> str:
    return str(PROJECT_ROOT / "data" / "sample_signals.csv")


def _validate_rows(rows: list[SignalRow]) -> tuple[int, int]:
    duplicate_counter = Counter((row.signal_date, row.symbol) for row in rows)
    duplicate_count = sum(1 for value in duplicate_counter.values() if value > 1)
    return len(rows), duplicate_count


def _build_risk_limits(args: argparse.Namespace) -> RiskLimits:
    return RiskLimits(
        max_positions=args.max_positions,
        min_score=args.min_score,
        max_weight_per_symbol=args.max_weight_per_symbol,
        max_daily_turnover=args.max_daily_turnover,
    )


def _add_risk_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--max-positions", type=int, default=3)
    parser.add_argument("--min-score", type=float, default=-1e9)
    parser.add_argument("--max-weight-per-symbol", type=float, default=0.5)
    parser.add_argument("--max-daily-turnover", type=float, default=1.0)


def command_sample(args: argparse.Namespace) -> None:
    source_path = Path(_default_sample_csv())
    if not source_path.exists():
        raise RuntimeError(f"Sample signal file not found: {source_path}")

    rows = read_signals(source_path)
    write_signals(args.output, rows)
    print(f"[sample] wrote {len(rows)} rows -> {args.output}")


def command_qlib(args: argparse.Namespace) -> None:
    rows = generate_signals_with_qlib(
        provider_uri=args.provider_uri,
        symbols=args.symbols,
        start=args.start,
        end=args.end,
    )
    write_signals(args.output, rows)
    print(f"[qlib] wrote {len(rows)} rows -> {args.output}")


def command_validate(args: argparse.Namespace) -> None:
    rows = read_signals(args.signal_csv)
    row_count, duplicate_count = _validate_rows(rows)
    date_count = len({row.signal_date for row in rows})
    symbol_count = len({row.symbol for row in rows})

    print(f"[validate] file          : {args.signal_csv}")
    print(f"[validate] rows          : {row_count}")
    print(f"[validate] dates         : {date_count}")
    print(f"[validate] symbols       : {symbol_count}")
    print(f"[validate] duplicates    : {duplicate_count}")

    if row_count == 0:
        raise RuntimeError("Signal CSV is empty.")
    if duplicate_count > 0:
        raise RuntimeError("Duplicate (date,symbol) rows detected.")

    print("[validate] OK")


def command_paper(args: argparse.Namespace) -> None:
    rows = read_signals(args.signal_csv)
    price_df = load_price_csv(args.price_csv)
    limits = _build_risk_limits(args)
    result = run_paper_simulation(rows, price_df, limits)

    print(f"[paper] signal_csv      : {args.signal_csv}")
    print(f"[paper] price_csv       : {args.price_csv}")
    print(f"[paper] total_return    : {result.total_return:.6f}")
    print(f"[paper] cagr            : {result.cagr:.6f}")
    print(f"[paper] max_drawdown    : {result.max_drawdown:.6f}")
    print(f"[paper] trades          : {result.trades}")
    print(f"[paper] end_equity      : {result.end_equity:.6f}")

    if args.output:
        save_result_csv(args.output, result)
        print(f"[paper] metrics saved  : {args.output}")


def command_pipeline(args: argparse.Namespace) -> None:
    errors: list[Exception] = []
    done = threading.Event()
    engine, EventClass = create_event_bus()

    def emit(event_type: str, payload: object | None = None) -> None:
        engine.put(EventClass(event_type, payload))

    def safe(handler):
        def wrapped(event):
            try:
                handler(event)
            except Exception as error:
                errors.append(error)
                done.set()
        return wrapped

    @safe
    def on_requested(_event) -> None:
        if args.mode == "sample":
            rows = read_signals(_default_sample_csv())
        else:
            if not args.provider_uri:
                raise RuntimeError("--provider-uri is required when mode=qlib")
            rows = generate_signals_with_qlib(
                provider_uri=args.provider_uri,
                symbols=args.symbols,
                start=args.start,
                end=args.end,
            )
        write_signals(args.signal_csv, rows)
        emit(EVENT_SIGNAL_GENERATED, {"signal_csv": args.signal_csv})

    @safe
    def on_generated(_event) -> None:
        rows = read_signals(args.signal_csv)
        row_count, duplicate_count = _validate_rows(rows)
        if row_count == 0:
            raise RuntimeError("Signal CSV is empty.")
        if duplicate_count > 0:
            raise RuntimeError("Duplicate (date,symbol) rows detected.")
        emit(EVENT_SIGNAL_VALIDATED, {"row_count": row_count})

    @safe
    def on_validated(_event) -> None:
        if args.price_csv:
            rows = read_signals(args.signal_csv)
            price_df = load_price_csv(args.price_csv)
            limits = _build_risk_limits(args)
            result = run_paper_simulation(rows, price_df, limits)
            print(f"[pipeline] paper total_return : {result.total_return:.6f}")
            print(f"[pipeline] paper cagr         : {result.cagr:.6f}")
            print(f"[pipeline] paper max_dd       : {result.max_drawdown:.6f}")
            if args.paper_output:
                save_result_csv(args.paper_output, result)
                print(f"[pipeline] paper metrics saved: {args.paper_output}")
        emit(EVENT_PIPELINE_DONE, {"signal_csv": args.signal_csv})

    @safe
    def on_done(_event) -> None:
        done.set()

    engine.register(EVENT_SIGNAL_REQUESTED, on_requested)
    engine.register(EVENT_SIGNAL_GENERATED, on_generated)
    engine.register(EVENT_SIGNAL_VALIDATED, on_validated)
    engine.register(EVENT_PIPELINE_DONE, on_done)

    try:
        emit(EVENT_SIGNAL_REQUESTED, {"mode": args.mode})
        if not done.wait(timeout=args.timeout_sec):
            raise TimeoutError("Pipeline timed out.")
    finally:
        stop_event_bus(engine)

    if errors:
        raise errors[0]

    print(f"[pipeline] done -> {args.signal_csv}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="NeonAlpha CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sample = sub.add_parser("sample", help="Copy sample signals to output path")
    sample.add_argument("--output", default=_default_generated_csv())
    sample.set_defaults(func=command_sample)

    qlib = sub.add_parser("qlib", help="Generate signals with qlib")
    qlib.add_argument("--provider-uri", required=True)
    qlib.add_argument("--start", default="2022-01-01")
    qlib.add_argument("--end", default="2025-12-31")
    qlib.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS)
    qlib.add_argument("--output", default=_default_generated_csv())
    qlib.set_defaults(func=command_qlib)

    validate = sub.add_parser("validate", help="Validate signal csv")
    validate.add_argument("--signal-csv", default=_default_generated_csv())
    validate.set_defaults(func=command_validate)

    paper = sub.add_parser("paper", help="Run local paper simulation (vnpy paper_account style)")
    paper.add_argument("--signal-csv", default=_default_generated_csv())
    paper.add_argument("--price-csv", required=True, help="CSV columns: date,symbol,close")
    paper.add_argument("--output", default=str(PROJECT_ROOT / "data" / "paper_metrics.csv"))
    _add_risk_args(paper)
    paper.set_defaults(func=command_paper)

    pipeline = sub.add_parser("pipeline", help="Event-driven pipeline (vnpy event style)")
    pipeline.add_argument("--mode", choices=["sample", "qlib"], default="sample")
    pipeline.add_argument("--provider-uri", default="")
    pipeline.add_argument("--start", default="2022-01-01")
    pipeline.add_argument("--end", default="2025-12-31")
    pipeline.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS)
    pipeline.add_argument("--signal-csv", default=_default_generated_csv())
    pipeline.add_argument("--price-csv", default="")
    pipeline.add_argument("--paper-output", default=str(PROJECT_ROOT / "data" / "pipeline_paper_metrics.csv"))
    pipeline.add_argument("--timeout-sec", type=int, default=30)
    _add_risk_args(pipeline)
    pipeline.set_defaults(func=command_pipeline)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Fetch price history via AKShare.

Generic runner script: symbols and window are CLI args, nothing is
hardcoded beyond the pilot defaults.

Pilot defaults:
  - A-share: 600519 (Kweichow Moutai) via ak.stock_zh_a_hist
  - US:      105.AAPL via ak.stock_us_hist (AKShare's US symbol format
             is "<market code>.<ticker>", e.g. 105 = NASDAQ for AAPL)

Each attempt is independent: on success the data is saved as CSV under
the output directory and rows / date range / first & last close are
recorded; on failure the exact exception is recorded. Either way a
summary.json is written and the script exits 0, so partial results
survive in the workflow artifact.
"""
import argparse
import json
import traceback
from datetime import date, timedelta
from pathlib import Path


def find_col(df, candidates, contains=None):
    for c in df.columns:
        if str(c) in candidates:
            return c
    if contains:
        for c in df.columns:
            if contains in str(c):
                return c
    return None


def summarise(df, out_csv):
    df.to_csv(out_csv, index=False)
    date_col = find_col(df, ["date", "Date", "日期"], contains="日期")
    if date_col is None:
        date_col = df.columns[0]
    close_col = find_col(df, ["close", "Close", "收盘"], contains="收盘")
    result = {
        "status": "ok",
        "rows": int(len(df)),
        "columns": [str(c) for c in df.columns],
        "csv": str(out_csv),
    }
    if len(df) > 0:
        result["date_first"] = str(df[date_col].iloc[0])
        result["date_last"] = str(df[date_col].iloc[-1])
        if close_col is not None:
            result["close_col"] = str(close_col)
            result["close_first"] = float(df[close_col].iloc[0])
            result["close_last"] = float(df[close_col].iloc[-1])
    return result


def attempt(fn_name, func, kwargs, out_csv):
    try:
        df = func(**kwargs)
        if df is None or len(df) == 0:
            return {"status": "empty", "function": fn_name,
                    "kwargs": {k: str(v) for k, v in kwargs.items()},
                    "error": "function returned no rows"}
        return {**summarise(df, out_csv), "function": fn_name,
                "kwargs": {k: str(v) for k, v in kwargs.items()}}
    except Exception as e:  # record the exact failure, keep going
        return {"status": "error", "function": fn_name,
                "kwargs": {k: str(v) for k, v in kwargs.items()},
                "error_type": type(e).__name__,
                "error": str(e),
                "traceback": traceback.format_exc()}


def main():
    p = argparse.ArgumentParser(description="Fetch history via AKShare")
    p.add_argument("--a-symbol", default="600519",
                   help="A-share symbol for stock_zh_a_hist (pilot: 600519 Kweichow Moutai)")
    p.add_argument("--us-symbol", default="105.AAPL",
                   help="US symbol for stock_us_hist in AKShare format (pilot: 105.AAPL)")
    p.add_argument("--days", type=int, default=365,
                   help="Look-back window in days (default 365, roughly the last year)")
    p.add_argument("--adjust", default="",
                   help="Adjustment passed to AKShare ('' = none, 'qfq', 'hfq')")
    p.add_argument("--outdir", default="results")
    p.add_argument("--skip-a", action="store_true")
    p.add_argument("--skip-us", action="store_true")
    args = p.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    end = date.today()
    start = end - timedelta(days=args.days)
    start_s, end_s = start.strftime("%Y%m%d"), end.strftime("%Y%m%d")

    summary = {
        "tool": "akshare",
        "window": {"start_date": start_s, "end_date": end_s, "days": args.days},
        "a_share": None,
        "us": None,
    }

    try:
        import akshare as ak
        summary["akshare_version"] = getattr(ak, "__version__", "unknown")
    except Exception as e:
        summary["akshare_version"] = None
        summary["import_error"] = f"{type(e).__name__}: {e}"
        (outdir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0

    if not args.skip_a:
        if hasattr(ak, "stock_zh_a_hist"):
            summary["a_share"] = attempt(
                "stock_zh_a_hist", ak.stock_zh_a_hist,
                {"symbol": args.a_symbol, "period": "daily",
                 "start_date": start_s, "end_date": end_s, "adjust": args.adjust},
                outdir / f"a_share_{args.a_symbol}.csv")
        else:
            summary["a_share"] = {"status": "unsupported",
                                  "error": "ak.stock_zh_a_hist not present in this akshare version"}

    if not args.skip_us:
        if hasattr(ak, "stock_us_hist"):
            summary["us"] = attempt(
                "stock_us_hist", ak.stock_us_hist,
                {"symbol": args.us_symbol, "period": "daily",
                 "start_date": start_s, "end_date": end_s, "adjust": args.adjust},
                outdir / f"us_{args.us_symbol}.csv")
        else:
            summary["us"] = {"status": "unsupported",
                             "error": "ak.stock_us_hist not present in this akshare version"}

    (outdir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

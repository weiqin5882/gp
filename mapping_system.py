#!/usr/bin/env python3
"""跨市场映射系统 1.0（Python 半自动化版）"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple


@dataclass
class TslaRecord:
    date: str
    close: float
    pct_change: float
    daily_volatility: float
    vol_3d: float
    volume: float
    volume_ma20: float
    breakout: bool
    ma5: float

    @property
    def volume_ratio(self) -> float:
        if self.volume_ma20 <= 0:
            return 0.0
        return self.volume / self.volume_ma20


@dataclass
class AShareRecord:
    date: str
    ticker: str
    name: str
    pool: str
    pct_change: float
    volume: float
    volume_ma5: float

    @property
    def volume_ratio(self) -> float:
        if self.volume_ma5 <= 0:
            return 0.0
        return self.volume / self.volume_ma5


def read_tsla_csv(path: Path) -> List[TslaRecord]:
    rows: List[TslaRecord] = []
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(
                TslaRecord(
                    date=row["date"],
                    close=float(row["close"]),
                    pct_change=float(row["pct_change"]),
                    daily_volatility=float(row["daily_volatility"]),
                    vol_3d=float(row["vol_3d"]),
                    volume=float(row["volume"]),
                    volume_ma20=float(row["volume_ma20"]),
                    breakout=row["breakout"].strip().lower() in {"1", "true", "yes", "y"},
                    ma5=float(row["ma5"]),
                )
            )
    return sorted(rows, key=lambda r: r.date)


def read_ashare_csv(path: Path, date: str) -> List[AShareRecord]:
    rows: List[AShareRecord] = []
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["date"] != date:
                continue
            rows.append(
                AShareRecord(
                    date=row["date"],
                    ticker=row["ticker"],
                    name=row.get("name", row["ticker"]),
                    pool=row["pool"],
                    pct_change=float(row["pct_change"]),
                    volume=float(row["volume"]),
                    volume_ma5=float(row["volume_ma5"]),
                )
            )
    return rows


def read_pools(path: Path) -> Dict[str, List[Dict[str, str]]]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def read_event_intensity(path: Path, date: str) -> int:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if date not in data:
        return 0
    value = int(data[date].get("event_intensity", 0))
    return max(0, min(3, value))


def classify_sentiment(tsla_today: TslaRecord, tsla_prev: TslaRecord | None) -> Tuple[str, int, List[str]]:
    notes: List[str] = []
    continuous_up = bool(tsla_prev and tsla_today.pct_change > 0 and tsla_prev.pct_change > 0)
    above_ma5 = tsla_today.close >= tsla_today.ma5

    if tsla_today.pct_change >= 3 and tsla_today.volume_ratio >= 1.3:
        state = "趋势扩张"
        momentum_score = 3
        notes.append("单日涨幅≥3%且放量")
    elif tsla_today.pct_change <= -2 or not above_ma5:
        state = "回撤"
        momentum_score = 0
        notes.append("跌破5日均线或单日跌幅较大")
    else:
        state = "震荡"
        momentum_score = 2
        notes.append("价格区间震荡")

    if continuous_up and state != "回撤":
        momentum_score += 1
        notes.append("连续2日上涨")

    if tsla_today.breakout and state == "趋势扩张":
        notes.append("突破关键区间")

    return state, min(momentum_score, 4), notes


def ashare_confirmation_score(
    records: List[AShareRecord], pools: Dict[str, List[Dict[str, str]]]
) -> Tuple[int, List[AShareRecord], List[str]]:
    allow_tickers = {item["ticker"] for items in pools.values() for item in items}
    pool_records = [r for r in records if r.ticker in allow_tickers]

    confirmed = [r for r in pool_records if r.pct_change >= 2.0 and r.volume_ratio >= 1.2]
    confirmed = sorted(confirmed, key=lambda x: (x.pct_change, x.volume_ratio), reverse=True)

    cnt = len(confirmed)
    if cnt >= 3:
        score = 3
    elif cnt == 2:
        score = 2
    elif cnt == 1:
        score = 1
    else:
        score = 0

    notes = [f"确认标的数: {cnt}"]
    return score, confirmed[:3], notes


def decide_action(total_score: int, state: str) -> str:
    if total_score >= 6 and state != "回撤":
        return "允许参与（T+1仅观察预设池放量确认，T+3/T+5统一平仓）"
    return "不参与（等待源头转强）"


def write_review_log(path: Path, row: Dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with path.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "date",
                "tsla_state",
                "us_momentum_score",
                "event_score",
                "a_confirm_score",
                "total_score",
                "action",
                "selected_a_shares",
            ],
        )
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def compute_result(
    target_date: str,
    tsla_csv: str,
    ashare_csv: str,
    events_json: str,
    pools_json: str,
) -> Dict[str, object]:
    tsla_rows = read_tsla_csv(Path(tsla_csv))
    idx_map = {r.date: i for i, r in enumerate(tsla_rows)}
    if target_date not in idx_map:
        raise ValueError(f"TSLA 数据中不存在日期: {target_date}")

    i = idx_map[target_date]
    tsla_today = tsla_rows[i]
    tsla_prev = tsla_rows[i - 1] if i > 0 else None

    pools = read_pools(Path(pools_json))
    a_records = read_ashare_csv(Path(ashare_csv), target_date)

    state, us_score, state_notes = classify_sentiment(tsla_today, tsla_prev)
    event_score = read_event_intensity(Path(events_json), target_date)
    a_score, picks, a_notes = ashare_confirmation_score(a_records, pools)

    total = us_score + event_score + a_score
    action = decide_action(total, state)

    return {
        "date": target_date,
        "state": state,
        "us_score": us_score,
        "event_score": event_score,
        "a_score": a_score,
        "total": total,
        "action": action,
        "state_notes": state_notes,
        "a_notes": a_notes,
        "picks": picks,
    }


def print_result(result: Dict[str, object]) -> None:
    print("=" * 60)
    print(f"日期: {result['date']}")
    print(f"TSLA 情绪状态: {result['state']}")
    print(
        f"美股动能: {result['us_score']}/4 | 事件强度: {result['event_score']}/3 | A股确认: {result['a_score']}/3"
    )
    print(f"总分: {result['total']}/10")
    print(f"执行建议: {result['action']}")
    print("- 情绪说明:", "；".join(result["state_notes"]))
    print("- A股说明:", "；".join(result["a_notes"]))
    if result["picks"]:
        print("- 重点观察:")
        for p in result["picks"]:
            print(f"  * {p.ticker} {p.name} ({p.pool}) 涨幅{p.pct_change:.2f}% 量比{p.volume_ratio:.2f}")
    print("=" * 60)


def evaluate(args: argparse.Namespace) -> int:
    result = compute_result(
        target_date=args.date,
        tsla_csv=args.tsla_csv,
        ashare_csv=args.ashare_csv,
        events_json=args.events_json,
        pools_json=args.pools_json,
    )
    print_result(result)

    if args.log_csv:
        picks = result["picks"]
        write_review_log(
            Path(args.log_csv),
            {
                "date": str(result["date"]),
                "tsla_state": str(result["state"]),
                "us_momentum_score": str(result["us_score"]),
                "event_score": str(result["event_score"]),
                "a_confirm_score": str(result["a_score"]),
                "total_score": str(result["total"]),
                "action": str(result["action"]),
                "selected_a_shares": ",".join(p.ticker for p in picks),
            },
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="跨市场映射系统 1.0（半自动化）")
    parser.add_argument("--date", required=True, help="评估日期，例如 2026-02-20")
    parser.add_argument("--tsla-csv", default="data/tsla_daily.csv")
    parser.add_argument("--ashare-csv", default="data/ashare_daily.csv")
    parser.add_argument("--events-json", default="data/events.json")
    parser.add_argument("--pools-json", default="config/pools.json")
    parser.add_argument("--log-csv", default="records/review_log.csv")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    datetime.strptime(args.date, "%Y-%m-%d")
    return evaluate(args)


if __name__ == "__main__":
    raise SystemExit(main())

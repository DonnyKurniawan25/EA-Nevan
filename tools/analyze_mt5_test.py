"""Reconcile MT5 tester statistics with owned, fully closed positions and fees."""
import argparse
import csv
from collections import defaultdict
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path


def read_text(path):
    raw = path.read_bytes()
    encoding = "utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else (
        "utf-16-le" if b"\0" in raw[:100] else "utf-8-sig")
    return raw.decode(encoding)


def analyze(native_path, deals_path):
    native = json.loads(read_text(native_path))
    positions = defaultdict(lambda: {"net": Decimal(0), "in": Decimal(0),
                                     "out": Decimal(0), "close": "", "reasons": []})
    max_volume = Decimal(0)
    seen = set()
    for row in csv.DictReader(io.StringIO(read_text(deals_path))):
        if row["deal_ticket"] in seen:
            raise ValueError("Duplicate deal ticket")
        seen.add(row["deal_ticket"])
        entry = int(row["entry"])
        if entry not in (0, 1, 3):
            raise ValueError("Unsupported reversal deal; hedging-only analysis expected")
        p = positions[row["position_id"]]
        volume = Decimal(row["volume"])
        max_volume = max(max_volume, volume)
        p["in" if entry == 0 else "out"] += volume
        p["net"] += sum((Decimal(row[k]) for k in ("profit", "commission", "swap", "fee")), Decimal(0))
        if entry != 0:
            p["close"] = row["time_server"]
            p["reasons"].append(int(row["reason"]))
    closed = []
    incomplete = []
    for pid, p in positions.items():
        if p["in"] <= 0 or abs(p["in"] - p["out"]) > Decimal("0.00000001"):
            incomplete.append(pid)
            continue
        closed.append({"position_id": pid, "closed_server": p["close"],
                       "net": float(p["net"]), "entry_lots": float(p["in"]),
                       "exit_reasons": p["reasons"]})
    closed.sort(key=lambda p: (p["closed_server"], p["position_id"]))
    wins = sum(p["net"] > 0 for p in closed)
    losses = sum(p["net"] < 0 for p in closed)
    net = round(sum(p["net"] for p in closed), 8)
    positive = sum(max(0, p["net"]) for p in closed)
    negative = -sum(min(0, p["net"]) for p in closed)
    checks = {
        "all_positions_fully_closed": not incomplete,
        "trade_count_matches_native": len(closed) == native["trades"],
        "net_profit_matches_native": abs(net - native["net_profit"]) < 0.011,
        "win_count_matches_native": wins == native["wins"],
        "loss_count_matches_native": losses == native["losses"],
        "deal_volume_within_cap": float(max_volume) <= native["base_lot_cap"] + 1e-8,
    }
    return {
        "source": "MT5 real-tick historical simulation, not live fills",
        "execution_mode": native["execution_mode"],
        "symbol": native["symbol"], "timeframe": native["timeframe"],
        "currency": native["currency"], "closed_positions": len(closed),
        "wins_after_all_costs": wins, "losses_after_all_costs": losses,
        "breakeven_after_all_costs": len(closed) - wins - losses,
        "win_rate_after_costs_pct": 100 * wins / len(closed) if closed else None,
        "net_profit_after_all_costs": net,
        "profit_factor_after_costs": positive / negative if negative else None,
        "maximum_equity_drawdown_pct_native": native["equity_drawdown_pct"],
        "maximum_equity_drawdown_money_native": native["equity_drawdown_money"],
        "initial_deposit": native["initial_deposit"],
        "return_pct": 100 * net / native["initial_deposit"],
        "maximum_deal_lots": float(max_volume), "incomplete_position_ids": incomplete,
        "checks": checks, "reconciled": all(checks.values()),
        "positions": closed,
        "evidence_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in (native_path, deals_path)},
        "limitations": [
            "One historical interval; no independent out-of-sample validation or optimization.",
            "Win rate counts profitable closed positions after commission, swap and fees.",
            "Equity floor may stop new trades before the test interval ends.",
            "This measures the RULES baseline; AI/ONNX is not implemented.",
            "Historical simulation does not establish future live accuracy or profitability.",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("native_json", type=Path)
    parser.add_argument("deals_csv", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = analyze(args.native_json, args.deals_csv)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k not in ("positions", "limitations", "evidence_sha256")}, indent=2))
    return 0 if result["reconciled"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

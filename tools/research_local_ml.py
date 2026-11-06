"""Local chronological ML research. This program cannot send MT5 orders."""
import argparse
import csv
from datetime import datetime
import hashlib
import json
from pathlib import Path
import numpy as np

FEATURES = ["return1_atr", "return4_atr", "return16_atr", "ema_gap_atr", "price_fast_atr",
            "fast_slope_atr", "rsi_centered", "body_atr", "range_atr", "log_volume",
            "spread_atr", "h1_gap_atr", "h1_price_fast_atr", "h1_fast_slope_atr"]


def ema(values, alpha):
    out = np.empty(len(values))
    out[0] = values[0]
    for i in range(1, len(values)):
        out[i] = alpha * values[i] + (1 - alpha) * out[i - 1]
    return out


def load(path):
    rows = list(csv.DictReader(path.open(encoding="utf-8-sig")))
    times = np.array([np.datetime64(datetime.strptime(r["time_server"], "%Y.%m.%d %H:%M:%S"), "s") for r in rows])
    if len(times) < 500 or np.any(np.diff(times).astype(int) <= 0):
        raise ValueError("Need ordered, unique, sufficient native closed bars")
    data = {key: np.array([float(r[key]) for r in rows]) for key in rows[0] if key != "time_server"}
    if not all(np.isfinite(a).all() for a in data.values()):
        raise ValueError("Nonfinite market data")
    return times, data


def features(times, d):
    o, h, l, c = (d[k] for k in ("open", "high", "low", "close"))
    prev = np.r_[c[0], c[:-1]]
    tr = np.maximum(h - l, np.maximum(abs(h - prev), abs(l - prev)))
    atr = ema(tr, 1 / 14)
    fast, slow = ema(c, 2 / 21), ema(c, 2 / 51)
    change = c - prev
    gain, loss = ema(np.maximum(change, 0), 1 / 14), ema(np.maximum(-change, 0), 1 / 14)
    rsi = np.divide(gain, gain + loss, out=np.full(len(c), .5), where=(gain + loss) > 0)
    # Only complete historical H1 buckets enter the as-of join.
    hour = times.astype("datetime64[h]")
    ends, closes = [], []
    for bucket in np.unique(hour):
        indexes = np.flatnonzero(hour == bucket)
        expected = bucket.astype("datetime64[s]") + np.arange(4) * np.timedelta64(15, "m")
        if len(indexes) == 4 and np.array_equal(times[indexes], expected):
            ends.append(bucket.astype("datetime64[s]") + np.timedelta64(1, "h"))
            closes.append(c[indexes[-1]])
    ends, closes = np.array(ends), np.array(closes)
    if len(closes) < 50:
        raise ValueError("Insufficient closed H1 context")
    hf, hs = ema(closes, 2 / 21), ema(closes, 2 / 51)
    available = times + np.timedelta64(15, "m")
    indexes = np.searchsorted(ends, available, side="right") - 1
    valid_h1 = indexes >= 1
    safe = np.maximum(indexes, 1)
    valid_h1 &= (available - ends[safe]) < np.timedelta64(2, "h")
    a = np.maximum(atr, 1e-9)
    def move(lag):
        out = np.full(len(c), np.nan)
        out[lag:] = (c[lag:] - c[:-lag]) / a[lag:]
        return out
    spread = np.maximum(d["spread_points"] * d["point"], .24)
    x = np.column_stack([move(1), move(4), move(16), (fast - slow) / a, (c - fast) / a,
                         np.r_[np.nan, np.diff(fast)] / a, rsi * 2 - 1, (c - o) / a,
                         (h - l) / a, np.log1p(d["tick_volume"]), spread / a,
                         (hf[safe] - hs[safe]) / a, (closes[safe] - hf[safe]) / a,
                         (hf[safe] - hf[safe - 1]) / a])
    x[~valid_h1] = np.nan
    x[:250] = np.nan
    return x, atr, available


def outcomes(times, d, atr, side):
    n = len(times)
    pnl, exits = np.full(n, np.nan), np.full(n, -1, dtype=int)
    spread = np.maximum(d["spread_points"] * d["point"], .24)
    for i in range(250, n - 17):
        entry_index = i + 1
        if times[entry_index] - times[i] != np.timedelta64(15, "m"):
            continue
        # Admission cannot depend on whether a future stop/target happens early.
        # Require the WHOLE fixed horizon to fit before midnight and have data.
        horizon = times[entry_index:entry_index + 16]
        if (horizon[-1] + np.timedelta64(15, "m")).astype("datetime64[D]") != horizon[0].astype("datetime64[D]"):
            continue
        if np.any(np.diff(horizon) != np.timedelta64(15, "m")):
            continue
        entry = d["open"][entry_index] + (spread[entry_index] if side == 1 else 0)
        sl = min(entry - 2 * atr[i], d["low"][i] - d["point"][i]) if side == 1 else max(entry + 2 * atr[i], d["high"][i] + d["point"][i])
        tp = entry + side * abs(entry - sl) * 2
        entry_day = times[entry_index].astype("datetime64[D]")
        for j in range(entry_index, entry_index + 16):
            close_time = times[j] + np.timedelta64(15, "m")
            if close_time.astype("datetime64[D]") != entry_day or (j > entry_index and times[j] - times[j - 1] != np.timedelta64(15, "m")):
                break  # No overnight/synthetic gap labels.
            opening = d["open"][j] + (spread[j] if side == -1 else 0)
            stop_hit = d["low"][j] <= sl if side == 1 else d["high"][j] + spread[j] >= sl
            target_hit = d["high"][j] >= tp if side == 1 else d["low"][j] + spread[j] <= tp
            if stop_hit:
                price = min(sl, opening) if side == 1 else max(sl, opening)
            elif target_hit:
                price = tp
            elif j == entry_index + 15:
                price = d["close"][j] + (spread[j] if side == -1 else 0)
            else:
                continue
            # Standard gold min lot: 100 oz/lot * .01 lot = 1 oz.
            # .10 USD is the preset cost buffer, in addition to spread in entry/exit.
            pnl[i] = side * (price - entry) - .10
            exits[i] = j
            break  # Stop first if both levels touch: conservative OHLC assumption.
    return pnl, exits


def sigmoid(z):
    return 1 / (1 + np.exp(-np.clip(z, -35, 35)))


def fit(x, y):
    mean, scale = x.mean(axis=0), x.std(axis=0)
    scale = np.maximum(scale, 1e-8)
    z = np.clip((x - mean) / scale, -8, 8)
    weights, intercept = np.zeros(x.shape[1]), 0.0
    for _ in range(600):
        error = sigmoid(z @ weights + intercept) - y
        weights -= .05 * (z.T @ error / len(y) + .02 * weights)
        intercept -= .05 * error.mean()
    return {"mean": mean.tolist(), "scale": scale.tolist(), "weights": weights.tolist(),
            "intercept": float(intercept), "training_positive_rate": float(y.mean()), "training_samples": len(y)}


def predict(model, x):
    z = np.clip((x - np.array(model["mean"])) / np.array(model["scale"]), -8, 8)
    return sigmoid(z @ np.array(model["weights"]) + model["intercept"])


def evaluate(start, end, x, available, d, outcomes_by_side, models):
    lo, hi = np.datetime64(start), np.datetime64(end)
    common = np.isfinite(x).all(axis=1) & (available >= lo) & (available < hi)
    probabilities, classification = {}, {}
    for side in (1, -1):
        net, exits = outcomes_by_side[side]
        valid = common & np.isfinite(net)
        valid &= available[np.maximum(exits, 0)] < hi  # Purge labels crossing split boundary.
        p = np.full(len(x), np.nan)
        p[valid] = predict(models[side], x[valid])
        probabilities[side] = p
        y = (net[valid] > 0).astype(float)
        brier = float(np.mean((p[valid] - y) ** 2)) if len(y) else None
        constant = float(np.mean((models[side]["training_positive_rate"] - y) ** 2)) if len(y) else None
        classification[str(side)] = {"labeled_samples": len(y), "brier": brier, "constant_train_rate_brier": constant,
                                      "accuracy_pct": float(np.mean((p[valid] >= .5) == y) * 100) if len(y) else None}
    # Non-overlapping hypothetical trades at native minimum lot, max one per day.
    selected, next_index, used_days = [], 0, set()
    for i in range(len(x)):
        day = str(available[i].astype("datetime64[D]"))
        if i < next_index or day in used_days:
            continue
        candidates = [s for s in (1, -1) if np.isfinite(probabilities[s][i]) and probabilities[s][i] >= .60]
        if not candidates:
            continue
        side = max(candidates, key=lambda s: probabilities[s][i])
        net, exits = outcomes_by_side[side]
        selected.append(float(net[i]))
        used_days.add(day)
        next_index = int(exits[i]) + 3  # No overlapping outcomes, plus 30-minute cooldown.
    gains, losses = sum(max(v, 0) for v in selected), -sum(min(v, 0) for v in selected)
    return {"from": start, "to_exclusive": end, "classification": classification,
            "hypothetical_trades": len(selected), "wins": sum(v > 0 for v in selected),
            "net_at_standard_min_lot_usd": round(sum(selected), 4),
            "profit_factor": gains / losses if losses else None,
            "capital_feasible": False, "note": "Research price labels, not MT5 fills or USD10-feasible trades."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("bars_csv", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--capital-report", type=Path, required=True)
    args = parser.parse_args()
    capital = next(csv.DictReader(args.capital_report.open(encoding="utf-8-sig")))
    if capital["symbol"] != "XAUUSDm" or capital["currency"] != "USD" or float(capital["min_lots"]) != .01:
        raise ValueError("This research label model supports verified Standard XAUUSDm/USD only; do not reuse for Cent")
    feasible = (capital["status"] == "PRELIMINARY_ONLY_SL_AND_SIGNAL_STILL_REQUIRED")
    times, d = load(args.bars_csv)
    x, atr, available = features(times, d)
    models, labels = {}, {}
    for side in (1, -1):
        labels[side] = outcomes(times, d, atr, side)
        net, exits = labels[side]
        train = np.isfinite(x).all(axis=1) & np.isfinite(net) & (available >= np.datetime64("2026-09-01"))
        train &= (available < np.datetime64("2026-10-01")) & (available[np.maximum(exits, 0)] < np.datetime64("2026-10-01"))
        if train.sum() < 500:
            raise ValueError("Insufficient purged chronological training examples")
        models[side] = fit(x[train], (net[train] > 0).astype(float))
    validation = evaluate("2026-10-01", "2026-11-01", x, available, d, labels, models)
    test = evaluate("2026-11-01", "2026-11-06", x, available, d, labels, models)
    report = {"status": "RESEARCH_ONLY_NOT_APPROVED", "execution_enabled": False,
              "algorithm": "L2 logistic regression, separate BUY/SELL, local numpy, no external API",
              "feature_names": FEATURES, "data_sha256": hashlib.sha256(args.bars_csv.read_bytes()).hexdigest(),
              "closed_native_bars": len(times), "training": "September 2026; labels purged at boundary",
              "validation": validation, "test": test,
              "broker_capital_assessment": capital,
              "acceptance_gate": {"capital_feasible": feasible,
                  "enough_validation_trades": validation["hypothetical_trades"] >= 100,
                  "enough_test_trades": test["hypothetical_trades"] >= 100,
                  "validation_profit_factor_at_least_1_2": (validation["profit_factor"] or 0) >= 1.2,
                  "test_profit_factor_at_least_1_2": (test["profit_factor"] or 0) >= 1.2},
              "limitations": ["Probabilities are uncalibrated research scores, not reliable live confidence.",
                  "OHLC labels use conservative stop-first ordering and a cost buffer; tick fills/slippage are not reproduced.",
                  "No sample is used simultaneously for training and chronological validation/test.",
                  "Even a good classifier cannot override broker minimum lot, margin or risk limits."]}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "evaluation.json").write_text(json.dumps(report, indent=2) + "\n")
    (args.output_dir / "model_research_only.json").write_text(json.dumps({"execution_enabled": False, "feature_names": FEATURES, "models": models}, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

"""Check causality and boundary behavior, not trading profitability."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np

path = Path(__file__).resolve().parents[1] / "tools/research_local_ml.py"
spec = importlib.util.spec_from_file_location("research_local_ml", path)
ml = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ml)


class LocalResearchTests(unittest.TestCase):
    def sample(self):
        n = 800
        times = np.datetime64("2026-09-01T00:00:00") + np.arange(n) * np.timedelta64(15, "m")
        close = 4000 + np.sin(np.arange(n) / 11) + np.arange(n) * .01
        data = {"open": close - .1, "high": close + 1, "low": close - 1, "close": close,
                "tick_volume": np.full(n, 1000), "spread_points": np.full(n, 240), "point": np.full(n, .001)}
        return times, data

    def test_future_ohlc_cannot_change_past_features(self):
        times, data = self.sample()
        original, _, _ = ml.features(times, data)
        changed = {k: v.copy() for k, v in data.items()}
        for k in ("open", "high", "low", "close"):
            changed[k][603:] += 500
        updated, _, _ = ml.features(times, changed)
        np.testing.assert_allclose(original[:603], updated[:603], equal_nan=True)

    def test_training_normalization_does_not_read_test_rows(self):
        rng = np.random.default_rng(7)
        x = rng.normal(size=(200, 4)); y = (x[:, 0] > 0).astype(float)
        model = ml.fit(x[:100], y[:100])
        np.testing.assert_allclose(model["mean"], x[:100].mean(axis=0))
        np.testing.assert_allclose(model["scale"], x[:100].std(axis=0))

    def test_late_entry_not_selected_by_early_future_exit(self):
        times, data = self.sample()
        _, atr, _ = ml.features(times, data)
        net, _ = ml.outcomes(times, data, atr, 1)
        next_time = times + np.timedelta64(15, "m")
        late = next_time.astype("datetime64[h]").astype(int) % 24 >= 20
        self.assertTrue(np.isnan(net[late]).all())

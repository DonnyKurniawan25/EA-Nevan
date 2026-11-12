import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from tools.telegram_notifier import LABELS, EVENT_ICONS, REASONS, REASON_DESCRIPTIONS, KEY_TRANSLATIONS


class TestFastScalperBasket(unittest.TestCase):
    def test_preset_contains_basket_settings(self):
        preset_path = os.path.join(
            os.path.dirname(__file__), "..", "deployment", "linux-guide", "presets", "EXNESS_CENT_USD10.set"
        )
        with open(preset_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("UseFastScalperBasket=true", content)
        self.assertIn("BasketLayers=5", content)
        self.assertIn("BasketTakeProfitUSC=5.0", content)
        self.assertIn("BasketCutLossUSC=20.0", content)
        self.assertIn("BasketCooldownMinutes=0", content)
        self.assertIn("MaxAccountPositions=5", content)
        self.assertIn("MaxTotalAccountLots=0.05", content)

    def test_notifier_basket_translations(self):
        self.assertIn("BASKET_PROFIT_EXIT", LABELS)
        self.assertIn("BASKET_CUT_LOSS_EXIT", LABELS)
        self.assertIn("BASKET_PROFIT_EXIT", EVENT_ICONS)
        self.assertIn("BASKET_CUT_LOSS_EXIT", EVENT_ICONS)
        self.assertIn("BASKET_TARGET_PROFIT_REACHED", REASON_DESCRIPTIONS)
        self.assertIn("BASKET_EMERGENCY_CUT_LOSS", REASON_DESCRIPTIONS)
        self.assertIn("layers", KEY_TRANSLATIONS)
        self.assertIn("total_pl", KEY_TRANSLATIONS)
        self.assertIn("target", KEY_TRANSLATIONS)
        self.assertIn("cut_loss", KEY_TRANSLATIONS)


if __name__ == "__main__":
    unittest.main()

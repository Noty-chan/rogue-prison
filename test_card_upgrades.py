import unittest

import content
import game


class CardUpgradeDefTest(unittest.TestCase):
    def test_all_cards_have_upgrade_data(self):
        missing = [c["id"] for c in content.CARDS if c.get("desc_up") is None and c.get("cost_up") is None and c.get("effects_up") is None]
        self.assertEqual(missing, [], f"Cards without upgrade data: {missing}")

    def test_get_card_def_applies_upgrade_fields(self):
        base = content.get_card_def("SCAVENGE", upgraded=False)
        upgraded = content.get_card_def("SCAVENGE", upgraded=True)
        self.assertNotEqual(base["cost"], upgraded["cost"])
        self.assertNotEqual(base["effects"], upgraded["effects"])
        self.assertIn("0", upgraded["desc"])

    def test_card_view_uses_upgraded_def(self):
        inst = {"uid": "t", "id": "WARD_OF_MIRRORS", "up": True}
        view = game.card_view(inst)
        upgraded_def = content.get_card_def("WARD_OF_MIRRORS", upgraded=True)
        self.assertEqual(view["cost"], upgraded_def["cost"])
        self.assertEqual(view["desc"], upgraded_def["desc"])

    def test_sanitize_deck_view_shows_upgraded_stats(self):
        state = game.default_state()
        state["run"] = {
            "hp": 30,
            "max_hp": 30,
            "floor": 1,
            "seed": 123,
            "rng_ctr": 0,
            "deck": [game.make_card_instance("GLIMMER_SHIELD", upgraded=True)],
        }
        sanitized = game.sanitize_for_client(state)
        deck_view = sanitized["run"]["deck_view"]
        self.assertEqual(len(deck_view), 1)
        upgraded_def = content.get_card_def("GLIMMER_SHIELD", upgraded=True)
        self.assertEqual(deck_view[0]["desc"], upgraded_def["desc"])
        self.assertEqual(deck_view[0]["cost"], upgraded_def["cost"])


if __name__ == "__main__":
    unittest.main()

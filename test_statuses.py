import unittest
from unittest import mock
import game


def make_base_state():
    combat = {
        "turn": 1,
        "phase": "player",
        "player": {
            "name": "Игрок",
            "hp": 20,
            "max_hp": 20,
            "block": 0,
            "mana_max": 3,
            "mana": 0,
            "statuses": {},
            "buffs": {},
            "crit": game.content.CRIT_BASE_CHANCE,
        },
        "enemies": [
            {
                "name": "Манекен",
                "id": "dummy",
                "hp": 10,
                "max_hp": 10,
                "block": 0,
                "statuses": {},
                "buffs": {},
                "vars": {"phase": "base", "status_bonus": {}},
                "status_immunities": [],
                "tier": 1,
                "moves": [
                    {"id": "wait", "name": "Ждёт", "type": "block", "block": 0, "w": 1}
                ],
                "intent": {"type": "block", "name": "Ждёт", "block": 0},
                "next_move": {"id": "wait", "name": "Ждёт", "type": "block", "block": 0},
            }
        ],
        "draw_pile": [],
        "discard_pile": [],
        "exhaust_pile": [],
        "hand": [],
        "pending": None,
        "log": [],
    }
    return {
        "run": {
            "hp": 20,
            "max_hp": 20,
            "floor": 1,
            "act": 1,
            "seed": 123,
            "rng_ctr": 0,
            "combat": combat,
        },
        "screen": "COMBAT",
        "ui": {},
    }


class FreezeControlRandom(game.random.Random):
    def __init__(self, sequence):
        super().__init__(0)
        self._seq = iter(sequence)

    def random(self):
        return next(self._seq)


class StatusSkipTest(unittest.TestCase):
    def test_player_stun_skips_and_calls_enemy_turn(self):
        state = make_base_state()
        state["run"]["combat"]["player"]["statuses"] = {"stun": 1}

        def record_enemy_turn(s):
            combat = s["run"]["combat"]
            combat["_enemy_calls"] = int(combat.get("_enemy_calls", 0)) + 1

        with mock.patch.object(game, "enemy_turn", side_effect=record_enemy_turn):
            game.start_player_turn(state)

        combat = state["run"]["combat"]
        self.assertEqual(game.status_get(combat["player"], "stun"), 0)
        self.assertEqual(combat.get("_enemy_calls"), 1)
        self.assertIn("оглушён", " ".join(combat.get("log", [])))

    def test_player_freeze_respects_probability_and_skips(self):
        state = make_base_state()
        state["run"]["combat"]["player"]["statuses"] = {"freeze": 1}

        def stub_seeded_rng(run):
            run["rng_ctr"] = int(run.get("rng_ctr", 0)) + 1
            return FreezeControlRandom([0.1, 0.9])

        with mock.patch.object(game, "seeded_rng", side_effect=stub_seeded_rng):
            with mock.patch.object(game, "enemy_turn") as enemy_turn:
                enemy_turn.side_effect = lambda s: None
                game.start_player_turn(state)

        combat = state["run"]["combat"]
        self.assertEqual(game.status_get(combat["player"], "freeze"), 0)
        self.assertTrue(any("заморожен" in entry for entry in combat.get("log", [])))

    def test_enemy_stun_and_intent_refresh(self):
        state = make_base_state()
        enemy = state["run"]["combat"]["enemies"][0]
        enemy["statuses"]["stun"] = 1

        def stub_choose_intent(ent, rng):
            ent["intent"] = {"type": "block", "name": "Подготовка", "block": 0}
            ent["next_move"] = {"id": "wait", "name": "Ждёт", "type": "block", "block": 0}

        with mock.patch.object(game, "choose_intent", side_effect=stub_choose_intent):
            game.enemy_turn(state)

        self.assertEqual(game.status_get(enemy, "stun"), 0)
        self.assertEqual(enemy.get("last_move"), None)
        self.assertEqual(enemy.get("intent", {}).get("name"), "Подготовка")


if __name__ == "__main__":
    unittest.main()

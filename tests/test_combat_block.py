import random
import unittest

import game


def make_enemy(block: int, statuses=None):
    move = {"id": "wait", "name": "Wait", "type": "attack", "dmg": 0}
    return {
        "id": "dummy",
        "name": "Манекен",
        "hp": 20,
        "max_hp": 20,
        "block": block,
        "statuses": statuses or {},
        "buffs": {},
        "vars": {"phase": "base", "status_bonus": {}},
        "status_immunities": [],
        "tier": 1,
        "moves": [move],
        "intent": None,
        "last_move": None,
        "next_move": move,
    }


def make_player():
    return {
        "name": "Игрок",
        "hp": 30,
        "max_hp": 30,
        "block": 0,
        "mana_max": 3,
        "mana": 3,
        "statuses": {},
        "buffs": {},
        "crit": game.content.CRIT_BASE_CHANCE,
    }


def make_combat_state(enemy):
    run = {
        "hp": 30,
        "max_hp": 30,
        "floor": 1,
        "act": 1,
        "seed": 123,
        "rng_ctr": 0,
        "deck": [],
        "relics": [],
    }
    player = make_player()
    combat = {
        "turn": 1,
        "phase": "enemy",
        "player": player,
        "enemies": [enemy],
        "draw_pile": [],
        "discard_pile": [],
        "exhaust_pile": [],
        "hand": [],
        "pending": None,
        "log": [],
        "_rng": random.Random(0),
    }
    run["combat"] = combat
    state = {"run": run, "screen": "COMBAT"}
    return state, combat, player


class EnemyBlockTests(unittest.TestCase):
    def test_enemy_block_absorbs_player_attack(self):
        enemy = make_enemy(block=10)
        _, combat, player = make_combat_state(enemy)

        taken, _ = game.deal_damage(combat, player, enemy, 8, allow_crit=False, source="test")

        self.assertEqual(taken, 0)
        self.assertEqual(enemy["hp"], 20)
        self.assertEqual(enemy["block"], 2)

    def test_enemy_block_clears_at_start_of_enemy_turn(self):
        enemy = make_enemy(block=6, statuses={"stun": 1})
        state, combat, player = make_combat_state(enemy)

        game.deal_damage(combat, player, enemy, 4, allow_crit=False, source="setup")
        self.assertEqual(enemy["block"], 2)

        game.enemy_turn(state)

        self.assertEqual(enemy["block"], 0)
        self.assertEqual(enemy["statuses"].get("stun", 0), 0)


if __name__ == "__main__":
    unittest.main()

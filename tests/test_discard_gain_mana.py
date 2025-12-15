import game


def test_scavenge_adds_mana_after_discard_choice():
    run = {"seed": 1, "rng_ctr": 0}
    combat = {
        "player": {"hp": 30, "max_hp": 30, "mana": 2, "mana_max": 3, "buffs": {}, "statuses": {}},
        "hand": [game.make_card_instance("SCAVENGE"), game.make_card_instance("ARCANE_JAB")],
        "draw_pile": [],
        "discard_pile": [],
        "exhaust_pile": [],
        "enemies": [{"hp": 10, "max_hp": 10}],
        "phase": "player",
        "pending": None,
    }
    run["combat"] = combat
    state = {"run": run}

    card_uid = combat["hand"][0]["uid"]
    game.play_card(state, card_uid, None)

    assert combat["pending"] and combat["pending"]["type"] == "discard_choose"
    assert combat["player"]["mana"] == 1  # заплатили за розыгрыш

    discard_uid = combat["hand"][0]["uid"]
    game.resolve_pending(state, {"uids": [discard_uid]})

    assert combat["pending"] is None
    assert combat["player"]["mana"] == 3  # +2 маны после сброса

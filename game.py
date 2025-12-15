# game.py
# Сердце игры: генерация забега, карта/этажи, бой, награды, автосейв-структура.

from __future__ import annotations
from typing import Dict, Any, List, Optional, Tuple
import os, json, time, uuid, random, copy, math

import content

SAVE_VERSION = 1

# ---- утилиты ----

def now_ts() -> int:
    return int(time.time())

def clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))

def deep(obj):
    return copy.deepcopy(obj)

def make_uid(prefix="c") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"

def act_for_floor(floor: int) -> int:
    # 10 этажей на цикл: 1–4 акт1 (босс 4), 5–8 акт2 (босс 8), 9–10 акт3 (босс 10)
    if floor <= 4: return 1
    if floor <= 8: return 2
    return 3

def is_boss_floor(floor: int) -> bool:
    return floor in (4, 8, 10)

def enemy_scale(run: Dict[str, Any]) -> float:
    # Нарастающая сложность: выбранный уровень + прогресс по этажам + бесконечные циклы
    d = run.get("difficulty", 0)
    floor = run.get("floor", 1)
    act = run.get("act", 1)
    loop = run.get("loop", 0)
    # мягкая, но заметная шкала
    scale = 1.0 + 0.06 * d + 0.03 * (floor - 1) + 0.12 * (act - 1) + 0.10 * loop
    return scale


def max_enemy_tier_for_floor(floor: int, loop: int = 0) -> int:
    if loop > 0 or floor >= 7:
        return 3
    if floor >= 3:
        return 2
    return 1


def enemy_pool_for_floor(run: Dict[str, Any]) -> List[Dict[str, Any]]:
    floor = int(run.get("floor", 1))
    loop = int(run.get("loop", 0))
    tier = max_enemy_tier_for_floor(floor, loop)
    pool = [e for e in content.ENEMIES if int(e.get("tier", 1)) <= tier]
    return pool or content.ENEMIES

def seeded_rng(run: Dict[str, Any]) -> random.Random:
    # детерминированный rng через счётчик
    seed = int(run.get("seed", 12345))
    ctr = int(run.get("rng_ctr", 0))
    run["rng_ctr"] = ctr + 1
    mix = (seed ^ (ctr * 0x9E3779B1)) & 0xFFFFFFFF
    return random.Random(mix)

def starter_deck() -> List[Dict[str, Any]]:
    # 10 стартовых карт (простые, без классов)
    # Немного всего, чтобы было куда билдиться.
    base = [
        ("ARCANE_JAB", False),
        ("ARCANE_JAB", False),
        ("GUARD_SIGIL", False),
        ("GUARD_SIGIL", False),
        ("SPARK_SHOT", False),
        ("SIDESTEP_GLYPH", False),
        ("FOCUS", False),
        ("MANA_DRIP", False),
        ("RUNE_SLASH", False),
        ("CHAIN_PULL", False),
    ]
    return [make_card_instance(cid, up) for cid, up in base]

def make_card_instance(card_id: str, upgraded: bool=False) -> Dict[str, Any]:
    return {
        "uid": make_uid("card"),
        "id": card_id,
        "up": bool(upgraded),
        # мета-поля (не обязаны быть у всех):
        "note": "",
    }

def add_card_to_deck(run: Dict[str, Any], card_id: str, upgraded: bool=False) -> Dict[str, Any]:
    inst = make_card_instance(card_id, upgraded)
    run.setdefault("deck", []).append(inst)
    return inst

def add_curse_to_deck(run: Dict[str, Any], curse_id: Optional[str] = None, rng: Optional[random.Random] = None) -> Dict[str, Any]:
    r = rng or random.Random()
    cid = curse_id or r.choice(content.CURSES)["id"]
    inst = make_card_instance(cid, False)
    run.setdefault("deck", []).append(inst)
    return inst

def is_curse_card(card_def: Dict[str, Any]) -> bool:
    return card_def.get("type") == "curse"

def has_relic(run: Dict[str, Any], relic_id: str) -> bool:
    return relic_id in run.get("relics", [])

def grant_relic(run: Dict[str, Any], relic_id: str) -> None:
    run.setdefault("relics", [])
    if relic_id not in run["relics"]:
        run["relics"].append(relic_id)

def random_relic(rng: random.Random, owned: Optional[List[str]] = None) -> Optional[str]:
    owned = owned or []
    pool = [r for r in content.RELICS if r["id"] not in owned]
    if not pool:
        return None
    return rng.choice(pool)["id"]

def ensure_rarity_pity(run: Dict[str, Any]) -> Dict[str, int]:
    rp = run.get("rarity_pity") or {}
    run["rarity_pity"] = {
        "rare": int(rp.get("rare", 0)),
        "legendary": int(rp.get("legendary", 0)),
    }
    return run["rarity_pity"]

def roll_card_rarity(run: Dict[str, Any], rng: random.Random) -> str:
    pity = ensure_rarity_pity(run)
    pity["rare"] += 1
    pity["legendary"] += 1
    w = dict(content.RARITY_WEIGHTS)
    floor = int(run.get("floor", 1))
    # Немного повышаем редкие карты по мере прогресса
    w["uncommon"] += max(0, floor // 2)
    w["rare"] += max(3, floor - 1)
    w["legendary"] += max(1, floor // 3)
    # гарантии после долгого отсутствия
    if pity["rare"] >= 4:
        w["rare"] += 25
    if pity["legendary"] >= 7:
        w["legendary"] += 12
    pick = content.weighted_choice(rng, [{"r": r, "w": w[r]} for r in content.RARITIES], "w")["r"]
    if pick == "rare":
        pity["rare"] = 0
    if pick == "legendary":
        pity["legendary"] = 0
    return pick

def generate_card_choices(run: Dict[str, Any], rng: random.Random, k: int = 3) -> List[str]:
    rarities = [roll_card_rarity(run, rng) for _ in range(k)]
    if not any(r in ("uncommon", "rare", "legendary") for r in rarities):
        rarities[-1] = "uncommon"
    ids: List[str] = []
    for r in rarities:
        pool = [c for c in content.CARDS if c["rarity"] == r]
        ids.append(rng.choice(pool)["id"])
    return ids

def card_cost(card_def: Dict[str, Any], inst: Dict[str, Any]) -> int:
    base = int(card_def["cost"])
    mod = int(inst.get("temp_cost_mod", 0))
    return max(0, base - mod)

def crit_chance(player: Dict[str, Any]) -> float:
    base = float(player.get("crit", content.CRIT_BASE_CHANCE))
    bonus = 0.0
    bonus += 0.10 * buff_count(player, "crit_plus_10")
    bonus += 0.15 * buff_count(player, "crit_plus_15")
    bonus += 0.25 * buff_count(player, "crit_godmode")
    return clamp(int((base + bonus) * 1000), 0, 1000) / 1000.0

def crit_mult(player: Dict[str, Any]) -> float:
    return 2.0 + float(buff_count(player, "crit_godmode"))

def status_get(ent: Dict[str, Any], status: str) -> int:
    return int(ent.get("statuses", {}).get(status, 0))

def status_add(ent: Dict[str, Any], status: str, stacks: int, *, combat: Optional[Dict[str, Any]] = None, source: Optional[str] = None) -> bool:
    if stacks <= 0:
        return False
    immune = set(ent.get("status_immunities", []))
    if status in immune:
        if combat and source:
            log(combat, f"{ent.get('name', 'Цель')} игнорирует {status}.")
        return False
    ent.setdefault("statuses", {})
    ent["statuses"][status] = int(ent["statuses"].get(status, 0)) + int(stacks)
    return True

def status_set(ent: Dict[str, Any], status: str, stacks: int):
    ent.setdefault("statuses", {})
    if stacks <= 0:
        ent["statuses"].pop(status, None)
    else:
        ent["statuses"][status] = int(stacks)


def status_with_bonus(attacker: Optional[Dict[str, Any]], status: str, stacks: int) -> int:
    bonus_map = (attacker or {}).get("vars", {}).get("status_bonus", {}) or {}
    return max(0, stacks + int(bonus_map.get(status, 0)))


def buff_count(ent: Dict[str, Any], buff: str) -> int:
    return int(ent.get("buffs", {}).get(buff, 0))

def status_dec(ent: Dict[str, Any], status: str, dec: int=1):
    s = status_get(ent, status) - dec
    status_set(ent, status, s)

def log(combat: Dict[str, Any], msg: str):
    combat.setdefault("log", [])
    combat["log"].append(msg)
    combat["log"] = combat["log"][-80:]  # ограничим историю

# ---- состояние/сейвы ----

def default_state() -> Dict[str, Any]:
    return {
        "version": SAVE_VERSION,
        "updated_at": now_ts(),
        "screen": "MENU",
        "settings": {
            "difficulty": 1,  # шкала
        },
        "meta": {
            "last_deck": [],         # список {id, up} после последнего забега (для наследования)
            "last_result": None,     # victory/defeat
            "last_seen_at": now_ts(),
        },
        "run": None,                # активный забег
        "ui": {
            "toast": "",
        },
    }

def sanitize_for_client(state: Dict[str, Any]) -> Dict[str, Any]:
    # Делаем "view": добавим карточные дефы в нужных местах, без лишней внутренней кухни.
    st = deep(state)
    run = st.get("run")
    if run:
        run["act"] = act_for_floor(run.get("floor", 1))
        # Заполняем удобные поля для фронта
        run["deck_view"] = [card_view(ci) for ci in run.get("deck", [])]
        run["relics_view"] = [content.RELIC_INDEX[rid] for rid in run.get("relics", []) if rid in content.RELIC_INDEX]
        if run.get("combat"):
            run["combat_view"] = combat_view(run["combat"])
        else:
            run["combat_view"] = None
    # Контент — для кодекса/рендера
    st["content_summary"] = {
        "rarities": content.RARITIES,
        "card_types": content.CARD_TYPES,
        "statuses": content.STATUSES,
        "buffs": {k:{"name":v["name"],"desc":v["desc"]} for k,v in content.BUFFS.items()},
        "curses": {c["id"]: {"name": c["name"], "desc": c["desc"]} for c in content.CURSES},
        "relics": {r["id"]: {"name": r["name"], "desc": r["desc"]} for r in content.RELICS},
        "crit_base": content.CRIT_BASE_CHANCE,
    }
    return st

def continue_run(state: Dict[str, Any]) -> None:
    """Вернуться в актуальный экран после перезагрузки."""
    run = state.get("run")
    state.setdefault("ui", {})
    if not run:
        state["screen"] = "MENU"
        state["ui"]["toast"] = "Активный забег не найден."
        state["updated_at"] = now_ts()
        return

    ensure_path_map(run)
    node_ids = {n["id"] for layer in run["path_map"].get("floors", []) for n in layer}
    if run.get("room_choices"):
        if any(ch.get("id") not in node_ids for ch in run.get("room_choices", [])):
            run["room_choices"] = map_room_choices(run)
    if state.get("screen") == "MAP" and not run.get("room_choices"):
        run["room_choices"] = map_room_choices(run)

    if state.get("screen") in ("VICTORY", "DEFEAT", "INHERIT"):
        # уважим финальные экраны, если вдруг их нужно показать повторно
        state["updated_at"] = now_ts()
        return

    if run.get("combat"):
        state["screen"] = "COMBAT"
    elif run.get("reward"):
        state["screen"] = "REWARD"
    elif run.get("event_pick"):
        state["screen"] = "EVENT_PICK"
    elif run.get("event"):
        state["screen"] = "EVENT"
    elif run.get("shop_remove"):
        state["screen"] = "SHOP_REMOVE"
    elif run.get("shop"):
        state["screen"] = "SHOP"
    elif run.get("room_choices"):
        state["screen"] = "MAP"
    else:
        state["screen"] = "MAP"
    state["updated_at"] = now_ts()

def card_view(inst: Dict[str, Any]) -> Dict[str, Any]:
    d = content.get_card_def(inst["id"], upgraded=bool(inst.get("up", False)))
    v = {
        "uid": inst["uid"],
        "id": inst["id"],
        "up": bool(inst.get("up", False)),
        "name": d["name"] + ("+" if inst.get("up") else ""),
        "rarity": d["rarity"],
        "type": d["type"],
        "cost": d["cost"],
        "desc": d["desc"],
        "target": d["target"],
        "tags": d.get("tags", []),
        "exhaust": bool(d.get("exhaust", False)),
        "stays_in_hand": bool(d.get("stays_in_hand", False)),
        "charge_per_turn": int(d.get("charge_per_turn", 0)),
    }
    return v

def combat_view(combat: Dict[str, Any]) -> Dict[str, Any]:
    # В бою нужен ещё charge/temp_cost_mod, чтобы красиво показывать
    v = deep(combat)
    # заменим карты в руке на view с динамикой
    hand = []
    for inst in combat.get("hand", []):
        d = content.get_card_def(inst["id"], upgraded=bool(inst.get("up", False)))
        dmg_preview = preview_damage(d, inst, combat)
        hv = card_view(inst)
        hv["uid"] = inst["uid"]
        hv["eff_cost"] = card_cost(d, inst)
        hv["charge"] = int(inst.get("charge", 0))
        hv["dmg_preview"] = dmg_preview
        hand.append(hv)
    v["hand"] = hand
    v["draw_count"] = len(combat.get("draw_pile", []))
    v["discard_count"] = len(combat.get("discard_pile", []))
    v["discard_pile_cards"] = [card_view(ci) for ci in combat.get("discard_pile", [])][-18:]
    v["exhaust_count"] = len(combat.get("exhaust_pile", []))
    # игрок
    p = combat.get("player", {})
    v["player"] = {
        "hp": p.get("hp", 0),
        "max_hp": p.get("max_hp", 0),
        "block": p.get("block", 0),
        "mana": p.get("mana", 0),
        "mana_max": p.get("mana_max", 0),
        "statuses": p.get("statuses", {}),
        "buffs": p.get("buffs", {}),
        "crit": round(crit_chance(p), 3),
    }
    # враги
    enemies = []
    for e in combat.get("enemies", []):
        enemies.append({
            "id": e["id"],
            "name": e["name"],
            "hp": e["hp"],
            "max_hp": e["max_hp"],
            "block": e.get("block", 0),
            "statuses": e.get("statuses", {}),
            "intent": e.get("intent", {}),
        })
    v["enemies"] = enemies
    # pending
    v["pending"] = combat.get("pending", None)
    return v

def preview_damage(card_def: Dict[str, Any], inst: Dict[str, Any], combat: Dict[str, Any]) -> Optional[int]:
    # очень приблизительный предпросмотр для attack/aoe
    try:
        if card_def["type"] not in ("attack", "skill"): 
            return None
        total = 0
        for eff in card_def.get("effects", []):
            if eff.get("op") == "damage":
                amt = eff.get("amount", 0)
                if isinstance(amt, dict) and amt.get("plus_charge"):
                    total += int(amt.get("base", 0)) + int(inst.get("charge", 0))
                else:
                    total += int(amt)
            if eff.get("op") == "aoe_damage":
                total += int(eff.get("amount", 0))
        return total if total > 0 else None
    except Exception:
        return None

# ---- генерация забега ----

def new_run(state: Dict[str, Any], *, keep_cards: Optional[List[Dict[str, Any]]] = None) -> None:
    """Создать новый забег. keep_cards — 0..3 карты, которые заменят 3 слабые стартовые."""
    run_seed = random.randint(1, 2_000_000_000)
    diff = int(state.get("settings", {}).get("difficulty", 1))
    run = {
        "id": make_uid("run"),
        "seed": run_seed,
        "rng_ctr": 0,
        "started_at": now_ts(),
        "difficulty": diff,
        "loop": 0,           # бесконечные циклы после победы
        "floor": 1,
        "act": 1,
        "gold": 60,
        "max_hp": 70,
        "hp": 70,
        "rarity_pity": {"rare": 0, "legendary": 0},
        "deck": starter_deck(),
        "relics": ["STARTER_SEAL"],
        "combat": None,
        "room": None,
        "room_choices": [],
        "reward": None,
        "shop": None,
        "event": None,
        "act_end": None,
        "inherit": None,
        "path_map": None,
        "visited_nodes": [],
        "current_node": None,
    }

    # Наследование: заменим 3 «простых» карты на выбранные, но оставим 10 карт в старте.
    if keep_cards:
        # выбросим из стартовой колоды 3 самых «простых» по приоритету
        weak_ids = ["SPARK_SHOT","SIDESTEP_GLYPH","MANA_DRIP"]
        removed = 0
        for wid in weak_ids:
            for i, ci in enumerate(list(run["deck"])):
                if removed >= 3: break
                if ci["id"] == wid:
                    run["deck"].pop(i)
                    removed += 1
                    break
        # добавим выбранные (клон с новым uid)
        for kc in keep_cards[:3]:
            run["deck"].append(make_card_instance(kc["id"], bool(kc.get("up", False))))
        # если всё равно не 10 (вдруг), добьём стартером
        while len(run["deck"]) < 10:
            run["deck"].append(make_card_instance("ARCANE_JAB", False))
        while len(run["deck"]) > 10:
            run["deck"].pop()

    run["path_map"] = build_path_map(run)
    run["room_choices"] = generate_room_choices(run)
    state["run"] = run
    state["screen"] = "MAP"
    state["ui"]["toast"] = "Новый забег: тюрьма ждёт."
    state["updated_at"] = now_ts()

def generate_room_choices(run: Dict[str, Any]) -> List[Dict[str, Any]]:
    ensure_path_map(run)
    run["act"] = act_for_floor(int(run.get("floor", 1)))
    return map_room_choices(run)


def ensure_path_map(run: Dict[str, Any]) -> None:
    if run.get("path_map"):
        return
    run["path_map"] = build_path_map(run, use_run_rng=False)
    run.setdefault("visited_nodes", [])
    run.setdefault("current_node", None)


def room_label_and_hint(room_type: str, act: int) -> Tuple[str, str]:
    label_map = {
        "fight": "БОЙ",
        "elite": "ЭЛИТА",
        "event": "СОБЫТИЕ",
        "shop": "ЛАВКА",
        "campfire": "КОСТЁР",
        "chest": "СУНДУК",
        "boss": f"БОСС акта {act}",
    }
    hint_map = {
        "fight": "Запах металла и магии.",
        "elite": "Тяжёлые шаги. И смех, как скрип.",
        "event": "Случайность в тюрьме — всегда чья-то работа.",
        "shop": "Тут всё продаётся, кроме свободы.",
        "campfire": "Костёр без дыма. И без вопросов.",
        "chest": "Щёлк. Пыль. Возможно, зубы.",
        "boss": "Огромная дверь. За ней — бухгалтерия боли.",
    }
    return label_map.get(room_type, room_type), hint_map.get(room_type, "…")


def build_path_map(run: Dict[str, Any], *, use_run_rng: bool = True) -> Dict[str, Any]:
    rng = seeded_rng(run) if use_run_rng else random.Random(int(run.get("seed", 12345)) ^ 0xC0FFEE)
    lanes = 5
    floors: List[List[Dict[str, Any]]] = []
    prev_layer: List[Dict[str, Any]] = []

    for floor in range(1, 11):
        act = act_for_floor(floor)
        is_boss = is_boss_floor(floor)
        count = 1 if is_boss else rng.randint(3, 4)
        positions = sorted(rng.sample(range(lanes), k=count)) if count < lanes else list(range(lanes))
        layer: List[Dict[str, Any]] = []
        for pos in positions:
            rtype = "boss" if is_boss else weighted_room(rng, {
                "fight": 42,
                "elite": 10 + 5 * (act - 1),
                "event": 18,
                "shop": 8,
                "campfire": 12,
                "chest": 10,
            })
            label, hint = room_label_and_hint(rtype, act)
            node = {
                "id": make_uid("node"),
                "type": rtype,
                "label": label,
                "hint": hint,
                "floor": floor,
                "lane": pos,
                "prev": [],
                "next": [],
            }
            layer.append(node)

        # соединения со слоем сверху
        if prev_layer:
            for p in prev_layer:
                target_pool = sorted(layer, key=lambda n: abs(n["lane"] - p["lane"]))
                tcount = 1 if len(target_pool) == 1 else (2 if rng.random() < 0.55 else 1)
                picks = rng.sample(target_pool[:min(len(target_pool), 3)], k=tcount)
                for tgt in picks:
                    p["next"].append(tgt["id"])
                    tgt["prev"].append(p["id"])
            # гарантируем, что у каждого есть хотя бы один вход
            for tgt in layer:
                if not tgt["prev"]:
                    anchor = min(prev_layer, key=lambda p: abs(p["lane"] - tgt["lane"]))
                    anchor["next"].append(tgt["id"])
                    tgt["prev"].append(anchor["id"])

        floors.append(layer)
        prev_layer = layer

    return {"floors": floors, "lanes": lanes}


def map_room_choices(run: Dict[str, Any]) -> List[Dict[str, Any]]:
    path = run.get("path_map") or {}
    floors = path.get("floors", [])
    floor = int(run.get("floor", 1))
    prev_node_id = run.get("current_node")
    idx = floor - 1
    if not (0 <= idx < len(floors)):
        return []

    layer = floors[idx]
    act = act_for_floor(floor)
    options: List[Dict[str, Any]] = []
    for node in layer:
        if floor > 1 and prev_node_id and prev_node_id not in node.get("prev", []):
            continue
        label, hint = room_label_and_hint(node["type"], act)
        options.append({
            "id": node["id"],
            "type": node["type"],
            "label": label,
            "hint": hint,
            "floor": node["floor"],
            "lane": node.get("lane", 0),
        })
    return options

def weighted_room(rng: random.Random, weights: Dict[str, int]) -> str:
    total = sum(max(0, w) for w in weights.values())
    r = rng.uniform(0, total)
    acc = 0.0
    for k, w in weights.items():
        acc += max(0, w)
        if r <= acc:
            return k
    return "fight"

# ---- особые комнатные события ----

ROOM_TWISTS = [
    {"id": "TWIST_POISON_FOG", "name": "Токсичная вентиляция", "desc": "Ядовитый туман пропитывает комнату.", "poison_on_start": 2, "hp_ping": 2},
    {"id": "TWIST_MIRROR_ECHO", "name": "Зеркальный резонанс", "desc": "Стены отражают заклинания и награды.", "start_reflect": True, "extra_reward": True},
    {"id": "TWIST_CONTRABAND", "name": "Контрабанда", "desc": "Крысы проносят монеты и скидки.", "shop_discount": 0.8, "bonus_gold": 12},
]

def maybe_roll_room_twist(state: Dict[str, Any], room_type: str) -> Optional[Dict[str, Any]]:
    run = state["run"]
    rng = seeded_rng(run)
    if rng.random() >= 0.5:
        run.pop("room_twist", None)
        return None
    twist = deep(rng.choice(ROOM_TWISTS))
    run["room_twist"] = twist
    if room_type not in ("fight", "elite", "boss") and twist.get("hp_ping"):
        run["hp"] = max(1, int(run.get("hp", 0)) - int(twist.get("hp_ping", 0)))
    state.setdefault("ui", {})
    state["ui"]["toast"] = f"Особое событие: {twist['name']} — {twist['desc']}"
    return twist

# ---- бой ----

def apply_relics_on_combat_start(run: Dict[str, Any], combat: Dict[str, Any]) -> None:
    p = combat.get("player", {})
    if has_relic(run, "STARTER_SEAL"):
        p["mana_max"] += 1
        p["mana"] += 1
    if has_relic(run, "BLOOD_VIAL"):
        p["hp"] = min(int(p.get("max_hp", 0)), int(p.get("hp", 0)) + 5)
        log(combat, "Сосуд крови: лечение +5 HP.")
    if has_relic(run, "ECHO_CORE"):
        log(combat, "Ядро эха: награда даст +1 выбор карты.")
    if has_relic(run, "RAT_POUCH"):
        log(combat, "Кошель крысолова шелестит — жетонов будет больше.")


def start_combat(state: Dict[str, Any], room_type: str) -> None:
    run = state["run"]
    rng = seeded_rng(run)

    scale = enemy_scale(run)
    floor = int(run["floor"])
    act = int(run["act"])

    if is_boss_floor(floor):
        room_type = "boss"

    # Выберем врагов
    enemies: List[Dict[str, Any]] = []
    if room_type == "boss":
        boss_tmpl = content.BOSSES[act-1]
        enemies = [instantiate_enemy(boss_tmpl, rng, scale)]
    elif room_type == "elite":
        # 1 элита или 2 слабых элиты
        if rng.random() < 0.7:
            enemies = [instantiate_enemy(rng.choice(content.ELITES), rng, scale)]
        else:
            e1 = instantiate_enemy(rng.choice(content.ELITES), rng, scale*0.85)
            e2 = instantiate_enemy(rng.choice(content.ENEMIES), rng, scale*0.85)
            enemies = [e1, e2]
    else:  # fight
        n = 1 if rng.random() < 0.45 else (2 if rng.random() < 0.75 else 3)
        pool = enemy_pool_for_floor(run)
        enemies = [instantiate_enemy(rng.choice(pool), rng, scale) for _ in range(n)]

    # Состояние игрока в бою
    player = {
        "name": "Игрок",
        "hp": int(run["hp"]),
        "max_hp": int(run["max_hp"]),
        "block": 0,
        "mana_max": 3,
        "mana": 3,
        "statuses": {},
        "buffs": {},   # бафы «до конца боя»
        "crit": content.CRIT_BASE_CHANCE,
    }

    # Скопируем колоду в боевой экземпляр
    draw_pile = []
    for ci in run["deck"]:
        inst = deep(ci)
        inst["charge"] = 0
        inst["temp_cost_mod"] = 0
        draw_pile.append(inst)

    rng.shuffle(draw_pile)

    combat = {
        "turn": 1,
        "phase": "player",
        "player": player,
        "enemies": enemies,
        "draw_pile": draw_pile,
        "discard_pile": [],
        "exhaust_pile": [],
        "hand": [],
        "pending": None,
        "log": [],
    }

    apply_relics_on_combat_start(run, combat)

    # Выставим начальные намерения
    for e in combat["enemies"]:
        choose_intent(e, rng)

    # Старт: добор до 6
    draw_to_hand(combat, n=6, rng=rng)

    twist = run.get("room_twist")
    if twist:
        if twist.get("poison_on_start"):
            stacks = int(twist.get("poison_on_start", 0))
            status_add(player, "poison", stacks, combat=combat, source=twist["name"])
            for e in combat["enemies"]:
                status_add(e, "poison", stacks, combat=combat, source=twist["name"])
            log(combat, f"{twist['name']}: все получают {stacks} Яда.")
        if twist.get("start_reflect"):
            add_buff(player, "reflect_half_1turn")
            log(combat, f"{twist['name']}: твоё первое попадание отражает урон.")

    log(combat, f"Этаж {run['floor']}, акт {run['act']}. В бой!")
    run["combat"] = combat
    state["screen"] = "COMBAT"
    state["updated_at"] = now_ts()

def instantiate_enemy(tmpl: Dict[str, Any], rng: random.Random, scale: float) -> Dict[str, Any]:
    hp = int(round(tmpl["max_hp"] * scale))
    hp = max(10, hp)
    e = {
        "id": tmpl["id"],
        "name": tmpl["name"],
        "hp": hp,
        "max_hp": hp,
        "block": 0,
        "statuses": {},
        "buffs": {},
        "vars": {"phase": tmpl.get("phase", "base"), "status_bonus": {}},
        "status_immunities": list(tmpl.get("immune_to", [])),
        "tier": int(tmpl.get("tier", 1)),
        "moves": deep(tmpl["moves"]),
        "intent": None,
        "last_move": None,
    }
    return e


def move_available(enemy: Dict[str, Any], move: Dict[str, Any]) -> bool:
    phase = enemy.get("vars", {}).get("phase", "base")
    hp = float(enemy.get("hp", 0))
    hp_pct = hp / float(enemy.get("max_hp", 1)) if enemy.get("max_hp") else 1.0
    req = move.get("requires", {}) or {}
    if move.get("threshold") is not None and hp_pct > float(move.get("threshold", 1.0)):
        return False
    if move.get("set_phase") and phase == move.get("set_phase"):
        return False
    if req.get("phase_is") and phase != req.get("phase_is"):
        return False
    if req.get("phase_not") and phase == req.get("phase_not"):
        return False
    if req.get("hp_pct_below") is not None and hp_pct >= float(req.get("hp_pct_below", 1.0)):
        return False
    return True


def choose_intent(enemy: Dict[str, Any], rng: random.Random):
    moves = enemy.get("moves", [])
    available = [m for m in moves if move_available(enemy, m)]
    if not available:
        available = moves
    # небольшой анти-спам: уменьшаем вес последнего
    weighted = []
    for m in available:
        w = int(m.get("w", 1))
        if enemy.get("last_move") and enemy["last_move"] == m.get("id"):
            w = max(1, w // 2)
        weighted.append({"m": m, "w": w})
    total = sum(x["w"] for x in weighted)
    r = rng.uniform(0, total)
    acc = 0.0
    pick = weighted[-1]["m"]
    for x in weighted:
        acc += x["w"]
        if r <= acc:
            pick = x["m"]
            break
    enemy["intent"] = summarize_move(pick)
    enemy["next_move"] = pick

def summarize_move(move: Dict[str, Any]) -> Dict[str, Any]:
    t = move.get("type")
    if t == "attack":
        return {"type":"attack","name":move["name"],"dmg":move.get("dmg",0)}
    if t == "attack_apply":
        return {"type":"attack_apply","name":move["name"],"dmg":move.get("dmg",0),"status":move.get("status"),"stacks":move.get("stacks",0)}
    if t == "apply":
        return {"type":"apply","name":move["name"],"status":move.get("status"),"stacks":move.get("stacks",0)}
    if t == "apply_all":
        return {"type":"apply_all","name":move["name"],"status":move.get("status"),"stacks":move.get("stacks",0)}
    if t == "block":
        return {"type":"block","name":move["name"],"block":move.get("block",0)}
    if t == "heal":
        return {"type":"heal","name":move["name"],"heal":move.get("amount",0)}
    if t == "phase_shift":
        return {"type":"phase","name":move.get("name"),"desc":move.get("intent_desc") or "Смена фазы", "phase": move.get("set_phase"), "block": move.get("block", 0)}
    if t == "counter_prep":
        return {"type":"counter","name":move.get("name"),"dmg":move.get("counter_dmg",0),"status":move.get("status"),"stacks":move.get("stacks",0),"desc":move.get("intent_desc"),"block":move.get("block",0)}
    if t == "self_debuff":
        return {"type":"weird","name":move["name"],"desc":move.get("desc","")}
    return {"type":"weird","name":move.get("name","?")}

def draw_to_hand(combat: Dict[str, Any], n: int, rng: random.Random):
    for _ in range(n):
        if len(combat["hand"]) >= 6:
            return
        if not combat["draw_pile"]:
            # мешаем сброс в колоду
            if combat["discard_pile"]:
                combat["draw_pile"] = combat["discard_pile"]
                combat["discard_pile"] = []
                rng.shuffle(combat["draw_pile"])
                log(combat, "Перетасовка сброса в колоду.")
            else:
                return
        inst = combat["draw_pile"].pop()
        # при доборе заряд обнулять не надо, он и так 0 пока не копится в руке
        combat["hand"].append(inst)

def find_hand_card(combat: Dict[str, Any], uid: str) -> Optional[Dict[str, Any]]:
    for c in combat.get("hand", []):
        if c.get("uid") == uid:
            return c
    return None

def remove_hand_card(combat: Dict[str, Any], uid: str) -> Optional[Dict[str, Any]]:
    for i, c in enumerate(combat.get("hand", [])):
        if c.get("uid") == uid:
            return combat["hand"].pop(i)
    return None

def enemy_by_index(combat: Dict[str, Any], idx: int) -> Optional[Dict[str, Any]]:
    enemies = combat.get("enemies", [])
    if 0 <= idx < len(enemies):
        return enemies[idx]
    return None

# ---- применение урона/блока ----

def compute_damage(attacker: Dict[str, Any], defender: Dict[str, Any], base: int) -> int:
    dmg = float(base)
    # weak на атакующем
    if status_get(attacker, "weak") > 0:
        dmg *= 0.75
    # freeze на атакующем: тоже -25%
    if status_get(attacker, "freeze") > 0:
        dmg *= 0.75
    # vulnerable на защищающемся
    if status_get(defender, "vulnerable") > 0:
        dmg *= 1.25
    return max(0, int(round(dmg)))

def deal_damage(combat: Dict[str, Any], attacker: Dict[str, Any], defender: Dict[str, Any], amount: int, *, allow_crit: bool=True, source: str="") -> Tuple[int,bool]:
    rng = combat.get("_rng")
    if rng is None:
        rng = random.Random(0)
    dmg = int(amount)
    is_crit = False
    if allow_crit and attacker is combat.get("player"):
        cc = crit_chance(attacker)
        if rng.random() < cc:
            is_crit = True
            dmg = int(round(dmg * crit_mult(attacker)))

    # фазы/бафы врагов
    bonus_mult = float(attacker.get("vars", {}).get("dmg_mult", 1.0))
    if bonus_mult != 1.0:
        dmg = int(round(dmg * bonus_mult))
    overdrive_active = False
    charge = buff_count(attacker, "arcane_charge")
    if charge:
        dmg = int(round(dmg * 1.15))
        consume_buff(attacker, "arcane_charge", 1)
    overdrive = buff_count(attacker, "arcane_overdrive")
    if overdrive:
        overdrive_active = True
        dmg = int(round(dmg * (1.10 + 0.05 * overdrive)))

    incoming = compute_damage(attacker, defender, dmg)
    dmg = incoming

    # блок
    block = int(defender.get("block", 0))
    pierce = 0.25 if overdrive_active else 0.0
    effective_block = int(math.floor(block * (1 - pierce)))
    taken = max(0, dmg - effective_block)
    defender["block"] = max(0, block - dmg)
    defender["hp"] = max(0, int(defender.get("hp", 0)) - taken)

    # thorns
    th = status_get(defender, "thorns")
    if th > 0 and taken > 0 and attacker is not defender:
        attacker["hp"] = max(0, int(attacker.get("hp", 0)) - th)
        log(combat, f"Шипы: {th} урона в ответ.")

    # отражение (только на игроке)
    if defender is combat.get("player"):
        half_reflect = buff_count(defender, "reflect_half_1turn")
        full_reflect = buff_count(defender, "reflect_full_1turn")
        if (half_reflect or full_reflect) and incoming > 0:
            mult = 1.0 if full_reflect else 0.5 * half_reflect
            reflect = int(math.floor(incoming * mult))
            if attacker is not defender and reflect > 0:
                attacker["hp"] = max(0, int(attacker.get("hp", 0)) - reflect)
                log(combat, f"Зеркальная защита отражает {reflect} урона.")

    if source:
        log(combat, f"{source}: {dmg}{' (КРИТ!)' if is_crit else ''}")

    # телеграфируемая контратака (у врагов)
    if defender is not combat.get("player") and attacker is combat.get("player"):
        counter = defender.get("vars", {}).pop("counter_ready", None)
        if counter and defender.get("hp", 0) > 0:
            counter_name = counter.get("name", "Контратака")
            c_dmg = int(counter.get("dmg", 0))
            if c_dmg > 0:
                deal_damage(combat, defender, attacker, c_dmg, allow_crit=False, source=f"{defender.get('name','Враг')} — {counter_name}")
            c_status = counter.get("status")
            c_stacks = int(counter.get("stacks", 0))
            if c_status and c_stacks:
                status_add(attacker, c_status, c_stacks, combat=combat, source=counter_name)
            log(combat, f"{defender.get('name','Враг')} отвечает: {counter_name}.")
    return taken, is_crit

# ---- эффекты карт ----

def play_card(state: Dict[str, Any], card_uid: str, target: Optional[int]) -> None:
    run = state["run"]
    combat = run.get("combat")
    if not combat or combat.get("phase") != "player":
        return

    rng = seeded_rng(run)
    combat["_rng"] = rng

    # pending-выборы блокируют игру
    if combat.get("pending"):
        return

    inst = find_hand_card(combat, card_uid)
    if not inst:
        return
    cdef = content.get_card_def(inst["id"], upgraded=bool(inst.get("up", False)))
    if is_curse_card(cdef):
        log(combat, "Проклятья не разыграть — их нужно переждать или убрать.")
        return
    cost = card_cost(cdef, inst)
    if combat["player"]["mana"] < cost:
        log(combat, "Недостаточно маны.")
        return

    # таргетинг
    tgt = None
    if cdef["target"] in ("enemy", "any"):
        if target is None:
            log(combat, "Нужна цель.")
            return
        tgt = enemy_by_index(combat, int(target))
        if not tgt or tgt["hp"] <= 0:
            log(combat, "Цель недоступна.")
            return
    elif cdef["target"] == "all_enemies":
        tgt = None
    elif cdef["target"] == "self":
        tgt = combat["player"]
    else:
        tgt = None

    # платим ману
    combat["player"]["mana"] -= cost

    # разыгрываем
    remove_hand_card(combat, card_uid)

    # хук: bounce_next (вернуть следующую сыгранную карту)
    bounced = False
    if buff_count(combat["player"], "bounce_next"):
        # этот баф потребляется, а карта вернётся в руку (кроме exhaust/upgrade)
        consume_buff(combat["player"], "bounce_next", 1)
        bounced = True

    # применим эффекты
    resolve_card_effects(state, combat, inst, cdef, tgt)

    # перемещение карты
    exhaust = bool(cdef.get("exhaust", False)) or (cdef.get("type") == "upgrade")
    # Зарядка сбрасывается, если карта ушла из руки
    inst["charge"] = 0

    if exhaust:
        combat["exhaust_pile"].append(inst)
    else:
        if bounced:
            combat["hand"].append(inst)
            log(combat, "Отмычка: карта вернулась в руку.")
        else:
            combat["discard_pile"].append(inst)

    # проверка победы
    if all(e["hp"] <= 0 for e in combat["enemies"]):
        win_combat(state)
        return

    state["updated_at"] = now_ts()

def resolve_card_effects(state: Dict[str, Any], combat: Dict[str, Any], inst: Dict[str, Any], cdef: Dict[str, Any], target_ent: Optional[Dict[str, Any]]):
    p = combat["player"]
    enemies = combat["enemies"]

    # Особые эффекты: choose_one — фронту нужно выбрать
    for eff in cdef.get("effects", []):
        if eff.get("op") == "choose_one":
            combat["pending"] = {
                "type": "choose_one",
                "card_uid": inst["uid"],
                "options": eff.get("options", []),
            }
            log(combat, "Выбери эффект карты.")
            return

    for eff in cdef.get("effects", []):
        op = eff.get("op")
        if op == "damage":
            amt = eff.get("amount", 0)
            base = 0
            if isinstance(amt, dict) and amt.get("plus_charge"):
                base = int(amt.get("base", 0)) + int(inst.get("charge", 0))
            else:
                base = int(amt)
            no_crit = bool(eff.get("no_crit", False))
            taken, was_crit = deal_damage(combat, p, target_ent, base, allow_crit=not no_crit, source=cdef["name"])
            # on_crit
            if was_crit and eff.get("on_crit"):
                resolve_effect_list(state, combat, eff["on_crit"], p, target_ent)
            # buff: burn_on_hit
            if target_ent:
                burn_boost = buff_count(p, "burn_on_hit")
                burn_boost_2 = buff_count(p, "burn_on_hit_2")
                burn_total = burn_boost + (2 * burn_boost_2)
                if burn_total:
                    status_add(target_ent, "burn", burn_total, combat=combat, source=cdef["name"])
            # echo_attack_half consumes once
            if target_ent:
                echo_stacks = buff_count(p, "echo_attack_half")
                if echo_stacks:
                    consume_buff(p, "echo_attack_half", echo_stacks)
                    half = int(math.floor(base * 0.5))
                    for _ in range(echo_stacks):
                        deal_damage(combat, p, target_ent, half, allow_crit=False, source=cdef["name"]+" (эхо)")
        elif op == "aoe_damage":
            base = int(eff.get("amount", 0))
            bonus = 0
            bonus_if = eff.get("bonus_if_has_any_status")
            if bonus_if:
                # бонус к каждому врагу индивидуально
                for e in enemies:
                    if e["hp"] <= 0: 
                        continue
                    dmg = base
                    if any(status_get(e, s) > 0 for s in bonus_if):
                        dmg += int(eff.get("bonus", 0))
                    deal_damage(combat, p, e, dmg, allow_crit=True, source=cdef["name"])
            else:
                for e in enemies:
                    if e["hp"] > 0:
                        deal_damage(combat, p, e, base, allow_crit=True, source=cdef["name"])
        elif op == "block":
            p["block"] = int(p.get("block", 0)) + int(eff.get("amount", 0))
            log(combat, f"{cdef['name']}: +{eff.get('amount',0)} Блока.")
        elif op == "apply":
            status = eff.get("status")
            stacks = int(eff.get("stacks", 0))
            to = eff.get("to", "enemy")
            if to == "enemy":
                if target_ent: status_add(target_ent, status, stacks, combat=combat, source=cdef["name"])
            elif to == "all_enemies":
                for e in enemies:
                    if e["hp"] > 0: status_add(e, status, stacks, combat=combat, source=cdef["name"])
            elif to == "self":
                status_add(p, status, stacks, combat=combat, source=cdef["name"])
            log(combat, f"{cdef['name']}: {content.STATUSES.get(status,{}).get('name',status)} +{stacks}.")
        elif op == "draw":
            draw_to_hand(combat, n=int(eff.get("n", 1)), rng=combat["_rng"])
            log(combat, f"{cdef['name']}: добор {eff.get('n',1)}.")
        elif op == "gain_mana":
            p["mana"] = int(p.get("mana", 0)) + int(eff.get("n", 1))
            log(combat, f"{cdef['name']}: +{eff.get('n',1)} маны.")
        elif op == "gain_max_mana":
            n = int(eff.get("n", 1))
            dur = eff.get("duration", "combat")
            if dur == "combat":
                p["mana_max"] = int(p.get("mana_max", 0)) + n
                p["mana"] = int(p.get("mana", 0)) + n
                log(combat, f"{cdef['name']}: +{n} макс.маны (бой).")
        elif op == "heal":
            amt = int(eff.get("amount", 0))
            p["hp"] = min(int(p["max_hp"]), int(p["hp"]) + amt)
            log(combat, f"{cdef['name']}: +{amt} HP.")
        elif op == "lose_hp":
            amt = int(eff.get("amount", 0))
            p["hp"] = max(0, int(p["hp"]) - amt)
            log(combat, f"{cdef['name']}: -{amt} HP.")
        elif op == "heal_per_enemy":
            amt = int(eff.get("amount", 0))
            alive = sum(1 for e in enemies if e["hp"] > 0)
            heal = amt * alive
            p["hp"] = min(int(p["max_hp"]), int(p["hp"]) + heal)
            log(combat, f"{cdef['name']}: +{heal} HP.")
        elif op == "discard_choose":
            combat["pending"] = {"type":"discard_choose","n":int(eff.get("n",1))}
            log(combat, "Выбери карты для сброса.")
            return
        elif op == "discard_random":
            n = int(eff.get("n", 1))
            do_discard_random(combat, n=n)
            log(combat, f"{cdef['name']}: случайный сброс {n}.")
        elif op == "take_from_discard":
            combat["pending"] = {"type":"take_from_discard","n":int(eff.get("n",1)),
                                 "reduce_cost": int(eff.get("reduce_cost",0))}
            log(combat, "Выбери карту из сброса.")
            return
        elif op == "add_buff":
            buff = eff.get("buff")
            add_buff(p, buff)
            log(combat, f"{cdef['name']}: баф «{content.BUFFS.get(buff,{}).get('name',buff)}».")
            # некоторые бафы сразу меняют параметры
            if buff in ("battery","battery_plus"):
                inc = 2 if buff=="battery" else 3
                p["mana_max"] += inc
                p["mana"] += inc
        elif op == "if_hand_has_tag":
            tag = eff.get("tag")
            if any(tag in content.get_card_def(ci["id"], bool(ci.get("up"))).get("tags", []) for ci in combat["hand"]):
                resolve_effect_list(state, combat, eff.get("then", []), p, target_ent)
        elif op == "if_enemy_hp_below":
            if target_ent and target_ent["max_hp"] > 0:
                if (target_ent["hp"] / target_ent["max_hp"]) < float(eff.get("pct", 0.5)):
                    resolve_effect_list(state, combat, eff.get("then", []), p, target_ent)
        elif op == "dot_detach_explode":
            if not target_ent: 
                continue
            statuses = eff.get("statuses", [])
            mult = float(eff.get("mult", 1.0))
            total = 0
            for s in statuses:
                total += status_get(target_ent, s)
                status_set(target_ent, s, 0)
            dmg = int(round(total * mult))
            if dmg > 0:
                deal_damage(combat, p, target_ent, dmg, allow_crit=False, source=cdef["name"])
        elif op == "combo":
            for step in eff.get("steps", []):
                # reuse resolve_effect_list
                resolve_effect_list(state, combat, [step], p, target_ent)
        else:
            # неизвестное — пропускаем (архитектура расширяемая)
            pass

def resolve_effect_list(state: Dict[str, Any], combat: Dict[str, Any], effects: List[dict], p: Dict[str, Any], target_ent: Optional[Dict[str, Any]]):
    # Мини-исполнитель эффектов для вложенных then/on_crit и т.п.
    for eff in effects:
        op = eff.get("op")
        if op == "draw":
            draw_to_hand(combat, n=int(eff.get("n", 1)), rng=combat["_rng"])
        elif op == "gain_mana":
            p["mana"] += int(eff.get("n", 1))
        elif op == "block":
            p["block"] += int(eff.get("amount", 0))
        elif op == "apply":
            status = eff.get("status")
            stacks = int(eff.get("stacks", 0))
            to = eff.get("to", "enemy")
            if to == "enemy" and target_ent:
                status_add(target_ent, status, stacks, combat=combat, source="Эффект")
        elif op == "damage":
            if target_ent:
                deal_damage(combat, p, target_ent, int(eff.get("amount", 0)), allow_crit=True, source="Эффект")
        elif op == "add_buff":
            add_buff(p, eff.get("buff"))
        elif op == "heal":
            amt = int(eff.get("amount", 0))
            p["hp"] = min(int(p["max_hp"]), int(p.get("hp", 0)) + amt)
        elif op == "lose_hp":
            p["hp"] = max(0, int(p.get("hp", 0)) - int(eff.get("amount", 0)))
        elif op == "heal_per_enemy":
            amt = int(eff.get("amount", 0))
            alive = sum(1 for e in combat.get("enemies", []) if e.get("hp", 0) > 0)
            p["hp"] = min(int(p["max_hp"]), int(p.get("hp", 0)) + amt * alive)
        else:
            pass

def add_buff(ent: Dict[str, Any], buff: str):
    ent.setdefault("buffs", {})
    ent["buffs"][buff] = int(ent["buffs"].get(buff, 0)) + 1


def consume_buff(ent: Dict[str, Any], buff: str, amount: int = 1) -> int:
    """Уменьшает стаки бафа и возвращает оставшееся количество."""
    if amount <= 0:
        return buff_count(ent, buff)
    ent.setdefault("buffs", {})
    cur = int(ent["buffs"].get(buff, 0))
    if cur <= amount:
        ent["buffs"].pop(buff, None)
        return 0
    ent["buffs"][buff] = cur - amount
    return ent["buffs"][buff]

def do_discard_random(combat: Dict[str, Any], n: int):
    rng = combat.get("_rng") or random.Random(0)
    hand = combat.get("hand", [])
    if not hand:
        return
    # не сбрасываем зарядные карты случайно? оставим, но сбрасываем тоже — иначе слишком сильный билд.
    picks = []
    for _ in range(min(n, len(hand))):
        c = rng.choice(hand)
        hand.remove(c)
        # при уходе из руки заряд обнуляем
        c["charge"] = 0
        combat["discard_pile"].append(c)
        trigger_on_discard(combat, c)
        picks.append(c)
    return

def trigger_on_discard(combat: Dict[str, Any], card_inst: Dict[str, Any]):
    p = combat["player"]
    mana_on_discard = buff_count(p, "mana_on_discard")
    if mana_on_discard:
        p["mana"] += mana_on_discard
        log(combat, f"Баф: сброс -> +{mana_on_discard} маны.")
    mana_block_on_discard = buff_count(p, "mana_block_on_discard")
    if mana_block_on_discard:
        p["mana"] += mana_block_on_discard
        p["block"] += mana_block_on_discard
        log(combat, f"Баф: сброс -> +{mana_block_on_discard} мана и +{mana_block_on_discard} Блок.")
    draw_on_discard = buff_count(p, "draw_on_discard")
    if draw_on_discard:
        draw_to_hand(combat, n=draw_on_discard, rng=combat["_rng"])
        log(combat, f"Баф: сброс -> добор {draw_on_discard}.")
    draw_block_on_discard = buff_count(p, "draw_block_on_discard")
    if draw_block_on_discard:
        draw_to_hand(combat, n=draw_block_on_discard, rng=combat["_rng"])
        p["block"] += draw_block_on_discard
        log(combat, f"Баф: сброс -> добор {draw_block_on_discard} и +{draw_block_on_discard} Блок.")

# ---- pending выборы ----

def resolve_pending(state: Dict[str, Any], payload: Dict[str, Any]) -> None:
    run = state["run"]
    combat = run.get("combat")
    if not combat:
        return
    pending = combat.get("pending")
    if not pending:
        return

    rng = seeded_rng(run)
    combat["_rng"] = rng

    ptype = pending.get("type")
    if ptype == "discard_choose":
        chosen = payload.get("uids", [])
        chosen = chosen[: int(pending.get("n", 1))]
        for uid in chosen:
            c = remove_hand_card(combat, uid)
            if c:
                c["charge"] = 0
                combat["discard_pile"].append(c)
                trigger_on_discard(combat, c)
        combat["pending"] = None
        state["updated_at"] = now_ts()
        return

    if ptype == "take_from_discard":
        uid = payload.get("uid")
        if not uid:
            return
        # найдём в сбросе
        disc = combat.get("discard_pile", [])
        pick = None
        for i, c in enumerate(disc):
            if c.get("uid") == uid:
                pick = disc.pop(i)
                break
        if pick:
            # опционально: -cost
            red = int(pending.get("reduce_cost", 0))
            if red > 0:
                pick["temp_cost_mod"] = int(pick.get("temp_cost_mod", 0)) + red
            combat["hand"].append(pick)
        combat["pending"] = None
        state["updated_at"] = now_ts()
        return

    if ptype == "choose_one":
        idx = int(payload.get("idx", -1))
        opts = pending.get("options", [])
        if 0 <= idx < len(opts):
            effs = opts[idx].get("effects", [])
            resolve_effect_list(state, combat, effs, combat["player"], None)
            combat["pending"] = None
            log(combat, f"Выбрано: {opts[idx].get('label','')}")
            state["updated_at"] = now_ts()
        return

# ---- проклятья ----

def apply_curse_penalties(combat: Dict[str, Any]) -> None:
    p = combat.get("player", {})
    for c in list(combat.get("hand", [])):
        cdef = content.get_card_def(c["id"], upgraded=bool(c.get("up", False)))
        if not is_curse_card(cdef):
            continue
        eff = cdef.get("curse_effect", {})
        if eff.get("lose_hp"):
            dmg = int(eff.get("lose_hp", 0))
            p["hp"] = max(0, int(p.get("hp", 0)) - dmg)
            log(combat, f"{cdef['name']}: -{dmg} HP.")
        if eff.get("apply_status"):
            st = eff["apply_status"].get("status")
            stacks = int(eff["apply_status"].get("stacks", 0))
            status_add(p, st, stacks, combat=combat, source=cdef["name"])
            log(combat, f"{cdef['name']}: на тебя накладывается {content.STATUSES.get(st,{}).get('name', st)}.")
        if eff.get("next_draw_penalty"):
            combat["_curse_draw_penalty"] = int(combat.get("_curse_draw_penalty", 0)) + int(eff.get("next_draw_penalty", 0))

# ---- конец хода ----

def end_turn(state: Dict[str, Any]) -> None:
    run = state["run"]
    combat = run.get("combat")
    if not combat or combat.get("phase") != "player":
        return
    if combat.get("pending"):
        return

    rng = seeded_rng(run)
    combat["_rng"] = rng

    p = combat["player"]

    apply_curse_penalties(combat)

    # turn_end_player бафы
    eclipse = buff_count(p, "eclipse")
    if eclipse:
        for e in combat["enemies"]:
            if e["hp"] > 0:
                status_add(e, "poison", 2 * eclipse, combat=combat, source="Затмение")
                status_add(e, "burn", 2 * eclipse, combat=combat, source="Затмение")
        log(combat, f"Затмение: всем врагам +{2 * eclipse} яд/+{2 * eclipse} ожог.")
    eclipse_plus = buff_count(p, "eclipse_plus")
    if eclipse_plus:
        for e in combat["enemies"]:
            if e["hp"] > 0:
                status_add(e, "poison", 3 * eclipse_plus, combat=combat, source="Затмение+")
                status_add(e, "burn", 3 * eclipse_plus, combat=combat, source="Затмение+")
        log(combat, f"Затмение+: всем врагам +{3 * eclipse_plus} яд/+{3 * eclipse_plus} ожог.")
    if "phoenix_heart" in p.get("buffs", {}):
        stacks = int(p["buffs"].get("phoenix_heart", 1))
        for e in combat["enemies"]:
            if e["hp"] > 0:
                status_add(e, "burn", 1 * stacks, combat=combat, source="Сердце феникса")
        log(combat, "Сердце феникса: всем врагам +Ожог.")
    if "phoenix_heart_plus" in p.get("buffs", {}):
        stacks = int(p["buffs"].get("phoenix_heart_plus", 1))
        for e in combat["enemies"]:
            if e["hp"] > 0:
                status_add(e, "burn", 2 * stacks, combat=combat, source="Сердце феникса+")
        log(combat, "Сердце феникса+: всем врагам +Ожог.")
    venom = buff_count(p, "venom_rain")
    if venom:
        for e in combat["enemies"]:
            if e["hp"] > 0:
                status_add(e, "poison", 2 * venom, combat=combat, source="Ядовитая призма")
        log(combat, f"Ядовитая призма: всем врагам +{2 * venom} Яда.")
    venom_plus = buff_count(p, "venom_rain_plus")
    if venom_plus:
        for e in combat["enemies"]:
            if e["hp"] > 0:
                status_add(e, "poison", 3 * venom_plus, combat=combat, source="Ядовитая призма+")
        log(combat, f"Ядовитая призма+: всем врагам +{3 * venom_plus} Яда.")


    # burn tick на игроке (конец хода игрока)
    tick_burn(combat, p, owner="player")

    # сбрасываем не-зарядные
    new_hand = []
    for c in combat["hand"]:
        cdef = content.get_card_def(c["id"], upgraded=bool(c.get("up", False)))
        if cdef.get("stays_in_hand"):
            # заряд
            inc = int(cdef.get("charge_per_turn", 0))
            c["charge"] = int(c.get("charge", 0)) + inc
            new_hand.append(c)
        else:
            c["charge"] = 0
            combat["discard_pile"].append(c)
            trigger_on_discard(combat, c)
    combat["hand"] = new_hand

    # ход врагов
    combat["phase"] = "enemy"
    enemy_turn(state)
    if state.get("screen") in ("DEFEAT","REWARD","ACT_END","VICTORY"):
        return

    # новый ход игрока
    start_player_turn(state)

def start_player_turn(state: Dict[str, Any]) -> None:
    run = state["run"]
    combat = run.get("combat")

    while True:
        rng = seeded_rng(run)
        combat["_rng"] = rng

        combat["turn"] += 1

        p = combat["player"]
        # одноходовые отражения очищаются к новому ходу
        p.get("buffs", {}).pop("reflect_half_1turn", None)
        p.get("buffs", {}).pop("reflect_full_1turn", None)
        # блок обнуляется в начале своего хода (как в StS)
        p["block"] = 0

        # dot tick на игроке (яд)
        tick_poison(combat, p, owner="player")

        # если умер от яда
        if p["hp"] <= 0:
            lose_combat(state)
            return

        skipped = False
        # stun: пропуск хода
        if status_get(p, "stun") > 0:
            status_dec(p, "stun", 1)
            log(combat, "Игрок оглушён и пропускает ход.")
            skipped = True
        # freeze: шанс сорваться
        elif status_get(p, "freeze") > 0:
            if rng.random() < 0.30:
                status_dec(p, "freeze", 1)
                log(combat, "Игрок заморожен и срывает ход.")
                skipped = True

        if skipped:
            combat["phase"] = "enemy"
            state["updated_at"] = now_ts()
            enemy_turn(state)
            if state.get("screen") in ("DEFEAT", "REWARD", "ACT_END", "VICTORY"):
                return
            # после пропуска сразу пробуем начать следующий ход
            continue

        combat["phase"] = "player"

        # мана: refill
        p["mana"] = int(p.get("mana_max", 3))
        # battery: в начале хода +1 мана за стак
        battery_stacks = buff_count(p, "battery") + buff_count(p, "battery_plus")
        if battery_stacks:
            p["mana"] += battery_stacks
            log(combat, f"Батарея: +{battery_stacks} маны в начале хода.")

        # ward: блок в начале хода
        if "ward_small" in p.get("buffs", {}):
            p["block"] += 2
        if "ward_medium" in p.get("buffs", {}):
            p["block"] += 3
        regen_heal = 0
        regen_block = 0
        buffs = p.get("buffs", {})
        if "regen_small" in buffs:
            regen_heal += 2 * int(buffs.get("regen_small", 1))
        if "regen_medium" in buffs:
            regen_heal += 3 * int(buffs.get("regen_medium", 1))
        if "regen_guard" in buffs:
            regen_heal += 4 * int(buffs.get("regen_guard", 1))
            regen_block += 2 * int(buffs.get("regen_guard", 1))
        if "regen_guard_plus" in buffs:
            regen_heal += 5 * int(buffs.get("regen_guard_plus", 1))
            regen_block += 3 * int(buffs.get("regen_guard_plus", 1))
        if "phoenix_heart" in buffs:
            regen_heal += 6 * int(buffs.get("phoenix_heart", 1))
        if "phoenix_heart_plus" in buffs:
            regen_heal += 7 * int(buffs.get("phoenix_heart_plus", 1))
        if regen_heal > 0:
            before = int(p.get("hp", 0))
            p["hp"] = min(int(p["max_hp"]), before + regen_heal)
            healed = p["hp"] - before
            if healed > 0:
                log(combat, f"Регенерация: +{healed} HP.")
        if regen_block > 0:
            p["block"] += regen_block
            log(combat, f"Регенерация: +{regen_block} Блока.")
        ward_small = buff_count(p, "ward_small")
        ward_medium = buff_count(p, "ward_medium")
        if ward_small:
            p["block"] += 2 * ward_small
        if ward_medium:
            p["block"] += 3 * ward_medium

        # добор до 6 с учётом проклятий
        penalty = int(combat.pop("_curse_draw_penalty", 0))
        if penalty:
            log(combat, f"Проклятье ограничивает добор: -{penalty} карта(ы).")
        draw_n = max(0, 6 - len(combat["hand"]) - penalty)
        draw_to_hand(combat, n=draw_n, rng=rng)

        # если умер от яда
        if p["hp"] <= 0:
            lose_combat(state)
            return

        # выставим намерения у врагов, если где-то нет
        for e in combat["enemies"]:
            if e["hp"] > 0 and not e.get("intent"):
                choose_intent(e, rng)

        state["updated_at"] = now_ts()
        return

def enemy_turn(state: Dict[str, Any]) -> None:
    run = state["run"]
    combat = run.get("combat")
    rng = combat.get("_rng") or seeded_rng(run)

    p = combat["player"]
    enemies = combat["enemies"]

    # яд тикает на врагах в начале их хода
    for e in enemies:
        if e["hp"] > 0:
            tick_poison(combat, e, owner="enemy")

    # если все умерли от DoT — победа
    if all(e["hp"] <= 0 for e in enemies):
        win_combat(state)
        return

    # враги действуют
    for e in enemies:
        if e["hp"] <= 0:
            continue

        # stun
        if status_get(e, "stun") > 0:
            status_dec(e, "stun", 1)
            log(combat, f"{e['name']} оглушён и пропускает ход.")
            choose_intent(e, rng)
            continue

        # freeze: шанс пропустить
        if status_get(e, "freeze") > 0:
            if rng.random() < 0.30:
                status_dec(e, "freeze", 1)
                log(combat, f"{e['name']} заморожен и срывается.")
                choose_intent(e, rng)
                continue

        move = e.get("next_move")
        if not move:
            choose_intent(e, rng)
            move = e.get("next_move")

        e["last_move"] = move.get("id")

        mtype = move.get("type")
        if mtype == "attack":
            dmg = int(move.get("dmg", 0))
            deal_damage(combat, e, p, dmg, allow_crit=False, source=e["name"] + " — " + move["name"])
            # bleed triggers on attacker when it attacks
            tick_bleed_on_attack(combat, e)
        elif mtype == "attack_apply":
            dmg = int(move.get("dmg", 0))
            deal_damage(combat, e, p, dmg, allow_crit=False, source=e["name"] + " — " + move["name"])
            stacks = status_with_bonus(e, move.get("status"), int(move.get("stacks", 0)))
            status_add(p, move.get("status"), stacks, combat=combat, source=e["name"] + " — " + move["name"])
            tick_bleed_on_attack(combat, e)
        elif mtype == "apply":
            stacks = status_with_bonus(e, move.get("status"), int(move.get("stacks", 0)))
            status_add(p, move.get("status"), stacks, combat=combat, source=e["name"] + " — " + move["name"])
            log(combat, f"{e['name']}: {move['name']} -> {move.get('status')} +{stacks}.")
        elif mtype == "apply_all":
            stacks = status_with_bonus(e, move.get("status"), int(move.get("stacks", 0)))
            status_add(p, move.get("status"), stacks, combat=combat, source=e["name"] + " — " + move["name"])
            log(combat, f"{e['name']}: {move['name']} -> {move.get('status')} +{stacks}.")
        elif mtype == "block":
            e["block"] = int(e.get("block", 0)) + int(move.get("block", 0))
            log(combat, f"{e['name']}: {move['name']} (+{move.get('block',0)} Блока).")
        elif mtype == "heal":
            amt = int(move.get("amount", 0))
            e["hp"] = min(int(e["max_hp"]), int(e["hp"]) + amt)
            log(combat, f"{e['name']}: лечится на {amt}.")
        elif mtype == "phase_shift":
            target_phase = move.get("set_phase", "phase2")
            e.get("vars", {})["phase"] = target_phase
            if move.get("block"):
                e["block"] = int(e.get("block", 0)) + int(move.get("block", 0))
            if move.get("buff"):
                add_buff(e, move.get("buff"))
            if move.get("dmg_mult"):
                e.setdefault("vars", {})["dmg_mult"] = float(move.get("dmg_mult", 1.0))
            sb = move.get("status_boost") or {}
            if sb.get("status"):
                bonus_map = e.setdefault("vars", {}).setdefault("status_bonus", {})
                bonus_map[sb["status"]] = int(bonus_map.get(sb["status"], 0)) + int(sb.get("bonus", 0))
            log(combat, f"{e['name']} меняет фазу: {move.get('name')}.")
        elif mtype == "counter_prep":
            if move.get("block"):
                e["block"] = int(e.get("block", 0)) + int(move.get("block", 0))
            e.get("vars", {})["counter_ready"] = {
                "dmg": int(move.get("counter_dmg", 0)),
                "status": move.get("status"),
                "stacks": int(move.get("stacks", 0)),
                "name": move.get("name"),
            }
            log(combat, f"{e['name']} готовится ответить: {move.get('name')}.")
        elif mtype == "self_debuff":
            # для «турели»: следующий луч сильнее
            e["vars"]["overheat"] = 1
            log(combat, f"{e['name']}: {move['name']} (что-то трещит внутри).")
        else:
            log(combat, f"{e['name']} делает что-то странное.")

        # dead check на игроке
        if p["hp"] <= 0:
            lose_combat(state)
            return

        # если враг умер от шипов/дотов в своём действии — пропустим burn/intents
        if e["hp"] <= 0:
            if all(en["hp"] <= 0 for en in enemies):
                win_combat(state)
                return
            continue

        # burn tick на враге (конец его хода)
        tick_burn(combat, e, owner="enemy")

        if e["hp"] <= 0:
            if all(en["hp"] <= 0 for en in enemies):
                win_combat(state)
                return
            continue

        # intent на следующий ход
        choose_intent(e, rng)

        # проверка победы, если враг умер от дотов/реактивных эффектов
        if all(en["hp"] <= 0 for en in enemies):
            win_combat(state)
            return

    # блок врагов обнуляется после их хода (как «снятие блока» в начале их следующего, упрощение)
    for e in enemies:
        e["block"] = 0

    # игрок блок обнулим в начале следующего хода игрока (уже делаем в start_player_turn)
    combat["phase"] = "player"

def tick_poison(combat: Dict[str, Any], ent: Dict[str, Any], owner: str):
    s = status_get(ent, "poison")
    if s <= 0:
        return
    ent["hp"] = max(0, int(ent["hp"]) - s)
    log(combat, f"Яд: {s} урона.")
    # decay unless бафы запрещают уменьшение
    no_decay = (
        "poison_no_decay" in combat.get("player", {}).get("buffs", {})
        or "venom_rain" in combat.get("player", {}).get("buffs", {})
        or "venom_rain_plus" in combat.get("player", {}).get("buffs", {})
    )
    if owner == "enemy":
        if not no_decay:
            status_dec(ent, "poison", 1)
    else:
        if not no_decay:
            status_dec(ent, "poison", 1)

def tick_burn(combat: Dict[str, Any], ent: Dict[str, Any], owner: str):
    s = status_get(ent, "burn")
    if s <= 0:
        return
    # burn_boost: +1 dmg per stack
    dmg = s + buff_count(combat.get("player", {}), "burn_boost")
    ent["hp"] = max(0, int(ent["hp"]) - dmg)
    log(combat, f"Ожог: {dmg} урона.")
    # decay
    if owner == "enemy":
        # чуть медленнее при burn_boost: у врага не уменьшается на его ходу (иронично), а уменьшится в начале хода игрока? упростим: уменьшается всё равно, но медленнее
        if buff_count(combat.get("player", {}), "burn_boost"):
            if s >= 2:
                status_dec(ent, "burn", 0)  # не уменьшаем
            else:
                status_dec(ent, "burn", 1)
        else:
            status_dec(ent, "burn", 1)
    else:
        status_dec(ent, "burn", 1)

def tick_bleed_on_attack(combat: Dict[str, Any], ent: Dict[str, Any]):
    s = status_get(ent, "bleed")
    if s <= 0:
        return
    ent["hp"] = max(0, int(ent["hp"]) - s)
    log(combat, f"Кровоток: {s} урона атакующему.")
    status_dec(ent, "bleed", 1)

# ---- исход боя / награды ----

def win_combat(state: Dict[str, Any]) -> None:
    run = state["run"]
    combat = run.get("combat")
    if not combat:
        return
    combat["phase"] = "won"
    # перенесём hp обратно в забег
    run["hp"] = int(combat["player"]["hp"])
    # золото
    rng = seeded_rng(run)
    base = 18 + 6 * (act_for_floor(run["floor"]) - 1)
    gain = base + rng.randint(0, 10)
    run["gold"] += gain

    twist = run.get("room_twist")
    extra_cards = 1 if twist and twist.get("extra_reward") else 0
    if has_relic(run, "ECHO_CORE"):
        extra_cards += 1
    # награда: 3 карты (+twist + реликвии)
    reward_cards = generate_card_choices(run, rng, k=3 + extra_cards)
    if twist and twist.get("bonus_gold"):
        gain += int(twist.get("bonus_gold", 0))
    if has_relic(run, "RAT_POUCH"):
        bonus = 6
        gain += bonus
        state.setdefault("ui", {})
        state["ui"]["toast"] = f"Победа. +{gain} жетонов (включая +{bonus} от кошеля)."
    else:
        state["ui"]["toast"] = f"Победа. +{gain} жетонов."
    run["reward"] = {
        "type": "card_pick",
        "cards": reward_cards,
        "gold_gained": gain,
    }
    run["combat"] = None
    state["screen"] = "REWARD"
    state["updated_at"] = now_ts()

def lose_combat(state: Dict[str, Any]) -> None:
    run = state["run"]
    combat = run.get("combat")
    if combat:
        run["hp"] = 0
    # сохраним колоду в мету для наследования
    state["meta"]["last_deck"] = [{"id": ci["id"], "up": bool(ci.get("up", False))} for ci in run.get("deck", [])]
    state["meta"]["last_result"] = "defeat"
    state["run"] = None
    state["screen"] = "DEFEAT"
    state["ui"]["toast"] = "Поражение. Тюрьма смеётся."

def complete_floor_and_continue(state: Dict[str, Any]) -> None:
    run = state["run"]
    if not run:
        return
    run.pop("room_twist", None)
    # босс-этаж? тогда акт-эндвью
    floor = int(run["floor"])
    if is_boss_floor(floor):
        # акт-энд: продублировать и удалить (из 4 случайных)
        rng = seeded_rng(run)
        deck = run["deck"]
        # если колода маленькая — подстроимся
        picks_dup = rng.sample(deck, k=min(4, len(deck))) if deck else []
        picks_rem = rng.sample(deck, k=min(4, len(deck))) if deck else []
        run["act_end"] = {
            "dup_choices": [{"uid": c["uid"], "id": c["id"], "up": bool(c.get("up", False))} for c in picks_dup],
            "rem_choices": [{"uid": c["uid"], "id": c["id"], "up": bool(c.get("up", False))} for c in picks_rem],
            "dup_done": False,
            "rem_done": False,
        }
        state["screen"] = "ACT_END"
        state["ui"]["toast"] = "Конец акта: дубликат + удаление."
        return

    # иначе просто следующий этаж
    run["floor"] += 1
    run["act"] = act_for_floor(run["floor"])
    run["room_choices"] = generate_room_choices(run)
    state["screen"] = "MAP"
    state["updated_at"] = now_ts()

# ---- действия вне боя ----

def choose_room(state: Dict[str, Any], room_id: str) -> None:
    run = state["run"]
    if not run:
        return
    ensure_path_map(run)
    choice = None
    for c in run.get("room_choices", []):
        if c["id"] == room_id:
            choice = c
            break
    if not choice:
        return
    run.setdefault("visited_nodes", [])
    if room_id not in run["visited_nodes"]:
        run["visited_nodes"].append(room_id)
    run["current_node"] = room_id
    run["room"] = choice
    t = choice["type"]
    twist = maybe_roll_room_twist(state, t)
    if t in ("fight", "elite", "boss"):
        start_combat(state, t)
    elif t == "event":
        start_event(state)
    elif t == "shop":
        start_shop(state)
    elif t == "campfire":
        start_campfire(state)
    elif t == "chest":
        open_chest(state)

def pick_reward_card(state: Dict[str, Any], card_id: Optional[str]) -> None:
    run = state["run"]
    if not run or not run.get("reward"):
        return
    if card_id:
        add_card_to_deck(run, card_id, upgraded=False)
        state["ui"]["toast"] = f"Карта добавлена: {content.get_card_def(card_id)['name']}"
    else:
        state["ui"]["toast"] = "Награда пропущена."
    run["reward"] = None
    complete_floor_and_continue(state)

def start_event(state: Dict[str, Any]) -> None:
    run = state["run"]
    rng = seeded_rng(run)
    ev = rng.choice(content.EVENTS)
    run["event"] = deep(ev)
    state["screen"] = "EVENT"
    state["updated_at"] = now_ts()

def choose_event_option(state: Dict[str, Any], opt_id: str) -> None:
    run = state["run"]
    ev = run.get("event")
    if not ev:
        return
    opt = None
    for o in ev.get("options", []):
        if o["id"] == opt_id:
            opt = o
            break
    if not opt:
        return
    eff = opt.get("effect", {"op":"noop"})
    apply_event_effect(state, eff)
    # Если эффект требует дополнительного выбора — не закрываем событие и не двигаем этаж.
    if state.get("screen") == "EVENT_PICK":
        state["updated_at"] = now_ts()
        return
    run["event"] = None
    # событие считается комнатой — этаж завершён
    complete_floor_and_continue(state)

def apply_event_effect(state: Dict[str, Any], eff: Dict[str, Any]) -> None:
    run = state["run"]
    rng = seeded_rng(run)
    op = eff.get("op")
    if op == "noop":
        state["ui"]["toast"] = "Ничего не произошло. Подозрительно."
    elif op == "event_gain_card":
        rarity = eff.get("rarity")
        n = int(eff.get("n", 1))
        ids = content.sample_cards(rng, rarity=rarity, k=n)
        for cid in ids:
            add_card_to_deck(run, cid, False)
        state["ui"]["toast"] = f"+{n} карта(ы): {rarity}."
    elif op == "event_gain_relic":
        relic = random_relic(rng, run.get("relics", []))
        if relic:
            grant_relic(run, relic)
            state["ui"]["toast"] = f"Получена реликвия: {content.RELIC_INDEX[relic]['name']}"
        else:
            state["ui"]["toast"] = "Реликвии закончились."
    elif op == "event_gain_curse":
        cid = add_curse_to_deck(run, rng=rng)["id"]
        cdef = content.get_card_def(cid)
        state["ui"]["toast"] = f"Проклятье добавлено: {cdef['name']}"
    elif op == "event_remove_card":
        n = int(eff.get("n", 1))
        picks = rng.sample(run["deck"], k=min(4, len(run["deck"])))
        run["event_pick"] = {"type":"remove", "choices":[{"uid":c["uid"],"id":c["id"],"up":c.get("up",False)} for c in picks], "n": n}
        state["screen"] = "EVENT_PICK"
        state["ui"]["toast"] = "Выбери карту для удаления."
    elif op == "event_upgrade_card":
        picks = rng.sample(run["deck"], k=min(4, len(run["deck"])))
        run["event_pick"] = {"type":"upgrade", "choices":[{"uid":c["uid"],"id":c["id"],"up":c.get("up",False)} for c in picks],"n": 1}
        state["screen"] = "EVENT_PICK"
        state["ui"]["toast"] = "Выбери карту для улучшения."
    elif op == "lose_hp":
        amt = int(eff.get("amount", 0))
        run["hp"] = max(1, int(run["hp"]) - amt)
        state["ui"]["toast"] = f"-{amt} HP."
    elif op == "heal":
        amt = int(eff.get("amount", 0))
        before = int(run.get("hp", 0))
        run["hp"] = min(int(run["max_hp"]), before + amt)
        healed = run["hp"] - before
        state["ui"]["toast"] = f"Исцеление {healed} HP." if healed > 0 else "Ничего не изменилось."
    elif op == "gain_gold":
        delta = int(eff.get("amount", 0))
        before = int(run.get("gold", 0))
        run["gold"] = max(0, before + delta)
        state["ui"]["toast"] = f"Изменение золота: {delta:+d}."
    elif op == "gain_max_hp":
        amt = int(eff.get("amount", 0))
        run["max_hp"] = max(1, int(run.get("max_hp", 0)) + amt)
        run["hp"] = min(run["max_hp"], int(run.get("hp", 0)) + amt)
        state["ui"]["toast"] = f"Макс. HP увеличено на {amt}."
    elif op == "combo":
        for step in eff.get("steps", []):
            apply_event_effect(state, step)
    else:
        state["ui"]["toast"] = "Событие не сработало (пока)."

def resolve_event_pick(state: Dict[str, Any], uid: str) -> None:
    run = state["run"]
    pick = run.get("event_pick")
    if not pick:
        return
    t = pick.get("type")
    if t == "remove":
        run["deck"] = [c for c in run["deck"] if c["uid"] != uid]
        state["ui"]["toast"] = "Карта удалена."
    elif t == "upgrade":
        for c in run["deck"]:
            if c["uid"] == uid:
                c["up"] = True
                break
        state["ui"]["toast"] = "Карта улучшена (+)."
    run.pop("event_pick", None)
    run["event"] = None
    complete_floor_and_continue(state)

def start_shop(state: Dict[str, Any]) -> None:
    run = state["run"]
    rng = seeded_rng(run)
    twist = run.get("room_twist")
    discount = float(twist.get("shop_discount", 1.0)) if twist else 1.0
    extra_offer = 1 if twist and twist.get("shop_discount") else 0
    offers = []
    for _ in range(3 + extra_offer):
        cid = generate_card_choices(run, rng, k=1)[0]
        price = 40 if content.CARD_INDEX[cid]["rarity"]=="common" else 65 if content.CARD_INDEX[cid]["rarity"]=="uncommon" else 95 if content.CARD_INDEX[cid]["rarity"]=="rare" else 140
        price = max(10, int(round(price * discount)))
        offers.append({"card_id": cid, "price": price})
    run["shop"] = {
        "offers": offers,
        "services": [
            {"id":"remove", "label":"Удалить карту", "price": 60},
        ]
    }
    state["screen"] = "SHOP"
    state["updated_at"] = now_ts()

def shop_buy(state: Dict[str, Any], what: str, idx: Optional[int]=None) -> None:
    run = state["run"]
    shop = run.get("shop")
    if not shop:
        return
    gold = int(run.get("gold", 0))
    if what == "card":
        if idx is None: return
        offers = shop.get("offers", [])
        if not (0 <= idx < len(offers)): return
        item = offers[idx]
        if gold < item["price"]:
            state["ui"]["toast"] = "Не хватает жетонов."
            return
        run["gold"] -= item["price"]
        add_card_to_deck(run, item["card_id"], False)
        offers.pop(idx)
        state["ui"]["toast"] = "Куплено."
    elif what == "remove":
        svc = shop.get("services", [])[0]
        if gold < svc["price"]:
            state["ui"]["toast"] = "Не хватает жетонов."
            return
        # удалим из 4 случайных
        rng = seeded_rng(run)
        picks = rng.sample(run["deck"], k=min(4, len(run["deck"])))
        run["shop_remove"] = {"price": svc["price"], "choices":[{"uid":c["uid"],"id":c["id"],"up":c.get("up",False)} for c in picks]}
        state["screen"] = "SHOP_REMOVE"
        state["ui"]["toast"] = "Выбери карту для удаления (услуга)."

def shop_remove_confirm(state: Dict[str, Any], uid: str) -> None:
    run = state["run"]
    sr = run.get("shop_remove")
    if not sr: return
    price = int(sr.get("price", 0))
    if run["gold"] < price:
        state["ui"]["toast"] = "Не хватает жетонов."
        return
    run["gold"] -= price
    run["deck"] = [c for c in run["deck"] if c["uid"] != uid]
    run.pop("shop_remove", None)
    state["screen"] = "SHOP"
    state["ui"]["toast"] = "Удалено."

def leave_shop(state: Dict[str, Any]) -> None:
    run = state["run"]
    run["shop"] = None
    complete_floor_and_continue(state)

def start_campfire(state: Dict[str, Any]) -> None:
    state["screen"] = "CAMPFIRE"
    state["updated_at"] = now_ts()

def campfire_choice(state: Dict[str, Any], choice: str) -> None:
    run = state["run"]
    if choice == "rest":
        heal = 18
        run["hp"] = min(int(run["max_hp"]), int(run["hp"]) + heal)
        state["ui"]["toast"] = f"Отдых: +{heal} HP."
        complete_floor_and_continue(state)
    elif choice == "upgrade":
        rng = seeded_rng(run)
        picks = rng.sample(run["deck"], k=min(4, len(run["deck"])))
        run["campfire_up"] = {"choices":[{"uid":c["uid"],"id":c["id"],"up":c.get("up",False)} for c in picks]}
        state["screen"] = "CAMPFIRE_UP"
        state["ui"]["toast"] = "Выбери карту для улучшения."

def campfire_upgrade_confirm(state: Dict[str, Any], uid: str) -> None:
    run = state["run"]
    for c in run["deck"]:
        if c["uid"] == uid:
            c["up"] = True
            break
    run.pop("campfire_up", None)
    state["ui"]["toast"] = "Карта улучшена."
    complete_floor_and_continue(state)

def open_chest(state: Dict[str, Any]) -> None:
    run = state["run"]
    rng = seeded_rng(run)
    gold = 35 + rng.randint(0, 25)
    run["gold"] += gold
    relic = random_relic(rng, run.get("relics", []))
    relic_text = ""
    if relic:
        grant_relic(run, relic)
        relic_text = f" Реликвия: {content.RELIC_INDEX[relic]['name']}."
    # шанс на проклятье (гарантия, если есть компас)
    if has_relic(run, "WARDENS_COMPASS") or rng.random() < 0.4:
        curse_id = rng.choice(content.CURSES)["id"]
        add_curse_to_deck(run, curse_id, rng)
        relic_text += " Проклятье добавлено в колоду!"
    cid = generate_card_choices(run, rng, k=1)[0]
    add_card_to_deck(run, cid, False)
    state["ui"]["toast"] = f"Сундук: +{gold} жетонов, карта и находка.{relic_text}"
    complete_floor_and_continue(state)

# ---- акт-энд ----

def act_end_select(state: Dict[str, Any], kind: str, uid: str) -> None:
    run = state["run"]
    ae = run.get("act_end")
    if not ae:
        return
    if kind == "dup" and not ae.get("dup_done"):
        # найдём карту в колоде
        src = next((c for c in run["deck"] if c["uid"] == uid), None)
        if src:
            add_card_to_deck(run, src["id"], bool(src.get("up", False)))
            ae["dup_done"] = True
            state["ui"]["toast"] = "Карта продублирована."
    if kind == "rem" and not ae.get("rem_done"):
        run["deck"] = [c for c in run["deck"] if c["uid"] != uid]
        ae["rem_done"] = True
        state["ui"]["toast"] = "Карта удалена."
    # если оба сделаны — идём дальше
    if ae.get("dup_done") and ae.get("rem_done"):
        run["act_end"] = None
        # если был финальный босс — победа
        if int(run["floor"]) == 10:
            state["meta"]["last_deck"] = [{"id": ci["id"], "up": bool(ci.get("up", False))} for ci in run.get("deck", [])]
            state["meta"]["last_result"] = "victory"
            state["screen"] = "VICTORY"
            state["ui"]["toast"] = "Победа. Тюрьма сделала вид, что не удивлена."
        else:
            # следующий этаж
            run["floor"] += 1
            run["act"] = act_for_floor(run["floor"])
            run["room_choices"] = generate_room_choices(run)
            state["screen"] = "MAP"
    state["updated_at"] = now_ts()

# ---- победа и «бесконечность» ----

def continue_endless(state: Dict[str, Any]) -> None:
    run = state.get("run")
    if not run:
        # если забег уже завершён, начнём «петлю» с последней меты: новый забег с наследованием
        return
    run["loop"] = int(run.get("loop", 0)) + 1
    run["floor"] = 1
    run["act"] = 1
    # подлечим чуть-чуть, чтобы не было мгновенной смерти
    run["hp"] = min(int(run["max_hp"]), int(run["hp"]) + 20)
    run["visited_nodes"] = []
    run["current_node"] = None
    run["path_map"] = build_path_map(run)
    run["room_choices"] = generate_room_choices(run)
    state["screen"] = "MAP"
    state["ui"]["toast"] = f"Петля #{run['loop']}: этажи снова те же, но тьма глубже."
    state["updated_at"] = now_ts()

# ---- наследование (мета) ----

def start_inherit_if_possible(state: Dict[str, Any]) -> bool:
    """Если есть last_deck, предложить выбрать 3 карты (каждая из 5 случайных)."""
    last = state.get("meta", {}).get("last_deck", [])
    if not last:
        return False
    rng = random.Random(int(time.time()))
    picks = []
    for slot in range(3):
        options = rng.sample(last, k=min(5, len(last)))
        picks.append({"slot": slot, "options": options, "picked": None})
    state["run"] = None
    state["screen"] = "INHERIT"
    state["inherit"] = {"slots": picks}
    return True

def inherit_pick(state: Dict[str, Any], slot: int, idx: int) -> None:
    inh = state.get("inherit")
    if not inh: 
        return
    slots = inh.get("slots", [])
    if not (0 <= slot < len(slots)): 
        return
    options = slots[slot].get("options", [])
    if not (0 <= idx < len(options)):
        return
    slots[slot]["picked"] = options[idx]
    # если все выбраны — стартуем забег
    if all(s.get("picked") is not None for s in slots):
        keep = [s["picked"] for s in slots]
        state.pop("inherit", None)
        state["ui"]["toast"] = "Наследие выбрано. Добро пожаловать обратно."
        new_run(state, keep_cards=keep)

# ---- диспетчер действий ----

def dispatch(state: Dict[str, Any], action: Dict[str, Any]) -> None:
    typ = action.get("type")
    state.setdefault("ui", {}).setdefault("toast", "")
    state["ui"]["toast"] = ""

    if typ == "NEW_RUN":
        # если есть прошлый забег — сначала наследование
        if start_inherit_if_possible(state):
            state["ui"]["toast"] = "Выбери наследие (3 карты)."
            return
        new_run(state)
        return

    if typ == "CONTINUE":
        continue_run(state)
        return

    if typ == "INHERIT_PICK":
        inherit_pick(state, int(action.get("slot", 0)), int(action.get("idx", 0)))
        return

    if typ == "CHOOSE_ROOM":
        choose_room(state, action.get("room_id"))
        return

    if typ == "PLAY_CARD":
        play_card(state, action.get("uid"), action.get("target"))
        return

    if typ == "END_TURN":
        end_turn(state)
        return

    if typ == "RESOLVE_PENDING":
        resolve_pending(state, action.get("payload", {}))
        return

    if typ == "PICK_REWARD":
        pick_reward_card(state, action.get("card_id"))
        return

    if typ == "EVENT_OPT":
        choose_event_option(state, action.get("opt_id"))
        return

    if typ == "EVENT_PICK":
        resolve_event_pick(state, action.get("uid"))
        return

    if typ == "SHOP_BUY":
        shop_buy(state, action.get("what"), action.get("idx"))
        return

    if typ == "SHOP_REMOVE":
        shop_remove_confirm(state, action.get("uid"))
        return

    if typ == "SHOP_LEAVE":
        leave_shop(state)
        return

    if typ == "CAMPFIRE":
        campfire_choice(state, action.get("choice"))
        return

    if typ == "CAMPFIRE_UP":
        campfire_upgrade_confirm(state, action.get("uid"))
        return

    if typ == "ACT_END":
        act_end_select(state, action.get("kind"), action.get("uid"))
        return

    if typ == "CONTINUE_ENDLESS":
        continue_endless(state)
        return

    if typ == "SET_DIFFICULTY":
        state.setdefault("settings", {})["difficulty"] = int(action.get("difficulty", 1))
        state["ui"]["toast"] = "Сложность изменена."
        return


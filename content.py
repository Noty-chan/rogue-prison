# content.py
# Данные: карты, враги, события. Держим в одном месте, чтобы проект оставался компактным (<=10 файлов).

from __future__ import annotations
from typing import Dict, List, Any, Optional
import random

RARITIES = ["common", "uncommon", "rare", "legendary"]
CARD_TYPES = ["attack", "defense", "skill", "upgrade"]

# Вероятности выпадения в наградах/магазине (приблизительно, как в StS-стиле).
RARITY_WEIGHTS = {
    "common": 65,
    "uncommon": 25,
    "rare": 9,
    "legendary": 1,
}

CRIT_BASE_CHANCE = 0.15

def _c(
    cid: str,
    name: str,
    rarity: str,
    ctype: str,
    cost: int,
    target: str,
    desc: str,
    effects: List[dict],
    tags: Optional[List[str]] = None,
    exhaust: bool = False,
    stays_in_hand: bool = False,
    charge_per_turn: int = 0,
    desc_up: Optional[str] = None,
    cost_up: Optional[int] = None,
    effects_up: Optional[List[dict]] = None,
) -> Dict[str, Any]:
    return {
        "id": cid,
        "name": name,
        "rarity": rarity,
        "type": ctype,
        "cost": cost,
        "target": target,  # enemy/self/all_enemies/none/any
        "desc": desc,
        "effects": effects,
        "tags": tags or [],
        "exhaust": exhaust,
        # Зарядка: карта НЕ сбрасывается в конце хода и усиливается.
        "stays_in_hand": stays_in_hand,
        "charge_per_turn": charge_per_turn,
        "desc_up": desc_up,
        "cost_up": cost_up,
        "effects_up": effects_up,
    }

# --------------------------
# 60 карт: 24/18/12/6
# Минимум 12 билд-тегов:
# charge, poison, burn, bleed, control, stun, freeze, burst, discard, crit, block, mana, hex, heal
# --------------------------

CARDS: List[Dict[str, Any]] = []

# --- COMMON (24) ---
CARDS += [
    _c("ARCANE_JAB", "Арканный тычок", "common", "attack", 1, "enemy",
       "Нанеси 6 урона. (Крит 15%)",
       [{"op":"damage","amount":6}],
       tags=["burst"]),
    _c("RUNE_SLASH", "Рунический разрез", "common", "attack", 1, "enemy",
       "Нанеси 5 урона. Наложи 1 Кровоток.",
       [{"op":"damage","amount":5},{"op":"apply","status":"bleed","stacks":1,"to":"enemy"}],
       tags=["bleed"]),
    _c("SPARK_SHOT", "Искра", "common", "attack", 0, "enemy",
       "Нанеси 3 урона.",
       [{"op":"damage","amount":3}],
       tags=["burst"]),
    _c("SHACKLED_STRIKE", "Удар в кандалах", "common", "attack", 1, "enemy",
       "Нанеси 4 урона. Наложи 1 Слабость.",
       [{"op":"damage","amount":4},{"op":"apply","status":"weak","stacks":1,"to":"enemy"}],
       tags=["control"]),
    _c("PRISON_SHIV", "Тюремная заточка", "common", "attack", 1, "enemy",
       "Нанеси 6 урона. Если это был крит — возьми 1 карту.",
       [{"op":"damage","amount":6,"on_crit":[{"op":"draw","n":1}]}],
       tags=["crit","burst"]),
    _c("GUARD_SIGIL", "Сигил стражи", "common", "defense", 1, "self",
       "Получишь 6 Блока.",
       [{"op":"block","amount":6}],
       tags=["block"]),
    _c("STONE_SKIN", "Каменная кожа", "common", "defense", 1, "self",
       "Получишь 5 Блока. Получишь 1 Шип.",
       [{"op":"block","amount":5},{"op":"apply","status":"thorns","stacks":1,"to":"self"}],
       tags=["block"]),
    _c("SIDESTEP_GLYPH", "Глиф уклонения", "common", "defense", 0, "self",
       "Получишь 3 Блока.",
       [{"op":"block","amount":3}],
       tags=["block"]),
    _c("FOCUS", "Фокус", "common", "skill", 1, "none",
       "Возьми 2 карты, затем сбрось 1 карту на выбор.",
       [{"op":"draw","n":2},{"op":"discard_choose","n":1}],
       tags=["discard"]),
    _c("SOUL_SIP", "Глоток души", "common", "skill", 1, "self",
       "Исцелись на 3. Потрать 1 ману.",
       [{"op":"heal","amount":3}],
       tags=[]),
    _c("MANA_DRIP", "Капля маны", "common", "skill", 0, "self",
       "Получи +1 маны.",
       [{"op":"gain_mana","n":1}],
       tags=["mana"]),
    _c("CHAIN_PULL", "Рывок цепью", "common", "skill", 1, "enemy",
       "Наложи 2 Уязвимость.",
       [{"op":"apply","status":"vulnerable","stacks":2,"to":"enemy"}],
       tags=["control"]),
    _c("TOXIC_NEEDLE", "Токсичная игла", "common", "attack", 1, "enemy",
       "Нанеси 3 урона. Наложи 3 Яд.",
       [{"op":"damage","amount":3},{"op":"apply","status":"poison","stacks":3,"to":"enemy"}],
       tags=["poison"]),
    _c("ASH_FLICK", "Щелчок пеплом", "common", "skill", 1, "enemy",
       "Наложи 4 Ожог.",
       [{"op":"apply","status":"burn","stacks":4,"to":"enemy"}],
       tags=["burn"]),
    _c("SHACKLES", "Оковы", "common", "skill", 1, "enemy",
       "Наложи 2 Слабость.",
       [{"op":"apply","status":"weak","stacks":2,"to":"enemy"}],
       tags=["control"]),
    _c("COIL_OF_POWER", "Катушка силы", "common", "attack", 1, "enemy",
       "Нанеси 4 урона. Эта карта остаётся в руке и в конце хода получает +2 к урону.",
       [{"op":"damage","amount":{"base":4,"plus_charge":True}}],
       tags=["charge","burst"],
       stays_in_hand=True, charge_per_turn=2,
       desc_up="Нанеси 5 урона. Остаётся в руке и получает +3 к урону.",
       effects_up=[{"op":"damage","amount":{"base":5,"plus_charge":True}}],
       ),
    _c("SCAVENGE", "Сортировка мусора", "common", "skill", 1, "none",
       "Сбрось 1 карту. Получи +2 маны.",
       [{"op":"discard_choose","n":1},{"op":"gain_mana","n":2}],
       tags=["discard","mana"]),
    _c("TRASH_TO_TREASURE", "Мусор в золото", "common", "skill", 1, "none",
       "Сбрось 2 случайные карты. Возьми 2 карты.",
       [{"op":"discard_random","n":2},{"op":"draw","n":2}],
       tags=["discard"]),
_c("PRISON_TATTOO", "Тюремная татуировка", "common", "upgrade", 1, "self",
       "Изгнание. До конца боя: в начале твоего хода получай 2 Блока.",
       [{"op":"add_buff","buff":"ward_small"}],
       tags=["block"],
       exhaust=True,
       desc_up="Изгнание. До конца боя: в начале твоего хода получай 3 Блока.",
       effects_up=[{"op":"add_buff","buff":"ward_medium"}]),
    _c("SMOLDERING_BRAND", "Тлеющее клеймо", "common", "upgrade", 1, "self",
       "Изгнание. До конца боя: твои атаки накладывают 1 Ожог.",
       [{"op":"add_buff","buff":"burn_on_hit"}],
       tags=["burn"],
       exhaust=True,
       desc_up="Изгнание. До конца боя: твои атаки накладывают 2 Ожога.",
       effects_up=[{"op":"add_buff","buff":"burn_on_hit_2"}]),
    _c("PATCH_UP", "Наложить бинты", "common", "defense", 1, "self",
       "Получишь 6 Блока. Исцелись на 3.",
       [{"op":"block","amount":6},{"op":"heal","amount":3}],
       tags=["heal","block"],
       desc_up="Получишь 7 Блока. Исцелись на 4.",
       effects_up=[{"op":"block","amount":7},{"op":"heal","amount":4}]),
    _c("SOUL_STITCH", "Стежок души", "common", "skill", 1, "self",
       "Исцелись на 6. Возьми 1 карту.",
       [{"op":"heal","amount":6},{"op":"draw","n":1}],
       tags=["heal"],
       desc_up="Исцелись на 8. Возьми 1 карту.",
       effects_up=[{"op":"heal","amount":8},{"op":"draw","n":1}]),
    _c("REST_TONIC", "Тоник отдыха", "common", "skill", 0, "self",
       "Исцелись на 2. Получи +1 маны.",
       [{"op":"heal","amount":2},{"op":"gain_mana","n":1}],
       tags=["heal","mana"],
       desc_up="Исцелись на 3. Получи +1 маны.",
       effects_up=[{"op":"heal","amount":3},{"op":"gain_mana","n":1}]),
    _c("REGROWTH_SIGIL", "Сигил возрождения", "common", "upgrade", 1, "self",
       "Изгнание. До конца боя: в начале твоего хода исцеляйся на 2.",
       [{"op":"add_buff","buff":"regen_small"}],
       tags=["heal"],
       exhaust=True,
       desc_up="Изгнание. До конца боя: в начале твоего хода исцеляйся на 3.",
       effects_up=[{"op":"add_buff","buff":"regen_medium"}]),
]

# --- UNCOMMON (18) ---
CARDS += [
    _c("CHARGED_LANCE", "Заряжаемое копьё", "uncommon", "attack", 2, "enemy",
       "Нанеси 8 урона. Остаётся в руке и в конце хода получает +3 к урону.",
       [{"op":"damage","amount":{"base":8,"plus_charge":True}}],
       tags=["charge","burst"],
       stays_in_hand=True, charge_per_turn=3,
       desc_up="Нанеси 10 урона. Остаётся в руке и получает +4 к урону.",
       effects_up=[{"op":"damage","amount":{"base":10,"plus_charge":True}}],
       ),
    _c("BATTERY_WARD", "Батарейный щит", "uncommon", "defense", 1, "self",
       "Получишь 8 Блока. Если в руке есть заряжающаяся карта — получишь ещё 3 Блока.",
       [{"op":"block","amount":8},{"op":"if_hand_has_tag","tag":"charge","then":[{"op":"block","amount":3}]}],
       tags=["block","charge"],
       desc_up="Получишь 10 Блока. Если в руке есть заряжающаяся карта — получишь ещё 4 Блока.",
       effects_up=[{"op":"block","amount":10},{"op":"if_hand_has_tag","tag":"charge","then":[{"op":"block","amount":4}]}]),
    _c("POISON_MIST", "Ядовитый туман", "uncommon", "skill", 1, "all_enemies",
       "Наложи 2 Яда всем врагам.",
       [{"op":"apply","status":"poison","stacks":2,"to":"all_enemies"}],
       tags=["poison"],
       desc_up="Наложи 3 Яда всем врагам.",
       effects_up=[{"op":"apply","status":"poison","stacks":3,"to":"all_enemies"}]),
    _c("BURNING_CHAINS", "Горящие цепи", "uncommon", "attack", 1, "enemy",
       "Нанеси 4 урона. Наложи 3 Ожога и 1 Слабость.",
       [{"op":"damage","amount":4},{"op":"apply","status":"burn","stacks":3,"to":"enemy"},{"op":"apply","status":"weak","stacks":1,"to":"enemy"}],
       tags=["burn","control"]),
    _c("HEMORRHAGE", "Кровотечение", "uncommon", "attack", 1, "enemy",
       "Нанеси 5 урона. Наложи 4 Кровотока.",
       [{"op":"damage","amount":5},{"op":"apply","status":"bleed","stacks":4,"to":"enemy"}],
       tags=["bleed"],
       desc_up="Нанеси 7 урона. Наложи 5 Кровотока.",
       effects_up=[{"op":"damage","amount":7},{"op":"apply","status":"bleed","stacks":5,"to":"enemy"}]),
    _c("COLD_SNAP", "Холодный щелчок", "uncommon", "skill", 1, "enemy",
       "Наложи 2 Заморозки. (Заморозка: -25% урона и 30% шанс пропустить ход.)",
       [{"op":"apply","status":"freeze","stacks":2,"to":"enemy"}],
       tags=["freeze","control"],
       desc_up="Наложи 3 Заморозки.",
       effects_up=[{"op":"apply","status":"freeze","stacks":3,"to":"enemy"}]),
    _c("COUNTER_SIGIL", "Контр-сигил", "uncommon", "defense", 1, "self",
       "Получишь 6 Блока. Получишь 2 Шипа.",
       [{"op":"block","amount":6},{"op":"apply","status":"thorns","stacks":2,"to":"self"}],
       tags=["block"],
       desc_up="Получишь 7 Блока. Получишь 3 Шипа.",
       effects_up=[{"op":"block","amount":7},{"op":"apply","status":"thorns","stacks":3,"to":"self"}]),
    _c("CRIT_LESSON", "Урок критов", "uncommon", "upgrade", 1, "self",
       "Изгнание. До конца боя: +10% шанс крита.",
       [{"op":"add_buff","buff":"crit_plus_10"}],
       tags=["crit"],
       exhaust=True,
       desc_up="Изгнание. До конца боя: +15% шанс крита.",
       effects_up=[{"op":"add_buff","buff":"crit_plus_15"}]),
    _c("DETONATION_RUNE", "Руна детонации", "uncommon", "skill", 2, "all_enemies",
       "Нанеси 6 урона всем. Если у цели есть Яд/Ожог/Кровоток — +4 урона.",
       [{"op":"aoe_damage","amount":6,"bonus_if_has_any_status":["poison","burn","bleed"],"bonus":4}],
       tags=["burst","poison","burn","bleed"],
       desc_up="Нанеси 7 урона всем. Бонус +5.",
       effects_up=[{"op":"aoe_damage","amount":7,"bonus_if_has_any_status":["poison","burn","bleed"],"bonus":5}]),
    _c("DISCARD_ENGINE", "Двигатель сброса", "uncommon", "upgrade", 1, "self",
       "Изгнание. До конца боя: каждый раз, когда ты сбрасываешь карту, получай +1 маны.",
       [{"op":"add_buff","buff":"mana_on_discard"}],
       tags=["discard","mana"],
       exhaust=True,
       desc_up="Изгнание. До конца боя: сброс даёт +1 маны и 1 Блок.",
       effects_up=[{"op":"add_buff","buff":"mana_block_on_discard"}]),
    _c("RECYCLE", "Переработка", "uncommon", "skill", 0, "none",
       "Выбери 1 карту из сброса и возьми её в руку.",
       [{"op":"take_from_discard","n":1}],
       tags=["discard"]),
    _c("LOCKPICK", "Отмычка", "uncommon", "skill", 1, "none",
       "Возьми 2 карты. Следующую карту, которую ты разыграешь, верни в руку вместо сброса.",
       [{"op":"draw","n":2},{"op":"add_buff","buff":"bounce_next"}],
       tags=["control","discard"],
       desc_up="Возьми 3 карты. Эффект тот же.",
       effects_up=[{"op":"draw","n":3},{"op":"add_buff","buff":"bounce_next"}]),
    _c("MIRROR_SHARD", "Осколок зеркала", "uncommon", "skill", 1, "none",
       "Следующая сыгранная атака в этот ход повторяется на того же врага с 50% силы.",
       [{"op":"add_buff","buff":"echo_attack_half"}],
       tags=["burst"]),
    _c("BARGAIN_WARDEN", "Сделка с надзирателем", "uncommon", "skill", 1, "self",
       "Получи 2 Макс.Маны до конца боя. Потеряй 3 HP.",
       [{"op":"lose_hp","amount":3},{"op":"gain_max_mana","n":2,"duration":"combat"}],
       tags=["mana"]),
    _c("PANIC_ROLL", "Панический кувырок", "uncommon", "skill", 0, "none",
       "Получишь 2 Блока. Возьми 1 карту. Сбрось 1 карту.",
       [{"op":"block","amount":2},{"op":"draw","n":1},{"op":"discard_choose","n":1}],
       tags=["discard","block"]),
    _c("LIFESTEAL_SLASH", "Вампирский рез", "uncommon", "attack", 1, "enemy",
       "Нанеси 7 урона. Исцелись на 4.",
       [{"op":"damage","amount":7},{"op":"heal","amount":4}],
       tags=["heal","burst"],
       desc_up="Нанеси 9 урона. Исцелись на 5.",
       effects_up=[{"op":"damage","amount":9},{"op":"heal","amount":5}]),
    _c("VITAL_DRAW", "Тяга жизни", "uncommon", "skill", 1, "self",
       "Потеряй 2 HP. Исцелись на 3 за каждого живого врага.",
       [{"op":"lose_hp","amount":2},{"op":"heal_per_enemy","amount":3}],
       tags=["heal"],
       desc_up="Потеряй 2 HP. Исцелись на 4 за каждого врага.",
       effects_up=[{"op":"lose_hp","amount":2},{"op":"heal_per_enemy","amount":4}]),
    _c("BALM_BARRIER", "Бальзамный барьер", "uncommon", "defense", 1, "self",
       "Получишь 9 Блока. Исцелись на 3. Если в руке есть карта исцеления — получи ещё 3 Блока.",
       [{"op":"block","amount":9},{"op":"heal","amount":3},{"op":"if_hand_has_tag","tag":"heal","then":[{"op":"block","amount":3}]}],
       tags=["heal","block"],
       desc_up="11 Блока, исцеление 4, бонус Блок 4.",
       effects_up=[{"op":"block","amount":11},{"op":"heal","amount":4},{"op":"if_hand_has_tag","tag":"heal","then":[{"op":"block","amount":4}]}]),
]

# --- RARE (12) ---
CARDS += [
    _c("ARCANE_BATTERY", "Арканная батарея", "rare", "upgrade", 2, "self",
       "Изгнание. До конца боя: +2 Макс.Маны и в начале хода +1 мана.",
       [{"op":"add_buff","buff":"battery"}],
       tags=["mana"],
       exhaust=True,
       desc_up="Изгнание. До конца боя: +3 Макс.Маны и в начале хода +1 мана.",
       effects_up=[{"op":"add_buff","buff":"battery_plus"}]),
    _c("TIME_STOP", "Останов времени", "rare", "skill", 2, "all_enemies",
       "Оглуши всех врагов на 1 ход.",
       [{"op":"apply","status":"stun","stacks":1,"to":"all_enemies"}],
       tags=["stun","control"],
       desc_up="Оглуши всех врагов на 2 хода.",
       effects_up=[{"op":"apply","status":"stun","stacks":2,"to":"all_enemies"}]),
    _c("PLAGUE_DOCTRINE", "Доктрина чумы", "rare", "upgrade", 1, "self",
       "Изгнание. До конца боя: Яд больше не уменьшается в конце хода.",
       [{"op":"add_buff","buff":"poison_no_decay"}],
       tags=["poison"],
       exhaust=True),
    _c("INFERNO_CONTRACT", "Адский контракт", "rare", "upgrade", 1, "self",
       "Изгнание. До конца боя: Ожог наносит +1 урона за стак и не уменьшается в ход врага.",
       [{"op":"add_buff","buff":"burn_boost"}],
       tags=["burn"],
       exhaust=True),
    _c("BLOODLETTING", "Кровопускание", "rare", "skill", 1, "all_enemies",
       "Потеряй 5 HP. Наложи 6 Кровотока всем врагам. Исцелись на 2 за каждого врага.",
       [{"op":"lose_hp","amount":5},{"op":"apply","status":"bleed","stacks":6,"to":"all_enemies"},{"op":"heal_per_enemy","amount":2}],
       tags=["bleed"],
       desc_up="Потеряй 4 HP. Наложи 7 Кровотока. Исцеление 2/враг.",
       effects_up=[{"op":"lose_hp","amount":4},{"op":"apply","status":"bleed","stacks":7,"to":"all_enemies"},{"op":"heal_per_enemy","amount":2}]),
    _c("EXECUTION_BEAM", "Луч казни", "rare", "attack", 2, "enemy",
       "Нанеси 12 урона. Если цель ниже 50% HP — нанеси ещё 12.",
       [{"op":"damage","amount":12},{"op":"if_enemy_hp_below","pct":0.5,"then":[{"op":"damage","amount":12,"no_crit":True}]}],
       tags=["burst","execute"],
       desc_up="База 14, бонус 14.",
       effects_up=[{"op":"damage","amount":14},{"op":"if_enemy_hp_below","pct":0.5,"then":[{"op":"damage","amount":14,"no_crit":True}]}]),
    _c("GRAVEYARD_SHIFT", "Ночная смена", "rare", "upgrade", 1, "self",
       "Изгнание. До конца боя: при каждом сбросе — возьми 1 карту.",
       [{"op":"add_buff","buff":"draw_on_discard"}],
       tags=["discard"],
       exhaust=True,
       desc_up="…и получай 1 Блок при сбросе.",
       effects_up=[{"op":"add_buff","buff":"draw_block_on_discard"}]),
    _c("BLACKOUT", "Блэкаут", "rare", "skill", 1, "all_enemies",
       "Наложи 2 Слабость и 2 Уязвимость всем врагам. Получи +1 маны.",
       [{"op":"apply","status":"weak","stacks":2,"to":"all_enemies"},{"op":"apply","status":"vulnerable","stacks":2,"to":"all_enemies"},{"op":"gain_mana","n":1}],
       tags=["control","mana"],
       desc_up="Наложи 3/3. Мана +1.",
       effects_up=[{"op":"apply","status":"weak","stacks":3,"to":"all_enemies"},{"op":"apply","status":"vulnerable","stacks":3,"to":"all_enemies"},{"op":"gain_mana","n":1}]),
    _c("WARD_OF_MIRRORS", "Зеркальный барьер", "rare", "defense", 2, "self",
       "Получишь 15 Блока. До конца хода: 50% получаемого урона отражается.",
       [{"op":"block","amount":15},{"op":"add_buff","buff":"reflect_half_1turn"}],
       tags=["block"]),
    _c("CHAIN_REACTION", "Цепная реакция", "rare", "skill", 2, "enemy",
       "Взорви эффекты: нанеси урон равный (Яд + Ожог + Кровоток) и сними их.",
       [{"op":"dot_detach_explode","statuses":["poison","burn","bleed"]}],
       tags=["burst","poison","burn","bleed"],
       desc_up="То же, но урон +25%.",
       effects_up=[{"op":"dot_detach_explode","statuses":["poison","burn","bleed"],"mult":1.25}]),
    _c("SANCTUARY_RUNE", "Священный символ", "rare", "upgrade", 2, "self",
       "Изгнание. До конца боя: в начале хода исцеляйся на 4 и получай 2 Блока.",
       [{"op":"add_buff","buff":"regen_guard"}],
       tags=["heal","block"],
       exhaust=True,
       desc_up="Изгнание. Исцеляйся на 5 и получай 3 Блока в начале хода.",
       effects_up=[{"op":"add_buff","buff":"regen_guard_plus"}]),
    _c("SECOND_WIND", "Второе дыхание", "rare", "skill", 1, "self",
       "Исцелись на 10. Возьми 2 карты, затем сбрось 1 карту.",
       [{"op":"heal","amount":10},{"op":"draw","n":2},{"op":"discard_choose","n":1}],
       tags=["heal","discard"],
       desc_up="Исцелись на 12. Возьми 3 карты, затем сбрось 1 карту.",
       effects_up=[{"op":"heal","amount":12},{"op":"draw","n":3},{"op":"discard_choose","n":1}]),
]

# --- LEGENDARY (6) ---
CARDS += [
    _c("CRIT_OF_DAMNED", "Крит проклятых", "legendary", "upgrade", 1, "self",
       "Изгнание. До конца боя: +25% шанс крита. Криты наносят x3 урона.",
       [{"op":"add_buff","buff":"crit_godmode"}],
       tags=["crit"],
       exhaust=True),
    _c("PRISON_ECLIPSE", "Тюремное затмение", "legendary", "upgrade", 2, "self",
       "Изгнание. До конца боя: в конце твоего хода накладывай 2 Яда и 2 Ожога всем врагам.",
       [{"op":"add_buff","buff":"eclipse"}],
       tags=["poison","burn"],
       exhaust=True,
       desc_up="Накладывай 3 и 3.",
       effects_up=[{"op":"add_buff","buff":"eclipse_plus"}]),
    _c("INFINITE_LOOP", "Бесконечная петля", "legendary", "skill", 1, "none",
       "Возьми 1 карту из сброса в руку. Снизь её стоимость на 1 (минимум 0) до конца боя.",
       [{"op":"take_from_discard","n":1,"reduce_cost":1}],
       tags=["discard","mana"],
       desc_up="Возьми 2 карты из сброса, обе -1 к стоимости.",
       effects_up=[{"op":"take_from_discard","n":2,"reduce_cost":1}]),
    _c("WARDENS_KEY", "Ключ надзирателя", "legendary", "skill", 0, "none",
       "Выбери одно: (1) +2 маны, (2) возьми 3 карты, (3) получи 10 Блока.",
       [{"op":"choose_one","options":[
           {"label":"+2 маны","effects":[{"op":"gain_mana","n":2}]},
           {"label":"Возьми 3","effects":[{"op":"draw","n":3}]},
           {"label":"10 Блока","effects":[{"op":"block","amount":10}]},
       ]}],
       tags=["mana","block"]),
    _c("LAST_FLOOR", "Последний этаж", "legendary", "attack", 3, "all_enemies",
       "Нанеси 30 урона всем врагам. Изгнание.",
       [{"op":"aoe_damage","amount":30}],
       tags=["burst"],
       exhaust=True,
       desc_up="Нанеси 35 урона всем. Изгнание.",
       effects_up=[{"op":"aoe_damage","amount":35}]),
    _c("PHOENIX_HEART", "Сердце феникса", "legendary", "upgrade", 2, "self",
       "Изгнание. До конца боя: в начале хода исцеляйся на 6 и накладывай 1 Ожог всем врагам.",
       [{"op":"add_buff","buff":"phoenix_heart"}],
       tags=["heal","burn"],
       exhaust=True,
       desc_up="В начале хода исцеление 7 и 2 Ожога всем врагам.",
       effects_up=[{"op":"add_buff","buff":"phoenix_heart_plus"}]),
]

# Проверка количества по редкостям (на этапе импорта).
_counts = {r:0 for r in RARITIES}
for c in CARDS:
    _counts[c["rarity"]] += 1
assert _counts["common"] == 24, f"common should be 24, got {_counts['common']}"
assert _counts["uncommon"] == 18, f"uncommon should be 18, got {_counts['uncommon']}"
assert _counts["rare"] == 12, f"rare should be 12, got {_counts['rare']}"
assert _counts["legendary"] == 6, f"legendary should be 6, got {_counts['legendary']}"

CARD_INDEX: Dict[str, Dict[str, Any]] = {c["id"]: c for c in CARDS}

def get_card_def(card_id: str, upgraded: bool=False) -> Dict[str, Any]:
    """Вернёт копию описания карты с учётом апгрейда (+)."""
    base = dict(CARD_INDEX[card_id])
    if upgraded:
        if base.get("desc_up"): base["desc"] = base["desc_up"]
        if base.get("cost_up") is not None: base["cost"] = base["cost_up"]
        if base.get("effects_up"): base["effects"] = base["effects_up"]
        base["upgraded"] = True
    else:
        base["upgraded"] = False
    # Не протаскиваем альтернативы дальше — фронту они не нужны.
    base.pop("desc_up", None)
    base.pop("cost_up", None)
    base.pop("effects_up", None)
    return base

# --------------------------
# Бафы (для upgrade-карт) — просто id -> описание и «хуки»
# --------------------------

BUFFS: Dict[str, Dict[str, Any]] = {
    "ward_small": {"name":"Тату: мини-щит", "desc":"В начале твоего хода +2 Блока.", "hooks":["turn_start_player"]},
    "ward_medium": {"name":"Тату: щит", "desc":"В начале твоего хода +3 Блока.", "hooks":["turn_start_player"]},
    "regen_small": {"name":"Возрождение", "desc":"В начале твоего хода лечишься на 2.", "hooks":["turn_start_player"]},
    "regen_medium": {"name":"Возрождение+", "desc":"В начале твоего хода лечишься на 3.", "hooks":["turn_start_player"]},
    "burn_on_hit": {"name":"Тлеющее клеймо", "desc":"Твои атаки накладывают 1 Ожог.", "hooks":["on_attack_hit"]},
    "burn_on_hit_2": {"name":"Тлеющее клеймо+", "desc":"Твои атаки накладывают 2 Ожога.", "hooks":["on_attack_hit"]},
    "crit_plus_10": {"name":"Школа критов", "desc":"+10% шанс крита.", "hooks":[]},
    "crit_plus_15": {"name":"Школа критов+", "desc":"+15% шанс крита.", "hooks":[]},
    "mana_on_discard": {"name":"Двигатель сброса", "desc":"Сброс: +1 мана.", "hooks":["on_discard"]},
    "mana_block_on_discard": {"name":"Двигатель сброса+", "desc":"Сброс: +1 мана и +1 Блок.", "hooks":["on_discard"]},
    "bounce_next": {"name":"Отмычка", "desc":"Следующая сыгранная карта возвращается в руку.", "hooks":["on_play_card"]},
    "echo_attack_half": {"name":"Осколок зеркала", "desc":"Следующая атака повторится на 50%.", "hooks":["on_attack_hit"]},
    "battery": {"name":"Арканная батарея", "desc":"+2 макс. маны. В начале хода +1 мана.", "hooks":["turn_start_player"]},
    "battery_plus": {"name":"Арканная батарея+", "desc":"+3 макс. маны. В начале хода +1 мана.", "hooks":["turn_start_player"]},
    "poison_no_decay": {"name":"Доктрина чумы", "desc":"Яд не уменьшается.", "hooks":["dot_tick_poison"]},
    "burn_boost": {"name":"Адский контракт", "desc":"Ожог сильнее и «держится» дольше.", "hooks":["dot_tick_burn"]},
    "draw_on_discard": {"name":"Ночная смена", "desc":"Сброс: возьми 1 карту.", "hooks":["on_discard"]},
    "draw_block_on_discard": {"name":"Ночная смена+", "desc":"Сброс: возьми 1 и +1 Блок.", "hooks":["on_discard"]},
    "reflect_half_1turn": {"name":"Зеркальный барьер", "desc":"До конца хода: отражаешь 50% урона.", "hooks":["on_take_damage"]},
    "crit_godmode": {"name":"Крит проклятых", "desc":"+25% крит, крит x3.", "hooks":[]},
    "eclipse": {"name":"Тюремное затмение", "desc":"В конце твоего хода: всем врагам +2 яд, +2 ожог.", "hooks":["turn_end_player"]},
    "eclipse_plus": {"name":"Тюремное затмение+", "desc":"В конце твоего хода: всем врагам +3 яд, +3 ожог.", "hooks":["turn_end_player"]},
    "regen_guard": {"name":"Священный символ", "desc":"В начале хода: лечишься на 4 и получаешь 2 Блока.", "hooks":["turn_start_player"]},
    "regen_guard_plus": {"name":"Священный символ+", "desc":"В начале хода: лечишься на 5 и получаешь 3 Блока.", "hooks":["turn_start_player"]},
    "phoenix_heart": {"name":"Сердце феникса", "desc":"Начало хода: лечишься на 6 и накладываешь 1 Ожог всем врагам.", "hooks":["turn_start_player","turn_end_player"]},
    "phoenix_heart_plus": {"name":"Сердце феникса+", "desc":"Начало хода: лечишься на 7 и накладываешь 2 Ожога всем врагам.", "hooks":["turn_start_player","turn_end_player"]},
}

# --------------------------
# Статусы
# --------------------------
STATUSES: Dict[str, Dict[str, Any]] = {
    "poison": {"name":"Яд", "desc":"В начале хода получаешь урон = стаки. Обычно уменьшается на 1."},
    "burn": {"name":"Ожог", "desc":"В конце хода получаешь урон = стаки. Обычно уменьшается на 1."},
    "bleed": {"name":"Кровоток", "desc":"Каждый раз, когда атакует, получает урон = стаки (и уменьшается на 1)."},
    "weak": {"name":"Слабость", "desc":"Наносит на 25% меньше урона."},
    "vulnerable": {"name":"Уязвимость", "desc":"Получает на 25% больше урона."},
    "stun": {"name":"Оглушение", "desc":"Пропускает ход."},
    "freeze": {"name":"Заморозка", "desc":"-25% урона и шанс пропустить ход."},
    "thorns": {"name":"Шипы", "desc":"Когда тебя бьют, отражаешь урон = стаки."},
}

# --------------------------
# Враги
# --------------------------
def _enemy(eid: str, name: str, max_hp: int, moves: List[dict], tags: Optional[List[str]]=None) -> Dict[str, Any]:
    return {"id": eid, "name": name, "max_hp": max_hp, "moves": moves, "tags": tags or []}

ENEMIES: List[Dict[str, Any]] = []

# Обычные — акт 1–2
ENEMIES += [
    _enemy("RAT_MAGE", "Крысомаг", 28, [
        {"id":"BITE","name":"Укус", "type":"attack", "dmg":6, "w":3},
        {"id":"SPIT","name":"Ядовитый плевок", "type":"attack_apply", "dmg":4, "status":"poison", "stacks":2, "w":2},
        {"id":"SKITTER","name":"Суета", "type":"block", "block":6, "w":1},
    ], tags=["poison"]),
    _enemy("CHAIN_GUARD", "Цепной страж", 34, [
        {"id":"SMASH","name":"Удар цепью", "type":"attack", "dmg":8, "w":3},
        {"id":"TAUNT","name":"Насмешка", "type":"apply", "status":"weak", "stacks":2, "w":2},
        {"id":"PLATE","name":"Пластина", "type":"block", "block":8, "w":1},
    ], tags=["control"]),
    _enemy("EMBER_IMP", "Угольно-имп", 24, [
        {"id":"FIREBOLT","name":"Огненный болт", "type":"attack_apply", "dmg":5, "status":"burn", "stacks":2, "w":3},
        {"id":"CACKLE","name":"Хохот", "type":"apply", "status":"vulnerable", "stacks":1, "w":1},
        {"id":"SMOKE","name":"Дымка", "type":"block", "block":5, "w":1},
    ], tags=["burn"]),
    _enemy("SKELETON_CLERK", "Скелет-делопроизводитель", 30, [
        {"id":"STAMP","name":"Печать", "type":"attack", "dmg":7, "w":3},
        {"id":"PAPER_CUT","name":"Бумажный порез", "type":"attack_apply", "dmg":3, "status":"bleed", "stacks":2, "w":2},
        {"id":"AUDIT","name":"Проверка", "type":"apply", "status":"weak", "stacks":1, "w":1},
    ], tags=["bleed"]),
    _enemy("ICE_WRAITH", "Ледяной призрак", 26, [
        {"id":"CHILL","name":"Холод", "type":"apply", "status":"freeze", "stacks":2, "w":3},
        {"id":"SLASH","name":"Ледяной рез", "type":"attack", "dmg":6, "w":2},
        {"id":"FADE","name":"Истаять", "type":"block", "block":7, "w":1},
    ], tags=["freeze"]),
    _enemy("HEX_LAWYER", "Адвокат проклятий", 32, [
        {"id":"OBJECTION","name":"Возражение!", "type":"attack", "dmg":6, "w":2},
        {"id":"CLAUSE","name":"Пункт договора", "type":"apply", "status":"vulnerable", "stacks":2, "w":2},
        {"id":"FINE","name":"Штраф", "type":"attack", "dmg":9, "w":1},
    ], tags=["control"]),
    _enemy("MANA_LEECH", "Манопиявка", 26, [
        {"id":"SIP","name":"Соснуть силы", "type":"attack", "dmg":5, "w":3},
        {"id":"DRAIN","name":"Манослив", "type":"apply", "status":"weak", "stacks":2, "w":2},
        {"id":"FUMES","name":"Тюремные испарения", "type":"apply_all", "status":"poison", "stacks":1, "w":1},
    ], tags=["mana","poison"]),
    _enemy("FROST_WARDEN", "Стужный надзиратель", 31, [
        {"id":"ICECHAIN","name":"Ледяные цепи", "type":"attack_apply", "dmg":6, "status":"freeze", "stacks":2, "w":3},
        {"id":"SHIELD","name":"Защитный купол", "type":"block", "block":9, "w":2},
        {"id":"GLARE","name":"Холодный взгляд", "type":"apply", "status":"vulnerable", "stacks":1, "w":1},
    ], tags=["freeze","control"]),
    _enemy("BLOOD_BUTCHER", "Кровавый палач", 33, [
        {"id":"HACK","name":"Расколоть", "type":"attack", "dmg":9, "w":3},
        {"id":"BLEEDING","name":"Капать на пол", "type":"attack_apply", "dmg":5, "status":"bleed", "stacks":3, "w":2},
        {"id":"GUARD","name":"Щиток", "type":"block", "block":7, "w":1},
    ], tags=["bleed","burst"]),
]

# Элиты — акт 2–3
ELITES: List[Dict[str, Any]] = [
    _enemy("WARDEN_HOUND", "Пёс надзирателя", 52, [
        {"id":"MAUL","name":"Растерзать", "type":"attack", "dmg":12, "w":3},
        {"id":"SNARL","name":"Рык", "type":"apply", "status":"weak", "stacks":2, "w":2},
        {"id":"RUSH","name":"Рывок", "type":"attack_apply", "dmg":9, "status":"bleed", "stacks":3, "w":2},
    ], tags=["bleed"]),
    _enemy("ARCANE_TURRET", "Арканная турель", 48, [
        {"id":"BEAM","name":"Луч", "type":"attack", "dmg":14, "w":3},
        {"id":"OVERHEAT","name":"Перегрев", "type":"self_debuff", "desc":"Турель теряет блок, но усиливает следующий луч", "w":1},
        {"id":"BARRIER","name":"Барьер", "type":"block", "block":12, "w":2},
    ], tags=["burst"]),
    _enemy("PLAGUE_SISTER", "Сестра чумы", 46, [
        {"id":"INCANT","name":"Заклятие", "type":"attack_apply", "dmg":7, "status":"poison", "stacks":4, "w":3},
        {"id":"MIST","name":"Туман", "type":"apply_all", "status":"poison", "stacks":2, "w":2},
        {"id":"PRAY","name":"Молитва", "type":"heal", "amount":6, "w":1},
    ], tags=["poison"]),
    _enemy("EMBER_KNIGHT", "Рыцарь угля", 54, [
        {"id":"CLEAVE","name":"Клинок жара", "type":"attack_apply", "dmg":10, "status":"burn", "stacks":3, "w":3},
        {"id":"ARMOR","name":"Латы", "type":"block", "block":14, "w":2},
        {"id":"SCOURGE","name":"Кара", "type":"attack", "dmg":16, "w":1},
    ], tags=["burn"]),
]

# Боссы — конец каждого акта
BOSSES: List[Dict[str, Any]] = [
    _enemy("BOSS_INQUISITOR", "Инквизитор бухгалтерии", 90, [
        {"id":"AUDIT_STRIKE","name":"Акт сверки", "type":"attack", "dmg":14, "w":3},
        {"id":"CONFISCATE","name":"Конфискация", "type":"apply", "status":"weak", "stacks":2, "w":2},
        {"id":"FEE","name":"Пошлина", "type":"attack_apply", "dmg":10, "status":"vulnerable", "stacks":2, "w":2},
        {"id":"FORTIFY","name":"Фортификация", "type":"block", "block":18, "w":1},
    ], tags=["control"]),
    _enemy("BOSS_WARDEN", "Надзиратель-архимаг", 105, [
        {"id":"ARCANE_BURST","name":"Арканный выброс", "type":"attack", "dmg":18, "w":3},
        {"id":"CHAINS","name":"Цепи власти", "type":"apply", "status":"stun", "stacks":1, "w":1},
        {"id":"RUNE_CAGE","name":"Руническая клетка", "type":"attack_apply", "dmg":12, "status":"freeze", "stacks":2, "w":2},
        {"id":"BARRIER","name":"Барьеры", "type":"block", "block":22, "w":2},
    ], tags=["stun","freeze"]),
    _enemy("BOSS_VOID_JUDGE", "Судья Пустоты", 125, [
        {"id":"VERDICT","name":"Приговор", "type":"attack", "dmg":22, "w":3},
        {"id":"SILENCE","name":"Безмолвие", "type":"apply", "status":"weak", "stacks":3, "w":2},
        {"id":"CORRUPT","name":"Порча", "type":"attack_apply", "dmg":14, "status":"poison", "stacks":5, "w":2},
        {"id":"FLARE","name":"Вспышка", "type":"attack_apply", "dmg":14, "status":"burn", "stacks":5, "w":2},
    ], tags=["poison","burn"]),
]

# --------------------------
# События (акт 1–3, мрак + ирония)
# --------------------------
EVENTS: List[Dict[str, Any]] = [
    {
        "id": "EVENT_SHOWER",
        "name": "Душевая камера",
        "desc": "Пахнет чистотой и подозрением. На полу — мыло, на стене — руны.",
        "options": [
            {"id":"SOAP", "label":"Взять мыло (удалить 1 карту)", "effect":{"op":"event_remove_card","n":1}},
            {"id":"RUNES", "label":"Слизать руну (получить случайную uncommon карту)", "effect":{"op":"event_gain_card","rarity":"uncommon","n":1}},
            {"id":"LEAVE", "label":"Уйти, пока цел(а)", "effect":{"op":"noop"}},
        ],
    },
    {
        "id": "EVENT_LIBRARY",
        "name": "Библиотека приговоров",
        "desc": "Каждая полка — чужая судьба. Каждая судьба — с пометкой «вернуть в срок».",
        "options": [
            {"id":"READ", "label":"Прочитать вслух (улучшить 1 карту)", "effect":{"op":"event_upgrade_card","n":1}},
            {"id":"STEAL", "label":"Украсть том (получить rare карту, но -6 HP)", "effect":{"op":"combo","steps":[{"op":"lose_hp","amount":6},{"op":"event_gain_card","rarity":"rare","n":1}]}},
            {"id":"LEAVE", "label":"Сделать вид, что ты тут не был(а)", "effect":{"op":"noop"}},
        ],
    },
    {
        "id": "EVENT_SCRAP",
        "name": "Склад конфиската",
        "desc": "Тут лежит всё, что «случайно» пропало у предыдущих счастливчиков.",
        "options": [
            {"id":"DIG", "label":"Порыться (получить 2 common карты)", "effect":{"op":"event_gain_card","rarity":"common","n":2}},
            {"id":"BURN", "label":"Сжечь улики (удалить 2 карты)", "effect":{"op":"event_remove_card","n":2}},
            {"id":"LEAVE", "label":"Уйти", "effect":{"op":"noop"}},
        ],
    },
]

# --------------------------
# Вспомогательное
# --------------------------
def weighted_choice(rng: random.Random, items: List[dict], weight_key: str="w") -> dict:
    total = sum(max(0, it.get(weight_key, 1)) for it in items)
    r = rng.uniform(0, total) if total > 0 else 0
    acc = 0.0
    for it in items:
        acc += max(0, it.get(weight_key, 1))
        if r <= acc:
            return it
    return items[-1]

def sample_cards(rng: random.Random, rarity: Optional[str]=None, k: int=1) -> List[str]:
    pool = [c for c in CARDS if (rarity is None or c["rarity"] == rarity)]
    return [rng.choice(pool)["id"] for _ in range(k)] if pool else []

def random_card_reward(rng: random.Random, k: int=3) -> List[str]:
    # В награде — смешанные редкости с весами
    ids: List[str] = []
    for _ in range(k):
        r = weighted_choice(rng, [{"r":rr,"w":RARITY_WEIGHTS[rr]} for rr in RARITIES], "w")["r"]
        ids.append(rng.choice([c for c in CARDS if c["rarity"] == r])["id"])
    return ids


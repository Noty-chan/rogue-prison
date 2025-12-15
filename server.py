# server.py
# Лёгкий локальный сервер (Flask): отдаёт фронт и принимает действия игрока.
# Запуск: python server.py  (или flask --app server run)

from __future__ import annotations
from typing import Dict, Any, Optional
import os, json, tempfile

from flask import Flask, request, send_from_directory, jsonify

import game
import content

APP_DIR = os.path.dirname(os.path.abspath(__file__))
SAVE_DIR = os.path.join(APP_DIR, "saves")
os.makedirs(SAVE_DIR, exist_ok=True)

app = Flask(__name__, static_folder="static", static_url_path="/static")

def save_path(sid: str) -> str:
    safe = "".join(ch for ch in sid if ch.isalnum() or ch in "_-")
    return os.path.join(SAVE_DIR, f"{safe}.json")

def load_state(sid: str) -> Dict[str, Any]:
    p = save_path(sid)
    was_corrupt = False
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            # битый сейв — переименуем и продолжим с новым
            was_corrupt = True
            corrupt = p + ".corrupt"
            if os.path.exists(corrupt):
                corrupt = p + f".{game.now_ts()}.corrupt"
            os.replace(p, corrupt)
        except Exception:
            # любой другой сбой — сбрасываем состояние, но не падаем
            was_corrupt = True
    st = game.default_state()
    if was_corrupt:
        st.setdefault("ui", {})["toast"] = "Сейв повреждён и восстановлен."
    return st

def _strip_transient(state: Dict[str, Any]):
    run = state.get("run")
    if not run:
        return
    combat = run.get("combat")
    if combat:
        combat.pop("_rng", None)

def save_state(sid: str, st: Dict[str, Any]) -> None:
    p = save_path(sid)
    st["updated_at"] = game.now_ts()
    _strip_transient(st)
    tmp_fd, tmp_path = tempfile.mkstemp(prefix="save_", suffix=".tmp", dir=SAVE_DIR)
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(st, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, p)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

@app.post("/api/bootstrap")
def api_bootstrap():
    data = request.get_json(silent=True) or {}
    sid = data.get("sid")
    if not sid:
        sid = game.make_uid("sid")
        st = game.default_state()
        save_state(sid, st)
        return jsonify({"sid": sid, "state": game.sanitize_for_client(st)})
    st = load_state(sid)
    # лёгкая защита от несовпадений версии
    if int(st.get("version", 0)) != game.SAVE_VERSION:
        st = game.default_state()
    save_state(sid, st)
    return jsonify({"sid": sid, "state": game.sanitize_for_client(st)})

@app.post("/api/action")
def api_action():
    data = request.get_json(silent=True) or {}
    sid = data.get("sid")
    action = data.get("action", {})
    if not sid:
        return jsonify({"error":"missing sid"}), 400
    st = load_state(sid)
    try:
        game.dispatch(st, action)
    except Exception as e:
        # чтобы фронт не зависал
        st.setdefault("ui", {})["toast"] = f"Ошибка: {type(e).__name__}"
    save_state(sid, st)
    return jsonify({"sid": sid, "state": game.sanitize_for_client(st)})

@app.get("/api/content")
def api_content():
    # Кодекс: отдаём все карты (base + плюс-версию)
    cards = []
    for c in content.CARDS:
        base = content.get_card_def(c["id"], upgraded=False)
        up = content.get_card_def(c["id"], upgraded=True)
        cards.append({"base": base, "up": up})
    for c in content.CURSES:
        base = content.get_card_def(c["id"], upgraded=False)
        cards.append({"base": base, "up": base})
    return jsonify({
        "cards": cards,
        "rarities": content.RARITIES,
        "card_types": content.CARD_TYPES,
        "statuses": content.STATUSES,
        "buffs": content.BUFFS,
        "relics": content.RELICS,
    })

@app.get("/api/ping")
def ping():
    return jsonify({"ok": True})

if __name__ == "__main__":
    # host=127.0.0.1 — только локально
    app.run(host="127.0.0.1", port=5173, debug=True)

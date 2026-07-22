# -*- coding: utf-8 -*-
"""
app.py - Server Flask + Socket.IO cho "Space Pathfinders".

QUAN TRỌNG VỀ MULTIPLAYER THẬT:
Bản này dùng Socket.IO (không chỉ REST) để mọi người chơi trong cùng 1
PHÒNG (room code 5 ký tự) đều nhận cập nhật NGAY LẬP TỨC khi có ai đó
hành động (tung xúc xắc, mua đồ, rút bài...), dù họ đang ở máy khác /
nơi khác. Muốn nhiều người ở nhiều nơi thật sự chơi được với nhau, bạn
cần DEPLOY server này lên một dịch vụ chạy liên tục (Render, Railway,
Fly.io...) rồi chia sẻ đường link + mã phòng cho bạn bè - chạy trên máy
cá nhân (localhost) thì chỉ người trong cùng mạng LAN mới vào được.

Chạy thử local:
    pip install -r requirements.txt
    python app.py
Sau đó mở nhiều tab / nhiều máy trong mạng LAN trỏ tới http://<ip-máy-chủ>:5000
"""
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, join_room, emit

from backend.game_engine import GameEngine, GameError

app = Flask(__name__, static_folder="frontend")
app.config["SECRET_KEY"] = "space-pathfinders-secret"
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

engine = GameEngine()

# room_code -> set(sid) đang kết nối, dùng để biết ai vừa rớt mạng
room_sockets: dict[str, dict[str, int]] = {}  # code -> {sid: player_id}


# ----------------------------------------------------------------------
# PHỤC VỤ FRONTEND TĨNH
# ----------------------------------------------------------------------
@app.route("/")
def serve_frontend():
    return send_from_directory("frontend", "index.html")


@app.route("/<path:filename>")
def serve_static_files(filename):
    return send_from_directory("frontend", filename)


# ----------------------------------------------------------------------
# HELPER
# ----------------------------------------------------------------------
def _ok(state):
    return jsonify({"success": True, "state": engine.serialize(state)})


def _err(e, code=400):
    return jsonify({"success": False, "error": str(e)}), code


def _broadcast(room_code, state, event="state_update"):
    socketio.emit(event, {"success": True, "state": engine.serialize(state)}, room=room_code)


# ----------------------------------------------------------------------
# REST: tạo / vào phòng (dùng REST cho bước lobby, còn lại dùng Socket.IO)
# ----------------------------------------------------------------------
@app.route("/api/create_room", methods=["POST"])
def create_room():
    data = request.get_json(force=True) or {}
    try:
        state = engine.create_room(data.get("name", ""), data.get("character", ""))
        return _ok(state)
    except GameError as e:
        return _err(e)


@app.route("/api/join_room", methods=["POST"])
def join_room_route():
    data = request.get_json(force=True) or {}
    try:
        # CHUẨN HÓA: strip + upper
        room_code = data.get("room_code", "").strip().upper()
        if not room_code:
            raise GameError("Mã phòng không được để trống")
        name = data.get("name", "").strip()
        character = data.get("character", "").strip()
        if not name or not character:
            raise GameError("Tên và nhân vật là bắt buộc")
        state = engine.join_room(room_code, name, character)
        _broadcast(state.room_code.upper(), state, "lobby_update")
        return _ok(state)
    except GameError as e:
        # In lỗi ra log để biết nguyên nhân cụ thể
        print(f"[ERROR] /api/join_room: {e}")
        return _err(e)

@app.route("/api/state/<room_code>", methods=["GET"])
def get_state(room_code):
    try:
        room_code = room_code.strip().upper()
        state = engine.get_state(room_code)
        return _ok(state)
    except GameError as e:
        print(f"[ERROR] /api/state: {e}")
        return _err(e)

@app.route("/api/characters", methods=["GET"])
def characters():
    from backend.constants import CHARACTERS
    return jsonify({"success": True, "characters": CHARACTERS})


# ----------------------------------------------------------------------
# SOCKET.IO: mọi hành động trong ván đấu đi qua đây để phát realtime
# ----------------------------------------------------------------------
@socketio.on("join")
def on_join(data):
    """Client join đúng 'room' Socket.IO trùng tên room_code để nhận broadcast."""
    room_code = (data.get("room_code") or "").upper()
    player_id = data.get("player_id")
    if not room_code:
        return
    join_room(room_code)
    room_sockets.setdefault(room_code, {})[request.sid] = player_id
    try:
        state = engine.set_connection(room_code, player_id, True, request.sid)
        _broadcast(room_code, state, "lobby_update" if not state.game_started else "state_update")
    except GameError:
        pass


@socketio.on("disconnect")
def on_disconnect():
    for room_code, sids in list(room_sockets.items()):
        if request.sid in sids:
            player_id = sids.pop(request.sid)
            try:
                state = engine.set_connection(room_code, player_id, False, None)
                _broadcast(room_code, state, "state_update")
            except GameError:
                pass


@socketio.on("start_game")
def on_start_game(data):
    room_code = (data.get("room_code") or "").upper()
    try:
        state = engine.start_game(room_code, data.get("player_id"))
        _broadcast(room_code, state)
    except GameError as e:
        emit("action_error", {"error": str(e)})


@socketio.on("roll_dice")
def on_roll_dice(data):
    room_code = (data.get("room_code") or "").upper()
    try:
        state = engine.roll_dice(room_code, data.get("player_id"), data.get("chosen_number"))
        _broadcast(room_code, state)
    except GameError as e:
        emit("action_error", {"error": str(e)})


@socketio.on("resolve_pending")
def on_resolve_pending(data):
    room_code = (data.get("room_code") or "").upper()
    try:
        state = engine.resolve_pending(room_code, data.get("player_id"), data.get("choice", {}))
        _broadcast(room_code, state)
    except GameError as e:
        emit("action_error", {"error": str(e)})


@socketio.on("buy_item")
def on_buy_item(data):
    room_code = (data.get("room_code") or "").upper()
    try:
        state = engine.buy_item(room_code, data.get("player_id"), data.get("item_type"))
        _broadcast(room_code, state)
    except GameError as e:
        emit("action_error", {"error": str(e)})


@socketio.on("skip_shop")
def on_skip_shop(data):
    room_code = (data.get("room_code") or "").upper()
    try:
        state = engine.skip_shop(room_code, data.get("player_id"))
        _broadcast(room_code, state)
    except GameError as e:
        emit("action_error", {"error": str(e)})


@socketio.on("use_item")
def on_use_item(data):
    room_code = (data.get("room_code") or "").upper()
    try:
        state = engine.use_item(
            room_code, data.get("player_id"), data.get("item_type"),
            data.get("target_id"), data.get("delta"),
        )
        _broadcast(room_code, state)
    except GameError as e:
        emit("action_error", {"error": str(e)})


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True, allow_unsafe_werkzeug=True)

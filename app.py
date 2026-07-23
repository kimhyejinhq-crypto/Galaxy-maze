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

QUAN TRỌNG VỀ DEPLOY TRÊN RENDER (đọc kỹ, đây là 2 lỗi hay gặp nhất):
1) Render cấp CỔNG NGẪU NHIÊN qua biến môi trường PORT, không phải cổng cố
   định 5000. App bên dưới đọc os.environ["PORT"] - KHÔNG được sửa lại
   thành số cố định, nếu không Render sẽ health-check thất bại, tự khởi
   động lại dyno liên tục -> vừa lag vừa mất hết state phòng đang chơi.
2) BẮT BUỘC chỉ chạy ĐÚNG 1 worker process (xem Procfile đi kèm). Vì toàn
   bộ dữ liệu phòng chơi (engine.rooms) đang lưu trong RAM của tiến trình
   Python, nếu Render/gunicorn chạy nhiều worker song song, mỗi worker có
   RAM riêng - phòng tạo ở worker A thì worker B không thấy, sinh ra lỗi
   "không tìm thấy phòng". Dùng đúng lệnh trong Procfile, ĐỪNG để Render
   tự đoán lệnh khởi động.

Chạy thử local:
    pip install -r requirements.txt
    python app.py
Sau đó mở nhiều tab / nhiều máy trong mạng LAN trỏ tới http://<ip-máy-chủ>:5000
"""
import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, join_room, emit

from backend.game_engine import GameEngine, GameError

app = Flask(__name__, static_folder="frontend")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "space-pathfinders-secret")
CORS(app)
# async_mode="threading": lựa chọn được Flask-SocketIO khuyến nghị chính
# thức hiện nay (eventlet đã ngừng bảo trì). Chạy tốt với Gunicorn ở chế
# độ multi-threaded (xem Procfile), chỉ cần đảm bảo LUÔN 1 worker process.
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
    # Lớp bảo hiểm: đảm bảo state luôn được lưu lại (Redis nếu có cấu hình,
    # RAM nếu không) ngay tại điểm phát broadcast, phòng trường hợp một
    # đường code nào đó trong game_engine quên gọi store.save().
    try:
        engine.store.save(state)
    except Exception:
        pass
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
        state = engine.join_room(data.get("room_code", ""), data.get("name", ""), data.get("character", ""))
        _broadcast(state.room_code.upper(), state, "lobby_update")
        return _ok(state)
    except GameError as e:
        return _err(e)


@app.route("/api/state/<room_code>", methods=["GET"])
def get_state(room_code):
    try:
        state = engine.get_state(room_code)
        return _ok(state)
    except GameError as e:
        return _err(e)


@app.route("/api/characters", methods=["GET"])
def characters():
    from backend.constants import CHARACTERS
    return jsonify({"success": True, "characters": CHARACTERS})


@app.route("/api/health", methods=["GET"])
def health():
    """Mở link này trên trình duyệt (vd: https://ten-app-cua-ban.onrender.com/api/health)
    để xác minh NGAY xem Redis có đang hoạt động thật hay không. Nếu
    "using_redis": false trên môi trường production (Render), phòng chơi SẼ
    bị mất khi container restart hoặc chạy nhiều instance - cần kiểm tra lại
    biến môi trường REDIS_URL trong Render Dashboard → Environment."""
    return jsonify({
        "success": True,
        "using_redis": engine.store.using_redis,
        "redis_error": engine.store.redis_error,
        "active_rooms": engine.store.room_count(),
        "pid": os.getpid(),
    })


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
    # QUAN TRỌNG: Render (và hầu hết các dịch vụ hosting) cấp cổng qua biến
    # môi trường PORT - KHÔNG được hardcode port=5000 khi chạy production,
    # nếu không nền tảng sẽ không route được request tới app, gây lag/timeout
    # và khiến dyno bị khởi động lại liên tục (mất hết state phòng chơi).
    port = int(os.environ.get("PORT", 5000))
    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    socketio.run(app, host="0.0.0.0", port=port, debug=debug_mode, allow_unsafe_werkzeug=True)

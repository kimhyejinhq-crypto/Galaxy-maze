# -*- coding: utf-8 -*-
"""
constants.py
============
Hằng số / enum dùng chung cho game "Space Pathfinders" (bản mê cung + multiplayer).

THAY ĐỔI SO VỚI BẢN GỐC:
- Bàn cờ giờ là một ĐỒ THỊ (mê cung): mỗi ô có 1 hoặc 2 ô "đi tiếp" hợp lệ
  (xem generate_maze() trong game_engine.py). Khi ô có 2 hướng, người chơi
  phải chọn hướng đi giữa lượt di chuyển.
- Thêm hệ thống NHÂN VẬT (4 nhân vật), chọn ở màn hình chờ phòng.
- Thêm PHÒNG CHƠI (room code) để nhiều người ở nhiều máy/nơi khác nhau
  cùng vào một ván qua Socket.IO.
"""

from enum import Enum


class TileType(str, Enum):
    TRONG = "TRONG"      # Ô trống - trắng, có người khác thì cướp 1 vàng
    VANG = "VANG"        # Ô vàng - +5 vàng
    DO = "DO"            # Ô đỏ - -3 vàng hoặc lùi 3 ô
    XANH = "XANH"        # Ô xanh dương - nhảy cóc tới ô cố định
    TIM = "TIM"          # Ô tím - rút bài Sự kiện
    CAM = "CAM"          # Ô cam - rút bài Bẫy
    HONG = "HONG"        # Ô hồng - cổng, trả phí đi qua
    DICH = "DICH"        # Ô 100 - đích


TILE_POOL_COUNTS = {
    TileType.TRONG: 40,
    TileType.VANG: 25,
    TileType.DO: 25,
    TileType.XANH: 15,
    TileType.TIM: 20,
    TileType.CAM: 15,
    TileType.HONG: 10,
}

BOARD_SIZE = 100
START_TILE = 1
FINISH_TILE = 100
SHOP_TILES = (20, 50, 80)

START_GOLD = 10
MAX_ITEMS_CARRIED = 2
MAX_CHAIN_REACTION = 10
GAME_TIME_LIMIT_SECONDS = 45 * 60

# --- Mê cung ---
# Tỉ lệ số ô có 2 hướng đi (ngã ba). Càng cao càng nhiều lựa chọn rẽ nhánh.
BRANCH_RATE = 0.14
# Nhánh phụ có thể nhảy xa tối đa bao nhiêu ô so với đường chính (để tạo
# cảm giác đường tắt / đường vòng thực sự, không chỉ lệch 1-2 ô).
BRANCH_MIN_OFFSET = 3
BRANCH_MAX_OFFSET = 9


class ItemType(str, Enum):
    XUC_XAC_X2 = "XUC_XAC_X2"
    LA_CHAN = "LA_CHAN"
    DAO_GAM = "DAO_GAM"
    BUA_HO_MENH = "BUA_HO_MENH"
    KINH_AP_TRONG = "KINH_AP_TRONG"


ITEM_INFO = {
    ItemType.XUC_XAC_X2: {
        "name": "Xúc Xắc Song Sinh",
        "price": 7, "stock": 5,
        "desc": "Lượt tới tung 2 lần, lấy kết quả cao hơn.",
        "emoji": "🎲",
    },
    ItemType.LA_CHAN: {
        "name": "Lá Chắn Từ Trường",
        "price": 5, "stock": 5,
        "desc": "Chặn 1 hiệu ứng xấu (Đỏ / Bẫy / Sự kiện xấu).",
        "emoji": "🛡️",
    },
    ItemType.DAO_GAM: {
        "name": "Tia Đẩy Lực",
        "price": 8, "stock": 5,
        "desc": "Đẩy lùi 4 ô 1 người trong bán kính 3 ô.",
        "emoji": "🔫",
    },
    ItemType.BUA_HO_MENH: {
        "name": "Bộ Đẩy Phụ (Booster)",
        "price": 10, "stock": 5,
        "desc": "Được tung xúc xắc & di chuyển 2 lần trong 1 lượt.",
        "emoji": "🚀",
    },
    ItemType.KINH_AP_TRONG: {
        "name": "Kính Định Vị 3 Mắt",
        "price": 6, "stock": 5,
        "desc": "Sau khi tung xúc xắc, +-1 điểm tuỳ chọn.",
        "emoji": "👁️",
    },
}

# --- Nhân vật ---
CHARACTERS = {
    "THO": {
        "id": "THO", "name": "Trang - Thỏ Vũ Trụ",
        "emoji": "🐰", "token": "🐰", "color": "#FF819C",
    },
    "CANH_CUT": {
        "id": "CANH_CUT", "name": "Quang - Cánh Cụt Du Hành",
        "emoji": "🐧", "token": "🐧", "color": "#66C7F4",
    },
    "CAO": {
        "id": "CAO", "name": "Thành - Cáo Phi Hành",
        "emoji": "🦊", "token": "🦊", "color": "#FFB8E3",
    },
    "QUA": {
        "id": "QUA", "name": "Jin - Quạ Không Gian",
        "emoji": "🐦‍⬛", "token": "🐦‍⬛", "color": "#6C6EA0",
    },
}
CHARACTER_ORDER = ["THO", "CANH_CUT", "CAO", "QUA"]

# --- Bài Sự kiện (TIM) ---
# await: None | single_target | two_targets | copy_choice | tile_choice
#        | two_tile_choice | five_tile_choice | area_choice
EVENT_CARDS = [
    {"id": "EV01", "name": "Mưa Sao Băng May Mắn", "desc": "+8 vàng từ trên trời rơi xuống.",
     "effect": "self_gold", "amount": 8, "await": None},
    {"id": "EV02", "name": "Trạm Tiếp Tế", "desc": "+6 vàng, +1 bước tiến.",
     "effect": "self_gold_move", "amount": 6, "move": 1, "await": None},
    {"id": "EV03", "name": "Cướp Nhiên Liệu", "desc": "Chọn 1 người chơi để lấy 5 vàng của họ.",
     "effect": "steal_gold", "amount": 5, "await": "single_target"},
    {"id": "EV04", "name": "Hố Sâu Không Gian", "desc": "Lùi lại 5 ô.",
     "effect": "self_move", "amount": -5, "await": None},
    {"id": "EV05", "name": "Cổng Dịch Chuyển Đôi", "desc": "Chọn 2 người chơi để họ hoán đổi vị trí cho nhau.",
     "effect": "swap_positions", "await": "two_targets"},
    {"id": "EV06", "name": "Máy Quét Sao Chép", "desc": "Chọn 1 người chơi, sao chép Vị trí hoặc Vàng của họ.",
     "effect": "copy_stat", "await": "copy_choice"},
    {"id": "EV07", "name": "Bùa Hộ Mệnh Vũ Trụ", "desc": "Miễn nhiễm hiệu ứng xấu trong 2 lượt tới.",
     "effect": "self_immune", "turns": 2, "await": None},
    {"id": "EV08", "name": "Trợ Lý AI", "desc": "+10 vàng.",
     "effect": "self_gold", "amount": 10, "await": None},
    {"id": "EV09", "name": "Dịch Chuyển Không Gian", "desc": "Chọn 1 ô (2-99) để dịch chuyển tới đó.",
     "effect": "teleport_to_tile", "await": "tile_choice"},
    {"id": "EV10", "name": "Bão Từ", "desc": "Mất 4 vàng.",
     "effect": "self_gold", "amount": -4, "await": None},
]

# --- Bài Bẫy (CAM) ---
TRAP_CARDS = [
    {"id": "TR01", "name": "Bẫy Trọng Lực", "desc": "Lùi 3 ô.",
     "effect": "self_move", "amount": -3, "await": None, "negative": True},
    {"id": "TR02", "name": "Bẫy Đánh Cắp", "desc": "Mất 6 vàng.",
     "effect": "self_gold", "amount": -6, "await": None, "negative": True},
    {"id": "TR03", "name": "Bẫy Đóng Băng", "desc": "Mất lượt kế tiếp.",
     "effect": "skip_turn", "await": None, "negative": True},
    {"id": "TR04", "name": "Bẫy Đảo Ngược Không Gian", "desc": "Chọn khu vực trên bàn cờ để đảo ngược thứ tự ô.",
     "effect": "reverse_area", "await": "area_choice",
     "options": ["1-25", "26-50", "51-75", "76-99"], "negative": True},
    {"id": "TR05", "name": "Bẫy Tráo Đổi", "desc": "Nhập 2 số ô để hoán đổi loại ô cho nhau.",
     "effect": "swap_tile_types", "await": "two_tile_choice", "negative": True},
    {"id": "TR06", "name": "Bẫy Tái Cấu Trúc", "desc": "Nhập đúng 5 số ô để đổi thành ô Trống.",
     "effect": "reset_tiles", "await": "five_tile_choice", "negative": True},
    {"id": "TR07", "name": "Bẫy Ngược - Đặt Bẫy Người Sau", "desc": "Ô hiện tại của bạn trở thành bẫy ngược cho người tiếp theo dừng ở đây.",
     "effect": "place_reverse_trap", "await": None, "negative": True},
]

REVERSE_TRAP_PENALTY_GOLD = 5

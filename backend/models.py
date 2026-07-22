# -*- coding: utf-8 -*-
"""
models.py
=========
Cấu trúc dữ liệu thuần tuý mô tả trạng thái ván game (không chứa luật chơi).
"""

from dataclasses import dataclass, field
from typing import Optional, Any
import time

from .constants import TileType, ItemType


@dataclass
class Tile:
    """Một ô trên bản đồ mê cung 1..100."""
    index: int
    type: TileType
    connections: list = field(default_factory=list)   # list[int] - 1 hoặc 2 ô đi tiếp
    jump_target: Optional[int] = None                  # chỉ Ô XANH dùng

    def to_dict(self):
        return {
            "index": self.index,
            "type": self.type.value,
            "connections": self.connections,
            "is_branch": len(self.connections) > 1,
            "jump_target": self.jump_target,
        }


@dataclass
class StatusEffect:
    kind: str
    turns_left: int
    data: dict = field(default_factory=dict)

    def to_dict(self):
        return {"kind": self.kind, "turns_left": self.turns_left, "data": self.data}


@dataclass
class Player:
    id: int
    name: str
    character: str              # id trong CHARACTERS, vd "THO"
    color: str = ""              # hex màu lấy từ CHARACTERS[character]
    position: int = 1
    gold: int = 10
    debt: int = 0
    items: list = field(default_factory=list)
    statuses: list = field(default_factory=list)
    skip_next_turn: bool = False
    finished: bool = False
    finish_rank: Optional[int] = None
    connected: bool = True        # dùng cho multiplayer: còn kết nối socket không
    sid: Optional[str] = None     # socket session id hiện tại của người chơi này
    shield_charges: int = 0       # số lần chặn hiệu ứng xấu còn lại (Lá Chắn / Bùa Hộ Mệnh)

    pending_double_action: bool = False
    pending_double_roll: bool = False
    pending_lens_delta: int = 0

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "character": self.character,
            "color": self.color,
            "position": self.position,
            "gold": self.gold,
            "debt": self.debt,
            "items": [i.value if hasattr(i, "value") else i for i in self.items],
            "statuses": [s.to_dict() for s in self.statuses],
            "skip_next_turn": self.skip_next_turn,
            "finished": self.finished,
            "finish_rank": self.finish_rank,
            "connected": self.connected,
            "shield_charges": self.shield_charges,
        }


@dataclass
class GameState:
    room_code: str = ""
    players: list = field(default_factory=list)
    board: list = field(default_factory=list)
    reserve_pool: list = field(default_factory=list)
    event_deck: list = field(default_factory=list)
    trap_deck: list = field(default_factory=list)
    item_stock: dict = field(default_factory=dict)
    common_fund: int = 0
    current_player_index: int = 0
    turn_count: int = 0
    started_at: float = field(default_factory=time.time)
    game_over: bool = False
    winner_id: Optional[int] = None
    log: list = field(default_factory=list)
    events_feed: list = field(default_factory=list)  # popup events cho frontend (xem game_engine)

    pending_shop_tile: bool = False
    pending_action: Optional[dict] = None
    pending_move: Optional[dict] = None   # {"player_id", "remaining_steps"} khi đang giữa lượt di chuyển

    reverse_trap_tiles: dict = field(default_factory=dict)
    game_started: bool = False   # phòng đã bắt đầu ván hay còn ở màn hình chờ

    def to_dict(self):
        return {
            "room_code": self.room_code,
            "players": [p.to_dict() for p in self.players],
            "board": [t.to_dict() for t in self.board[1:]],
            "common_fund": self.common_fund,
            "current_player_index": self.current_player_index,
            "turn_count": self.turn_count,
            "started_at": self.started_at,
            "time_limit_seconds": 45 * 60,
            "game_over": self.game_over,
            "winner_id": self.winner_id,
            "log": self.log[-40:],
            "events_feed": self.events_feed[-10:],
            "pending_shop_tile": self.pending_shop_tile,
            "pending_action": self.pending_action,
            "pending_move": self.pending_move,
            "item_stock": {k.value: v for k, v in self.item_stock.items()},
            "item_info": None,   # điền ở game_engine.to_dict_public() (tránh import vòng)
            "reserve_count": len(self.reserve_pool),
            "event_deck_count": len(self.event_deck),
            "trap_deck_count": len(self.trap_deck),
            "game_started": self.game_started,
        }

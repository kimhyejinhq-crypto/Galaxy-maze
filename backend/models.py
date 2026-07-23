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

    def to_full(self):
        return {"index": self.index, "type": self.type.value,
                "connections": self.connections, "jump_target": self.jump_target}

    @staticmethod
    def from_full(d):
        return Tile(index=d["index"], type=TileType(d["type"]),
                    connections=list(d.get("connections", [])),
                    jump_target=d.get("jump_target"))


@dataclass
class StatusEffect:
    kind: str
    turns_left: int
    data: dict = field(default_factory=dict)

    def to_dict(self):
        return {"kind": self.kind, "turns_left": self.turns_left, "data": self.data}

    def to_full(self):
        return {"kind": self.kind, "turns_left": self.turns_left, "data": self.data}

    @staticmethod
    def from_full(d):
        return StatusEffect(kind=d["kind"], turns_left=d["turns_left"], data=d.get("data", {}))


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

    def to_full(self):
        return {
            "id": self.id, "name": self.name, "character": self.character, "color": self.color,
            "position": self.position, "gold": self.gold, "debt": self.debt,
            "items": [i.value if hasattr(i, "value") else i for i in self.items],
            "statuses": [s.to_full() for s in self.statuses],
            "skip_next_turn": self.skip_next_turn, "finished": self.finished,
            "finish_rank": self.finish_rank, "connected": self.connected, "sid": self.sid,
            "shield_charges": self.shield_charges,
            "pending_double_action": self.pending_double_action,
            "pending_double_roll": self.pending_double_roll,
            "pending_lens_delta": self.pending_lens_delta,
        }

    @staticmethod
    def from_full(d):
        from .constants import ItemType as _ItemType
        return Player(
            id=d["id"], name=d["name"], character=d["character"], color=d.get("color", ""),
            position=d.get("position", 1), gold=d.get("gold", 10), debt=d.get("debt", 0),
            items=[_ItemType(x) for x in d.get("items", [])],
            statuses=[StatusEffect.from_full(s) for s in d.get("statuses", [])],
            skip_next_turn=d.get("skip_next_turn", False), finished=d.get("finished", False),
            finish_rank=d.get("finish_rank"), connected=d.get("connected", True), sid=d.get("sid"),
            shield_charges=d.get("shield_charges", 0),
            pending_double_action=d.get("pending_double_action", False),
            pending_double_roll=d.get("pending_double_roll", False),
            pending_lens_delta=d.get("pending_lens_delta", 0),
        )


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

    def to_full(self):
        """Serialize TOÀN BỘ state (kể cả dữ liệu nội bộ) để lưu vào Redis/bộ nhớ
        ngoài, phục vụ khôi phục chính xác 100% sau khi restart/đổi container."""
        return {
            "room_code": self.room_code,
            "players": [p.to_full() for p in self.players],
            "board": [t.to_full() for t in self.board[1:]] if self.board else [],
            "reserve_pool": [t.value for t in self.reserve_pool],
            "event_deck": self.event_deck,
            "trap_deck": self.trap_deck,
            "item_stock": {k.value: v for k, v in self.item_stock.items()},
            "common_fund": self.common_fund,
            "current_player_index": self.current_player_index,
            "turn_count": self.turn_count,
            "started_at": self.started_at,
            "game_over": self.game_over,
            "winner_id": self.winner_id,
            "log": self.log,
            "events_feed": self.events_feed,
            "pending_shop_tile": self.pending_shop_tile,
            "pending_action": self.pending_action,
            "pending_move": self.pending_move,
            "reverse_trap_tiles": {str(k): v for k, v in self.reverse_trap_tiles.items()},
            "game_started": self.game_started,
        }

    @staticmethod
    def from_full(d):
        from .constants import ItemType as _ItemType
        board = [None] + [Tile.from_full(t) for t in d.get("board", [])] if d.get("board") else []
        state = GameState(
            room_code=d.get("room_code", ""),
            players=[Player.from_full(p) for p in d.get("players", [])],
            board=board,
            reserve_pool=[TileType(x) for x in d.get("reserve_pool", [])],
            event_deck=d.get("event_deck", []),
            trap_deck=d.get("trap_deck", []),
            item_stock={_ItemType(k): v for k, v in d.get("item_stock", {}).items()},
            common_fund=d.get("common_fund", 0),
            current_player_index=d.get("current_player_index", 0),
            turn_count=d.get("turn_count", 0),
            started_at=d.get("started_at", time.time()),
            game_over=d.get("game_over", False),
            winner_id=d.get("winner_id"),
            log=d.get("log", []),
            events_feed=d.get("events_feed", []),
            pending_shop_tile=d.get("pending_shop_tile", False),
            pending_action=d.get("pending_action"),
            pending_move=d.get("pending_move"),
            reverse_trap_tiles={int(k): v for k, v in d.get("reverse_trap_tiles", {}).items()},
            game_started=d.get("game_started", False),
        )
        return state

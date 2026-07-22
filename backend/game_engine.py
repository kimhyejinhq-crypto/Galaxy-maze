# -*- coding: utf-8 -*-
"""
game_engine.py
==============
Toàn bộ luật chơi "Space Pathfinders". Bản này thay bàn cờ thẳng bằng
MÊ CUNG (đồ thị có nhánh rẽ), thêm nhân vật, thêm phòng chơi nhiều người
(nhiều máy / nhiều nơi), và SỬA bug mua đồ ở cửa hàng của bản cũ.

Kiến trúc: mỗi phòng (room) là 1 GameState độc lập, lưu trong self.rooms.
app.py (Socket.IO) sẽ gọi các hàm public ở đây rồi phát (emit) state mới
cho toàn bộ người chơi trong phòng.
"""

import random
import string
import threading
import time
from typing import Optional

from .constants import (
    TileType, ItemType, ITEM_INFO, CHARACTERS, CHARACTER_ORDER,
    TILE_POOL_COUNTS, BOARD_SIZE, START_TILE, FINISH_TILE, SHOP_TILES,
    START_GOLD, MAX_ITEMS_CARRIED, BRANCH_RATE, BRANCH_MIN_OFFSET,
    BRANCH_MAX_OFFSET, EVENT_CARDS, TRAP_CARDS, REVERSE_TRAP_PENALTY_GOLD,
)
from .models import Tile, Player, GameState, StatusEffect


class GameError(Exception):
    pass


class GameEngine:
    def __init__(self):
        self.rooms: dict[str, GameState] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # PHÒNG CHƠI / LOBBY
    # ------------------------------------------------------------------
    def create_room(self, host_name: str, character: str) -> GameState:
        if not host_name or not host_name.strip():
            raise GameError("Vui lòng nhập tên.")
        if character not in CHARACTERS:
            raise GameError("Nhân vật không hợp lệ.")
        with self._lock:
            code = self._gen_room_code()
            state = GameState(room_code=code)
            state.item_stock = {it: ITEM_INFO[it]["stock"] for it in ItemType}
            player = Player(
                id=1, name=host_name.strip()[:20], character=character,
                color=CHARACTERS[character]["color"], position=START_TILE,
                gold=START_GOLD,
            )
            state.players.append(player)
            self.rooms[code] = state
            self._log(state, f"🚀 {player.name} ({CHARACTERS[character]['name']}) đã tạo phòng {code}.")
            return state

    def join_room(self, code: str, name: str, character: str) -> GameState:
        state = self._get(code)
        if state.game_started:
            raise GameError("Ván đấu đã bắt đầu, không thể tham gia thêm.")
        if len(state.players) >= 4:
            raise GameError("Phòng đã đủ 4 phi hành gia.")
        if not name or not name.strip():
            raise GameError("Vui lòng nhập tên.")
        if character not in CHARACTERS:
            raise GameError("Nhân vật không hợp lệ.")
        taken = {p.character for p in state.players}
        if character in taken:
            raise GameError("Nhân vật này đã có người chọn.")
        new_id = max(p.id for p in state.players) + 1
        player = Player(
            id=new_id, name=name.strip()[:20], character=character,
            color=CHARACTERS[character]["color"], position=START_TILE,
            gold=START_GOLD,
        )
        state.players.append(player)
        self._log(state, f"👋 {player.name} ({CHARACTERS[character]['name']}) đã vào phòng.")
        return state

    def set_connection(self, code: str, player_id: int, connected: bool, sid: Optional[str] = None):
        state = self._get(code)
        p = self._find_player(state, player_id)
        if p:
            p.connected = connected
            p.sid = sid
        return state

    def start_game(self, code: str, player_id: int) -> GameState:
        state = self._get(code)
        if state.game_started:
            raise GameError("Ván đấu đã bắt đầu rồi.")
        if len(state.players) < 2:
            raise GameError("Cần tối thiểu 2 phi hành gia để bắt đầu.")
        if state.players[0].id != player_id:
            raise GameError("Chỉ chủ phòng mới có thể bắt đầu ván đấu.")
        board, reserve = self._generate_maze()
        state.board = board
        state.reserve_pool = reserve
        state.event_deck = self._fresh_deck(EVENT_CARDS)
        state.trap_deck = self._fresh_deck(TRAP_CARDS)
        state.game_started = True
        state.started_at = time.time()
        state.current_player_index = 0
        self._log(state, f"🛰️ Ván đấu chính thức bắt đầu với {len(state.players)} phi hành gia! Chúc may mắn.")
        self._push_event(state, "game_start", "Ván đấu bắt đầu! Chúc các phi hành gia may mắn.")
        return state

    # ------------------------------------------------------------------
    # SINH BÀN CỜ MÊ CUNG
    # ------------------------------------------------------------------
    def _generate_maze(self):
        bag = []
        for t, cnt in TILE_POOL_COUNTS.items():
            bag += [t] * cnt
        random.shuffle(bag)

        n_playable = BOARD_SIZE - 2  # ô 2..99
        draw = bag[:n_playable]
        reserve = bag[n_playable:]

        board = [None] * (BOARD_SIZE + 1)
        board[START_TILE] = Tile(START_TILE, TileType.TRONG)
        for i in range(2, BOARD_SIZE):
            board[i] = Tile(i, draw[i - 2])
        board[FINISH_TILE] = Tile(FINISH_TILE, TileType.DICH)

        # đường đi mặc định: mỗi ô nối tới ô kế tiếp
        for i in range(START_TILE, FINISH_TILE):
            board[i].connections = [i + 1]
        board[FINISH_TILE].connections = []

        # gán ô Xanh: nhảy cóc tới 1 ô cố định khác (random, cố định cho cả ván)
        for i in range(2, FINISH_TILE):
            if board[i].type == TileType.XANH:
                candidates = [j for j in range(2, FINISH_TILE) if j != i]
                board[i].jump_target = random.choice(candidates)

        # tạo ngã ba (mê cung): một số ô có 2 hướng đi
        branch_count = max(1, int(n_playable * BRANCH_RATE))
        candidate_indices = list(range(2, FINISH_TILE - BRANCH_MIN_OFFSET))
        random.shuffle(candidate_indices)
        made = 0
        for idx in candidate_indices:
            if made >= branch_count:
                break
            offset = random.randint(BRANCH_MIN_OFFSET, BRANCH_MAX_OFFSET)
            alt = min(FINISH_TILE, idx + offset)
            main_next = board[idx].connections[0] if board[idx].connections else idx + 1
            if alt == main_next or alt <= idx:
                continue
            board[idx].connections = [main_next, alt]
            made += 1

        return board, reserve

    def _fresh_deck(self, cards):
        deck = [dict(c) for c in cards] * 3   # nhân bản để đủ rút nhiều lượt
        random.shuffle(deck)
        return deck

    def _gen_room_code(self) -> str:
        while True:
            code = "".join(random.choices(string.ascii_uppercase + string.digits, k=5))
            if code not in self.rooms:
                return code

    # ------------------------------------------------------------------
    # TRUY XUẤT / TIỆN ÍCH
    # ------------------------------------------------------------------
    def _get(self, code: str) -> GameState:
        state = self.rooms.get((code or "").upper())
        if not state:
            raise GameError("Không tìm thấy phòng chơi này.")
        return state

    def get_state(self, code: str) -> GameState:
        return self._get(code)

    def serialize(self, state: GameState) -> dict:
        d = state.to_dict()
        d["item_info"] = {k.value: v for k, v in ITEM_INFO.items()}
        d["characters"] = CHARACTERS
        return d

    def _find_player(self, state: GameState, player_id) -> Optional[Player]:
        for p in state.players:
            if p.id == player_id:
                return p
        return None

    def _log(self, state: GameState, text: str):
        state.log.append(text)

    def _push_event(self, state: GameState, kind: str, text: str, data: Optional[dict] = None):
        """Sự kiện popup hiển thị giữa màn hình cho frontend (kind dùng để chọn animation)."""
        state.events_feed.append({
            "id": f"{int(time.time()*1000)}-{random.randint(0,9999)}",
            "kind": kind, "text": text, "data": data or {}, "ts": time.time(),
        })

    def _validate_turn(self, state: GameState, player_id) -> Player:
        if state.game_over:
            raise GameError("Ván đấu đã kết thúc.")
        if not state.game_started:
            raise GameError("Ván đấu chưa bắt đầu.")
        if state.pending_action:
            raise GameError("Đang có hành động chờ xử lý, hãy giải quyết trước.")
        player = self._find_player(state, player_id)
        if not player:
            raise GameError("Người chơi không tồn tại trong phòng.")
        if state.players[state.current_player_index].id != player_id:
            raise GameError("Chưa đến lượt của bạn.")
        return player

    def _consume_shield(self, player: Player) -> bool:
        if player.shield_charges > 0:
            player.shield_charges -= 1
            return True
        return False

    def _add_gold(self, player: Player, amount: int):
        """Cộng/trừ vàng, tự động trừ nợ cũ trước khi cộng thêm (ghi chú luật gốc)."""
        if amount >= 0:
            if player.debt > 0:
                pay = min(amount, player.debt)
                player.debt -= pay
                amount -= pay
            player.gold += amount
        else:
            player.gold = max(0, player.gold + amount)

    # ------------------------------------------------------------------
    # TUNG XÚC XẮC / DI CHUYỂN
    # ------------------------------------------------------------------
    def roll_dice(self, code: str, player_id: int, chosen_number=None) -> GameState:
        state = self._get(code)
        player = self._validate_turn(state, player_id)
        if state.pending_shop_tile:
            raise GameError("Bạn đang ở cửa hàng, hãy mua đồ hoặc bỏ qua trước.")
        if state.pending_move:
            raise GameError("Đang trong lượt di chuyển, chưa thể tung xúc xắc mới.")

        if player.skip_next_turn:
            player.skip_next_turn = False
            self._log(state, f"❄️ {player.name} đang bị đóng băng, mất lượt này.")
            self._push_event(state, "skip_turn", f"{player.name} mất lượt do bị đóng băng!")
            self._advance_turn(state)
            return state

        rolls = [random.randint(1, 6)]
        if player.pending_double_roll:
            rolls.append(random.randint(1, 6))
            player.pending_double_roll = False
        steps = max(rolls)

        if player.pending_lens_delta != 0:
            steps = max(1, steps + player.pending_lens_delta)
            player.pending_lens_delta = 0

        self._log(state, f"🎲 {player.name} tung xúc xắc: {rolls} → di chuyển {steps} ô.")
        self._push_event(state, "dice_roll", f"{player.name} tung được {steps}!",
                          data={"rolls": rolls, "player_id": player.id})

        state.pending_move = {"player_id": player.id, "remaining_steps": steps, "path": [player.position]}
        self._advance_move(state)
        return state

    def _advance_move(self, state: GameState):
        pm = state.pending_move
        if not pm:
            return
        player = self._find_player(state, pm["player_id"])
        while pm["remaining_steps"] > 0:
            tile = state.board[player.position]
            conns = tile.connections
            if not conns:
                break
            if len(conns) > 1:
                state.pending_action = {
                    "kind": "direction_choice",
                    "card_name": "Ngã Ba Không Gian",
                    "card_desc": "Có 2 đường đi - chọn hướng của bạn!",
                    "await": "direction_choice",
                    "options": conns,
                    "player_id": player.id,
                }
                self._push_event(state, "branch", f"{player.name} gặp ngã ba không gian, phải chọn hướng!",
                                  data={"options": conns, "player_id": player.id, "path": list(pm["path"])})
                return
            player.position = conns[0]
            pm["path"].append(player.position)
            pm["remaining_steps"] -= 1
            if player.position >= FINISH_TILE:
                pm["remaining_steps"] = 0
                break
        self._push_event(state, "move_path", f"{player.name} di chuyển.",
                          data={"player_id": player.id, "path": list(pm["path"])})
        state.pending_move = None
        self._land_on_tile(state, player)

    # ------------------------------------------------------------------
    # XỬ LÝ Ô / BÀI SỰ KIỆN / BÀI BẪY
    # ------------------------------------------------------------------
    def _land_on_tile(self, state: GameState, player: Player, depth: int = 0):
        if depth > 5:
            self._post_landing_checks(state, player)
            return

        if player.position >= FINISH_TILE:
            player.position = FINISH_TILE
            player.finished = True
            player.finish_rank = 1
            state.winner_id = player.id
            state.game_over = True
            self._log(state, f"🏆 {player.name} đã về đích đầu tiên và giành chiến thắng!")
            self._push_event(state, "game_over", f"🏆 {player.name} về đích đầu tiên!",
                              data={"player_id": player.id})
            return

        if player.position in state.reverse_trap_tiles and state.reverse_trap_tiles[player.position] != player.id:
            placer_id = state.reverse_trap_tiles.pop(player.position)
            placer = self._find_player(state, placer_id)
            pay = min(REVERSE_TRAP_PENALTY_GOLD, player.gold)
            if not self._consume_shield(player):
                player.gold -= pay
                if placer:
                    placer.gold += pay
                self._log(state, f"💥 {player.name} dính bẫy ngược của {placer.name if placer else '??'}, mất {pay} vàng!")
                self._push_event(state, "trap_reverse", f"{player.name} dính bẫy ngược! -{pay} vàng")
            else:
                self._log(state, f"🛡️ {player.name} dùng Lá Chắn chặn bẫy ngược!")
                self._push_event(state, "shield_block", f"{player.name} chặn được bẫy ngược!")

        tile = state.board[player.position]
        self._apply_tile_type(state, player, tile, depth)

        if state.pending_action or state.game_over:
            return
        self._post_landing_checks(state, player)

    def _apply_tile_type(self, state: GameState, player: Player, tile: Tile, depth: int):
        ttype = tile.type

        if ttype == TileType.TRONG:
            others = [p for p in state.players
                      if p.id != player.id and p.position == player.position and not p.finished]
            if tile.index != START_TILE and others:
                victim = others[0]
                pay = min(1, victim.gold)
                if not self._consume_shield(victim):
                    victim.gold -= pay
                    player.gold += pay
                    self._log(state, f"🕳️ {player.name} cướp {pay} vàng của {victim.name} tại ô trống.")
                    self._push_event(state, "steal", f"{player.name} cướp {pay} vàng của {victim.name}!")
                else:
                    self._log(state, f"🛡️ {victim.name} dùng Lá Chắn chặn cướp vàng!")
            else:
                self._log(state, f"⬜ {player.name} dừng ở ô trống, an toàn.")

        elif ttype == TileType.VANG:
            self._add_gold(player, 5)
            self._log(state, f"✨ {player.name} nhặt được 5 vàng từ mảnh thiên thạch!")
            self._push_event(state, "gold_gain", f"{player.name} +5 vàng!")

        elif ttype == TileType.DO:
            if self._consume_shield(player):
                self._log(state, f"🛡️ {player.name} dùng Lá Chắn chặn ô nguy hiểm (Đỏ)!")
                self._push_event(state, "shield_block", f"{player.name} chặn được ô Đỏ!")
            else:
                if player.gold >= 3:
                    player.gold -= 3
                    self._log(state, f"🔥 {player.name} rơi vào vùng thiên thạch, mất 3 vàng.")
                else:
                    debt_added = 3 - player.gold
                    player.debt += debt_added
                    player.gold = 0
                    self._log(state, f"🔥 {player.name} không đủ vàng, ghi nợ {debt_added} vàng.")
                self._push_event(state, "danger", f"{player.name} gặp vùng nguy hiểm! -3 vàng")

        elif ttype == TileType.XANH:
            target = tile.jump_target or player.position
            self._log(state, f"🌀 {player.name} rơi vào cổng dịch chuyển, nhảy tới ô {target}!")
            self._push_event(state, "warp", f"{player.name} dịch chuyển tới ô {target}!",
                              data={"target": target})
            player.position = target
            self._land_on_tile(state, player, depth + 1)
            return

        elif ttype == TileType.TIM:
            self._draw_event(state, player)
            return

        elif ttype == TileType.CAM:
            self._draw_trap(state, player)
            return

        elif ttype == TileType.HONG:
            if self._consume_shield(player):
                self._log(state, f"🛡️ {player.name} dùng Lá Chắn miễn phí cổng thu phí!")
                self._push_event(state, "shield_block", f"{player.name} miễn phí qua cổng!")
            else:
                toll = 3
                if player.gold >= toll:
                    player.gold -= toll
                    state.common_fund += toll
                else:
                    state.common_fund += player.gold
                    player.debt += (toll - player.gold)
                    player.gold = 0
                self._log(state, f"🚪 {player.name} trả phí {toll} vàng qua cổng không gian.")
                self._push_event(state, "toll", f"{player.name} trả phí cổng không gian.")

        elif ttype == TileType.DICH:
            pass  # xử lý ở đầu _land_on_tile

    def _draw_event(self, state: GameState, player: Player):
        if not state.event_deck:
            state.event_deck = self._fresh_deck(EVENT_CARDS)
        card = state.event_deck.pop()
        self._push_event(state, "draw_event", f"{player.name} rút bài Sự Kiện!",
                          data={"card": card})
        self._resolve_card(state, player, card, is_trap=False)

    def _draw_trap(self, state: GameState, player: Player):
        if not state.trap_deck:
            state.trap_deck = self._fresh_deck(TRAP_CARDS)
        card = state.trap_deck.pop()
        self._push_event(state, "draw_trap", f"{player.name} rút bài Bẫy!",
                          data={"card": card})
        self._resolve_card(state, player, card, is_trap=True)

    def _resolve_card(self, state: GameState, player: Player, card: dict, is_trap: bool):
        negative = bool(card.get("negative")) or is_trap
        if negative and card.get("await") is None and self._consume_shield(player):
            self._log(state, f"🛡️ {player.name} dùng Lá Chắn chặn '{card['name']}'!")
            self._push_event(state, "shield_block", f"{player.name} chặn được {card['name']}!")
            self._post_landing_checks(state, player)
            return

        if card.get("await") is None:
            self._apply_card_effect(state, player, card, None)
            if not state.game_over:
                self._post_landing_checks(state, player)
            return

        options = card.get("options")
        if options is None:
            if card["await"] in ("single_target", "two_targets", "copy_choice"):
                options = [p.id for p in state.players if p.id != player.id and not p.finished]
            else:
                options = []
        state.pending_action = {
            "kind": "trap" if is_trap else "event",
            "card_name": card["name"], "card_desc": card["desc"],
            "await": card["await"], "options": options,
            "card": card, "acting_player_id": player.id,
        }

    def _apply_card_effect(self, state: GameState, player: Player, card: dict, choice):
        effect = card["effect"]
        choice = choice or {}

        if effect == "self_gold":
            self._add_gold(player, card["amount"])
            self._log(state, f"{'💰' if card['amount']>=0 else '💸'} {player.name}: {card['name']} ({card['amount']:+d} vàng).")

        elif effect == "self_gold_move":
            self._add_gold(player, card["amount"])
            self._simple_shift(state, player, card.get("move", 0))
            self._log(state, f"{player.name}: {card['name']} ({card['amount']:+d} vàng, {card.get('move',0):+d} ô).")

        elif effect == "self_move":
            self._simple_shift(state, player, card["amount"])
            self._log(state, f"{player.name}: {card['name']} ({card['amount']:+d} ô).")

        elif effect == "steal_gold":
            target = self._find_player(state, choice.get("target_id"))
            if target and target.id != player.id:
                if self._consume_shield(target):
                    self._log(state, f"🛡️ {target.name} dùng Lá Chắn chặn bị cướp vàng!")
                else:
                    pay = min(card["amount"], target.gold)
                    target.gold -= pay
                    player.gold += pay
                    self._log(state, f"{player.name} cướp {pay} vàng của {target.name} ({card['name']}).")

        elif effect == "swap_positions":
            ids = choice.get("targets", [])
            ps = [self._find_player(state, i) for i in ids]
            if len(ps) == 2 and all(ps):
                ps[0].position, ps[1].position = ps[1].position, ps[0].position
                self._log(state, f"🔀 {ps[0].name} và {ps[1].name} hoán đổi vị trí ({card['name']}).")

        elif effect == "copy_stat":
            target = self._find_player(state, choice.get("target_id"))
            field_name = choice.get("field", "position")
            if target and field_name in ("position", "gold"):
                setattr(player, field_name, getattr(target, field_name))
                self._log(state, f"{player.name} sao chép {field_name} của {target.name} ({card['name']}).")

        elif effect == "self_immune":
            player.shield_charges += max(1, card.get("turns", 1))
            self._log(state, f"🛡️ {player.name} nhận {card.get('turns',1)} lượt miễn nhiễm ({card['name']}).")

        elif effect == "teleport_to_tile":
            tile_no = choice.get("tile")
            if isinstance(tile_no, int) and 2 <= tile_no <= FINISH_TILE - 1:
                player.position = tile_no
                self._log(state, f"🌌 {player.name} dịch chuyển tới ô {tile_no} ({card['name']}).")

        elif effect == "skip_turn":
            player.skip_next_turn = True
            self._log(state, f"❄️ {player.name} sẽ mất lượt kế tiếp ({card['name']}).")

        elif effect == "reverse_area":
            area = choice.get("area") or (card.get("options") or [None])[0]
            if area:
                lo, hi = [int(x) for x in area.split("-")]
                lo, hi = max(2, lo), min(FINISH_TILE - 1, hi)
                types = [state.board[i].type for i in range(lo, hi + 1)]
                types.reverse()
                for i, t in zip(range(lo, hi + 1), types):
                    state.board[i].type = t
                self._log(state, f"🔄 {player.name} đảo ngược khu vực ô {lo}-{hi} ({card['name']}).")

        elif effect == "swap_tile_types":
            a, b = choice.get("tile_a"), choice.get("tile_b")
            if isinstance(a, int) and isinstance(b, int) and 2 <= a <= 99 and 2 <= b <= 99 and a != b:
                state.board[a].type, state.board[b].type = state.board[b].type, state.board[a].type
                self._log(state, f"🔀 {player.name} hoán đổi loại ô {a} và {b} ({card['name']}).")

        elif effect == "reset_tiles":
            tiles = choice.get("tiles", [])
            valid = sorted(set(t for t in tiles if isinstance(t, int) and 2 <= t <= 99))
            if len(valid) == 5:
                for i in valid:
                    state.board[i].type = TileType.TRONG
                self._log(state, f"♻️ {player.name} tái cấu trúc 5 ô {valid} thành ô Trống ({card['name']}).")

        elif effect == "place_reverse_trap":
            state.reverse_trap_tiles[player.position] = player.id
            self._log(state, f"🪤 {player.name} đặt bẫy ngược tại ô {player.position} ({card['name']}).")

    def _simple_shift(self, state: GameState, player: Player, amount: int):
        """Dịch chuyển đơn giản (không cần chọn hướng) dùng cho hiệu ứng bài -
        đi theo đường mặc định (connections[0]) khi tiến, hoặc lùi thẳng số ô khi amount<0."""
        if amount == 0:
            return
        pos = player.position
        if amount > 0:
            for _ in range(amount):
                conns = state.board[pos].connections
                if not conns:
                    break
                pos = conns[0]
        else:
            pos = max(START_TILE, pos + amount)
        player.position = min(FINISH_TILE, pos)

    def _post_landing_checks(self, state: GameState, player: Player):
        if state.game_over:
            return
        if not player.finished and player.position in SHOP_TILES and not state.pending_shop_tile:
            state.pending_shop_tile = True
            self._log(state, f"🛍️ {player.name} dừng đúng trạm mua sắm của Gã Hề!")
            self._push_event(state, "shop", f"{player.name} ghé trạm mua sắm!")
            return
        self._finish_landing_flow(state, player)

    def _finish_landing_flow(self, state: GameState, player: Player):
        if state.game_over:
            return
        if player.pending_double_action:
            player.pending_double_action = False
            self._log(state, f"🚀 {player.name} dùng Booster, được tung xúc xắc thêm lần nữa!")
            self._push_event(state, "booster", f"{player.name} được đi tiếp!")
            return
        self._advance_turn(state)

    def _advance_turn(self, state: GameState):
        state.turn_count += 1
        n = len(state.players)
        idx = state.current_player_index
        for _ in range(n):
            idx = (idx + 1) % n
            if not state.players[idx].finished:
                state.current_player_index = idx
                return
        state.game_over = True

    # ------------------------------------------------------------------
    # GIẢI QUYẾT HÀNH ĐỘNG CHỜ (ngã ba / bài sự kiện / bài bẫy)
    # ------------------------------------------------------------------
    def resolve_pending(self, code: str, player_id: int, choice: dict) -> GameState:
        state = self._get(code)
        pa = state.pending_action
        if not pa:
            raise GameError("Không có hành động nào đang chờ xử lý.")

        actor_id = pa.get("player_id") or pa.get("acting_player_id")
        if actor_id != player_id:
            raise GameError("Đây không phải lựa chọn của bạn.")

        if pa.get("kind") == "direction_choice":
            target = choice.get("target")
            if target not in pa["options"]:
                raise GameError("Hướng đi không hợp lệ.")
            player = self._find_player(state, pa["player_id"])
            player.position = target
            state.pending_action = None
            pm = state.pending_move
            if pm:
                pm["path"].append(target)
                pm["remaining_steps"] -= 1
            self._advance_move(state)
            return state

        card = pa["card"]
        player = self._find_player(state, pa["acting_player_id"])
        state.pending_action = None
        self._apply_card_effect(state, player, card, choice)
        if not state.game_over:
            self._post_landing_checks(state, player)
        return state

    # ------------------------------------------------------------------
    # CỬA HÀNG CỦA GÃ HỀ (fix bug: so sánh kiểu ItemType đúng, kiểm tra đủ điều kiện trước khi trừ tiền)
    # ------------------------------------------------------------------
    def buy_item(self, code: str, player_id: int, item_type: str) -> GameState:
        state = self._get(code)
        player = self._validate_turn(state, player_id)
        if not state.pending_shop_tile:
            raise GameError("Bạn không ở trạm mua sắm.")
        try:
            item = ItemType(item_type)
        except ValueError:
            raise GameError("Vật phẩm không tồn tại.")
        if state.item_stock.get(item, 0) <= 0:
            raise GameError("Vật phẩm đã hết hàng trong kho.")
        if len(player.items) >= MAX_ITEMS_CARRIED:
            raise GameError(f"Bạn đã mang tối đa {MAX_ITEMS_CARRIED} vật phẩm.")
        price = ITEM_INFO[item]["price"]
        if player.gold < price:
            raise GameError("Không đủ vàng để mua vật phẩm này.")

        player.gold -= price
        state.common_fund += price
        state.item_stock[item] -= 1
        player.items.append(item)
        self._log(state, f"🛒 {player.name} mua {ITEM_INFO[item]['emoji']} {ITEM_INFO[item]['name']} với {price} vàng.")
        self._push_event(state, "shop_buy", f"{player.name} mua {ITEM_INFO[item]['name']}!",
                          data={"item": item.value})
        return state

    def skip_shop(self, code: str, player_id: int) -> GameState:
        state = self._get(code)
        player = self._validate_turn(state, player_id)
        if not state.pending_shop_tile:
            raise GameError("Bạn không ở trạm mua sắm.")
        state.pending_shop_tile = False
        self._log(state, f"{player.name} rời trạm mua sắm, không mua gì.")
        self._finish_landing_flow(state, player)
        return state

    # ------------------------------------------------------------------
    # DÙNG VẬT PHẨM
    # ------------------------------------------------------------------
    def use_item(self, code: str, player_id: int, item_type: str, target_id=None, delta=None) -> GameState:
        state = self._get(code)
        if state.game_over or not state.game_started:
            raise GameError("Ván đấu chưa sẵn sàng.")
        if state.pending_action:
            raise GameError("Đang có hành động khác chờ xử lý.")
        if state.pending_move:
            raise GameError("Đang giữa lượt di chuyển, chưa thể dùng vật phẩm.")
        player = self._find_player(state, player_id)
        if not player:
            raise GameError("Người chơi không tồn tại.")
        if state.players[state.current_player_index].id != player_id:
            raise GameError("Chưa đến lượt của bạn.")
        try:
            item = ItemType(item_type)
        except ValueError:
            raise GameError("Vật phẩm không hợp lệ.")
        if item not in player.items:
            raise GameError("Bạn không sở hữu vật phẩm này.")

        if item == ItemType.XUC_XAC_X2:
            player.pending_double_roll = True
            self._log(state, f"🎲 {player.name} kích hoạt Xúc Xắc Song Sinh cho lượt tới.")
        elif item == ItemType.LA_CHAN:
            player.shield_charges += 1
            self._log(state, f"🛡️ {player.name} trang bị Lá Chắn Từ Trường.")
        elif item == ItemType.DAO_GAM:
            target = self._find_player(state, target_id)
            if not target or target.id == player.id:
                raise GameError("Mục tiêu không hợp lệ.")
            if abs(target.position - player.position) > 3:
                raise GameError("Mục tiêu phải trong bán kính 3 ô.")
            if self._consume_shield(target):
                self._log(state, f"🛡️ {target.name} dùng Lá Chắn chặn Tia Đẩy Lực!")
            else:
                target.position = max(START_TILE, target.position - 4)
                self._log(state, f"🔫 {player.name} bắn Tia Đẩy Lực, đẩy lùi {target.name} về ô {target.position}.")
                self._push_event(state, "push_back", f"{target.name} bị đẩy lùi 4 ô!")
        elif item == ItemType.BUA_HO_MENH:
            player.pending_double_action = True
            self._log(state, f"🚀 {player.name} kích hoạt Booster, sẽ được đi 2 lần liên tiếp.")
        elif item == ItemType.KINH_AP_TRONG:
            if delta not in (1, -1):
                raise GameError("Delta phải là +1 hoặc -1.")
            player.pending_lens_delta = delta
            self._log(state, f"👁️ {player.name} chỉnh Kính Định Vị ({delta:+d}) cho lượt tung xúc xắc tới.")
        else:
            raise GameError("Vật phẩm chưa hỗ trợ.")

        player.items.remove(item)
        self._push_event(state, "use_item", f"{player.name} dùng {ITEM_INFO[item]['name']}!",
                          data={"item": item.value})
        return state

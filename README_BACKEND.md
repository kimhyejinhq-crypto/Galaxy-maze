# Space Pathfinders - Backend (Đợt 1/2)

## Đã làm trong đợt này
1. **Mê cung thật**: mỗi ô có 1 hoặc 2 hướng đi (`connections` trong Tile). Khi gặp ô 2 hướng,
   client phải gọi `resolve_pending` với `{"choice": {"target": <ô đích>}}` để chọn hướng.
2. **4 nhân vật**: THO (Trang - Thỏ), CANH_CUT (Quang - Cánh cụt), CAO (Thành - Cáo), QUA (Jin - Quạ).
   Chọn nhân vật khi tạo phòng / vào phòng, không ai được trùng nhân vật.
3. **Sửa bug cửa hàng**: lỗi cũ do so sánh sai kiểu dữ liệu vật phẩm (string vs Enum) khiến
   luôn báo lỗi/không trừ đúng tiền. Đã test: mua đủ tiền → OK, không đủ tiền → báo lỗi rõ ràng,
   hết hàng → báo lỗi, tối đa 2 vật phẩm mang theo.
4. **Multiplayer thật qua Socket.IO**: nhiều người ở nhiều máy/nơi khác nhau cùng vào 1 "phòng"
   bằng mã code 5 ký tự, mọi hành động của ai đó được đẩy (emit) tới TẤT CẢ người trong phòng
   ngay lập tức - không cần bấm refresh hay chờ polling.
5. **Hệ thống popup sự kiện** (`events_feed` trong state, mỗi item có `kind` + `text` + `data`) -
   đây chính là "móc nối" để đợt 2 (frontend) hiển thị popup giữa màn hình, animation rút bài
   tarot, roulette xúc xắc... `kind` hiện có: dice_roll, branch, shop, shop_buy, draw_event,
   draw_trap, gold_gain, danger, steal, warp, toll, trap_reverse, shield_block, push_back,
   booster, skip_turn, game_start, game_over, use_item.

## Cách chạy thử
```bash
pip install -r requirements.txt
python app.py
```
Mở nhiều tab trình duyệt trỏ tới `http://localhost:5000` để test nhiều người chơi trên 1 máy.
Muốn bạn bè ở NƠI KHÁC chơi cùng thật sự, cần deploy lên Render/Railway/Fly.io (có domain public)
rồi chia sẻ link + mã phòng.

## API chính (Socket.IO events, gửi kèm `room_code` + `player_id`)
- `join` — vào phòng Socket.IO để nhận cập nhật
- `start_game`
- `roll_dice`
- `resolve_pending` — kèm `choice` (xem game_engine.py để biết format cho từng loại bài)
- `buy_item` — kèm `item_type`
- `skip_shop`
- `use_item` — kèm `item_type`, `target_id`, `delta` (tuỳ vật phẩm)

REST (chỉ dùng cho bước vào phòng ban đầu):
- `POST /api/create_room` `{name, character}`
- `POST /api/join_room` `{room_code, name, character}`
- `GET /api/state/<room_code>`
- `GET /api/characters`

## Việc còn lại (Đợt 2 - mình gửi tin nhắn tiếp theo)
- Giao diện chọn nhân vật + tạo/vào phòng
- Theme phi hành gia vũ trụ (thay Pastel Circus)
- Popup thông báo giữa màn hình cho mọi hành động
- Animation rút bài kiểu tarot (bài sự kiện/bẫy) + animation xúc xắc kiểu roulette
- Animation nhân vật di chuyển từng ô mượt (không "tele" tới thẳng ô đích)
- Camera chỉ theo người chơi hiện tại
- Nút hướng dẫn luật chơi ở góc màn hình
- Kết nối Socket.IO client (thay toàn bộ fetch() cũ trong scripts.js)

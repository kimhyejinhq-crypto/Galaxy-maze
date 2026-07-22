# SPACE PATHFINDERS — Bản Hoàn Chỉnh

Game cờ mê cung vũ trụ nhiều người chơi thời gian thực, chủ đề phi hành gia.

## Đã làm những gì (đầy đủ mọi yêu cầu)

1. **Multiplayer thật, nhiều máy / nhiều nơi khác nhau** — dùng Socket.IO thật (không
   phải fetch API đơn thuần). Tạo phòng ra mã 5 ký tự, người khác nhập mã để vào; mọi
   hành động được đẩy real-time cho tất cả người trong phòng ngay lập tức.
2. **Chọn nhân vật đầu game**: 🐰 Trang (Thỏ), 🐧 Quang (Cánh Cụt), 🦊 Thành (Cáo),
   🐦‍⬛ Jin (Quạ) — không ai được chọn trùng nhân vật.
3. **Popup thông báo giữa màn hình** cho MỌI hành động (tung xúc xắc, nhặt vàng, gặp
   nguy hiểm, dịch chuyển, mua đồ, dùng vật phẩm...) — không còn cảm giác chỉ click
   chuột im lặng.
4. **Rút bài kiểu Tarot thật**: modal lật bài 3D (mặt sau bí ẩn → lật sang mặt trước lộ
   tên + hiệu ứng), viền tím cho Sự Kiện, viền đỏ cho Bẫy.
5. **Xúc xắc kiểu roulette**: quả cầu xoay, mặt số nhảy loạn trước khi dừng ở kết quả
   thật (kết quả đã được server tính công bằng từ trước, phần xoay chỉ là hiệu ứng
   hồi hộp).
6. **Cửa hàng Gã Hề đã sửa xong và mua được**: lỗi cũ do so sánh sai kiểu dữ liệu vật
   phẩm; đã test mua đủ tiền / thiếu tiền / hết hàng / vượt quá 2 món đều báo đúng.
7. **Màu ô khớp 100% giữa bàn cờ và phần hướng dẫn** — cùng một class CSS dùng chung
   cho cả ô thật trên bàn và ô minh hoạ trong Sổ Tay Phi Hành Gia.
8. **Nút Hướng Dẫn (📖)** ở góc thanh HUD trên cùng — giải thích ý nghĩa từng màu ô,
   ngã ba, chợ phiên, cách điều khiển.
9. **Theme phi hành gia vũ trụ** hoàn toàn mới: nền tinh vân + sao lấp lánh chuyển
   động thật (canvas), khung HUD góc bo kim loại phát sáng, chữ Orbitron/monospace
   phong cách trạm chỉ huy liên ngân hà.
10. **Bàn cờ dạng mê cung thật**: một số ô có 2 hướng đi (ngã ba không gian, viền vàng
    nhấp nháy), người chơi phải chọn hướng khi dừng đúng ô đó giữa lượt di chuyển.
11. **Camera chỉ theo người đang chơi**: khung nhìn (viewport) có kính che góc (vignette)
    tối các cạnh, tự động lia mượt tới vị trí người chơi hiện tại — không thấy toàn bộ
    bản đồ, tạo cảm giác kịch tính.
12. **Nhân vật di chuyển từng ô có animation mượt**, đi theo đúng đường nối thật trên
    bản đồ (không còn "tele" thẳng đến ô theo số xúc xắc); nếu là cổng dịch chuyển thì
    có hiệu ứng warp riêng.

## Cách chạy

```bash
cd space-pathfinders
pip install -r requirements.txt
python app.py
```

Mở nhiều tab trình duyệt tới `http://localhost:5000` để test nhiều người chơi trên
cùng một máy.

**Để bạn bè ở NƠI KHÁC (nhà khác, mạng khác) chơi cùng thật sự**, bạn cần deploy server
này lên một dịch vụ hosting chạy liên tục có domain public, ví dụ Render, Railway, hoặc
Fly.io (đều có gói miễn phí phù hợp cho project nhỏ). Chạy trên máy cá nhân (localhost)
thì chỉ những người cùng mạng Wi-Fi/LAN mới truy cập được.

## Cấu trúc file

```
space-pathfinders/
├── app.py                  # Flask + Socket.IO server, route tĩnh, mọi socket event
├── requirements.txt
├── backend/
│   ├── __init__.py
│   ├── constants.py        # Enum ô, nhân vật, vật phẩm, bài Sự Kiện/Bẫy
│   ├── models.py           # Cấu trúc dữ liệu Tile/Player/GameState
│   └── game_engine.py      # Toàn bộ luật chơi: mê cung, phòng, cửa hàng, bài...
└── frontend/
    ├── index.html          # Toàn bộ màn hình: setup, lobby, game, các modal
    ├── style.css           # Theme phi hành gia vũ trụ
    └── scripts.js          # Socket.IO client, render, animation
```

## Vài lưu ý kỹ thuật quan trọng

- Server dev hiện chạy bằng `python app.py` (Werkzeug dev server) — đủ để test, nhưng
  khi deploy thật lên hosting, nên chạy qua `gunicorn` với worker hỗ trợ WebSocket
  (ví dụ `gunicorn --worker-class eventlet -w 1 app:app`) để Socket.IO hoạt động ổn
  định với nhiều người dùng cùng lúc.
- State ván đấu hiện lưu trong bộ nhớ (RAM) của server, nghĩa là nếu server restart,
  các phòng đang chơi sẽ mất. Với quy mô chơi bạn bè thông thường thì không vấn đề gì,
  nhưng nếu sau này muốn "cứng" hơn (chịu được restart), có thể lưu state ra Redis/DB.
- Icon nhân vật dùng emoji hệ thống, hiển thị hơi khác nhau một chút tuỳ trình duyệt/
  hệ điều hành của mỗi người chơi — đây là giới hạn chung của emoji, không phải bug.

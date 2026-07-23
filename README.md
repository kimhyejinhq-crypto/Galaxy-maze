# SPACE PATHFINDERS — Bản Hoàn Chỉnh

Game cờ mê cung vũ trụ nhiều người chơi thời gian thực, chủ đề phi hành gia.

## 🆕 SỬA LẦN NÀY — Chặn bấm dồn dập + công cụ kiểm tra Redis

1. **SỬA LỖI THẬT: bấm nút "Khởi động tên lửa" nhiều lần gửi nhiều request cùng lúc.**
   Trước đây nút KHÔNG bị khoá trong lúc đang chờ server phản hồi, nên khi server
   phản hồi chậm (thường do Render đang "thức dậy"), người chơi sốt ruột bấm thêm ->
   gửi 2-3 request `join_room`/`create_room` chồng nhau, gây lỗi khó hiểu. Đã sửa:
   - Bấm 1 lần -> nút tự khoá NGAY, đổi chữ thành "ĐANG KẾT NỐI TỚI TRẠM..." kèm icon
     xoay tròn.
   - Bấm thêm trong lúc đang chờ -> bị chặn hoàn toàn, không gửi thêm request nào.
   - Nếu thất bại -> nút tự mở khoá lại để thử lần nữa, kèm thông báo lỗi rõ ràng
     (có gợi ý "server có thể đang khởi động lại, thử lại sau vài giây").
   - Đã tự kiểm tra bằng mô phỏng: bấm 4 lần liên tiếp trong lúc server "chậm" ->
     chỉ đúng 1 request được gửi đi.

2. **Thêm endpoint `/api/health` để TỰ KIỂM TRA xem Redis có đang hoạt động thật
   không** — mở thẳng trên trình duyệt: `https://<link-render-của-bạn>/api/health`.
   Sẽ thấy:
   ```json
   { "success": true, "using_redis": true/false, "redis_error": null hoặc lý do lỗi,
     "active_rooms": số phòng đang mở, "pid": mã tiến trình hiện tại }
   ```
   - `"using_redis": false` trên Render → phòng chơi SẼ vẫn bị mất khi container
     restart/nhiều instance, y hệt lỗi trước đây. Cần quay lại kiểm tra biến môi
     trường `REDIS_URL` trong Render Dashboard → Environment (xem phần Redis bên
     dưới) — rất có thể bước này chưa được lưu đúng hoặc chưa deploy lại sau khi
     thêm biến.
   - Refresh `/api/health` vài lần cách nhau vài phút, nếu thấy `"pid"` liên tục
     đổi số dù bạn không deploy lại gì — đó là bằng chứng container đang tự khởi
     động lại (đúng nguyên nhân gây mất phòng).
   - Server cũng tự in dòng log rõ ràng lúc khởi động (✅ kết nối Redis thành công /
     ⚠️ không có REDIS_URL / ⚠️ có REDIS_URL nhưng không kết nối được) - xem trong
     Render Dashboard → Logs để xác nhận.

---

## 🆕 SỬA LẦN NÀY — Cửa hàng, bài Tarot, bản đồ

1. **Bỏ giới hạn tối đa 2 vật phẩm** — giờ mua thoải mái tới khi hết vàng, đúng như
   bạn yêu cầu. Chỉ bị giới hạn bởi vàng bạn có và hàng còn trong kho.
2. **SỬA LỖI THẬT khiến cửa hàng "đứng hình"**: khi bạn rút bài Sự Kiện/Bẫy đúng lúc
   dừng ở ô cửa hàng (ví dụ bài di chuyển thêm khiến bạn dừng đúng ô 20/50/80), modal
   lật bài Tarot (nằm ở lớp trên cùng màn hình) che mất modal cửa hàng NGAY BÊN DƯỚI —
   bấm Mua/Skip lúc đó bị bài Tarot "nuốt mất" click, không có phản hồi gì, làm bạn
   tưởng game bị đứng. Đã sửa: cửa hàng giờ đợi bài Tarot đọc xong mới hiện ra, không
   còn bị đè nữa. Đã tự kiểm tra bằng test mô phỏng đúng tình huống này — xác nhận
   sửa đúng.
3. **Bài Tarot không tự đóng vội nữa** — giờ có nút "ĐÃ ĐỌC XONG — TIẾP TỤC" để bạn
   chủ động đóng khi đọc xong, có hẹn giờ tự đóng dự phòng sau 12 giây (thay vì 2.2
   giây như trước) nếu bạn quên bấm.
4. **Bản đồ to hơn**: khung nhìn (viewport) tăng từ 720px lên 960px.
5. **Thêm 2 chế độ xem bản đồ** — nút "🎯 THEO DÕI NGƯỜI CHƠI" (camera bám theo người
   đang chơi, chế độ cũ) và "🔭 TOÀN CẢNH BẢN ĐỒ" (thu nhỏ để thấy toàn bộ 100 ô cùng
   lúc) — chuyển đổi bất kỳ lúc nào bằng 2 nút phía trên bàn cờ.
6. Thêm hiển thị rõ "Không đủ vàng" / "Hết hàng trong kho" ngay trên từng món đồ trong
   cửa hàng, và số vàng hiện có ở đầu cửa hàng — để không còn nhầm "nút mờ = bug" nữa.

---

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

## ⚠️ SỬA LỖI "KHÔNG TÌM THẤY PHÒNG" TRÊN RENDER (đọc kỹ trước khi deploy)

### Nguyên nhân thật sự

Bản trước lưu dữ liệu phòng chơi trong RAM của tiến trình server. Vấn đề: Render có
thể chạy **nhiều container song song** hoặc **khởi động lại container** (kể cả khi
server "ngủ" do không ai dùng ~15 phút). Mỗi container có RAM RIÊNG — phòng tạo ở
container A thì container B (nhận request tiếp theo, kể cả của chính người tạo phòng)
hoàn toàn không biết gì về nó → báo "không tìm thấy phòng". Đây là lý do dù đã sửa
lệnh khởi động (Procfile) ở lần trước, lỗi vẫn còn — vì bản chất vấn đề nằm ở việc dữ
liệu chỉ tồn tại trong 1 container, chứ không phải do lệnh khởi động sai nữa.

### Cách sửa (đã làm, đã test thật)

Server giờ dùng **Redis** — một kho dữ liệu dùng chung nằm NGOÀI mọi container. Dù
Render chạy bao nhiêu container, dù container có bị khởi động lại, phòng chơi vẫn
còn nguyên vì không nằm trong RAM của container nữa.

Mình đã tự kiểm tra bằng cách giả lập đúng tình huống lỗi: tạo 4 tiến trình Python
hoàn toàn tách biệt (y hệt 4 container khác nhau) rồi cho chúng lần lượt tạo phòng /
vào phòng / chơi — chạy mượt, không còn lỗi. Cũng đã chạy thử với Gunicorn 3 worker
(giả lập trường hợp xấu nhất) + Redis thật, tạo phòng - kiểm tra state - vào phòng
đều thành công 100%.

**Nếu KHÔNG cấu hình Redis, code vẫn tự động chạy được bằng RAM như cũ** (để bạn test
ở máy cá nhân cho tiện) — nhưng để chơi ổn định qua Render, bạn PHẢI làm theo các
bước dưới đây.

### Các bước bắt buộc để chơi được trên Render

**Bước 1 — Tạo Redis miễn phí trên Upstash** (mất khoảng 2 phút):
1. Vào https://upstash.com → đăng ký tài khoản miễn phí (dùng GitHub cho nhanh).
2. Bấm **Create Database** → đặt tên tuỳ ý → chọn region gần Render nhất (ví dụ
   Singapore hoặc Oregon tuỳ bạn deploy Render ở đâu) → Create.
3. Vào database vừa tạo, tìm phần **"Connect"** hoặc **REST API / Redis URL** →
   copy chuỗi bắt đầu bằng `rediss://` (LƯU Ý: có 2 chữ "s", nghĩa là kết nối bảo
   mật TLS — bắt buộc phải dùng đúng chuỗi này).

**Bước 2 — Gắn Redis URL vào Render**:
1. Vào Render Dashboard → chọn service game của bạn → **Environment**.
2. Bấm **Add Environment Variable**:
   - Key: `REDIS_URL`
   - Value: dán chuỗi `rediss://...` vừa copy ở Upstash
3. Save Changes.

**Bước 3 — Push code mới và deploy lại**:
1. Push toàn bộ code trong file zip này lên GitHub repo của bạn (đè lên code cũ).
2. Vào Render → **Manual Deploy → Clear build cache & deploy** (để chắc chắn không
   dùng cache cũ).
3. Xác nhận **Start Command** vẫn đang dùng đúng (để trống để Render tự đọc
   `Procfile`, hoặc nhập tay):
   ```
   gunicorn --worker-class gthread --workers 1 --threads 8 --timeout 120 app:app
   ```

Sau bước này, dù Render chạy nhiều container/instance, dù server ngủ rồi thức dậy,
phòng chơi sẽ luôn còn nguyên vì đã nằm ở Redis (Upstash), không còn phụ thuộc vào
container nào cả.

### Vì sao lần load ĐẦU TIÊN sau một lúc không ai vào vẫn hơi chậm

Đây là đặc điểm của gói Render **miễn phí**: server "ngủ" sau ~15 phút không có
traffic, lần truy cập đầu tiên sau đó mất khoảng 30–60 giây để "đánh thức" — đây là
giới hạn của gói free, không phải lỗi code, và không ảnh hưởng tới việc mất phòng nữa
(vì phòng đã ở Redis, không ở RAM container). Nếu muốn loại bỏ luôn độ trễ đánh thức
này, cần nâng cấp gói trả phí của Render, hoặc dùng dịch vụ ping định kỳ (UptimeRobot)
gọi vào link mỗi 10 phút để giữ server không ngủ.

---

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

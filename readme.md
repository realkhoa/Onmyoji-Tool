# 🎮 Onmyoji Bot

Bot tự động cho game **陰陽師 Onmyoji** — điều khiển qua ngôn ngữ script DSL.

---

## ✨ Tính năng

- 🔍 **Tự động attach** cửa sổ game — không cần cài đặt, mở lên là dùng
- 🖼 **Preview màn hình** game trực tiếp trong tool (hover để xem tọa độ X/Y)
- 📜 **DSL scripting** — viết script automation dễ đọc, dễ chỉnh
- 🔎 **Template matching đa tỷ lệ** — nhận dạng ảnh dù game chạy ở resolution nào

---

## 🚀 Cài đặt & Chạy

> Khuyến nghị dùng **conda** hoặc **venv** để tránh xung đột package.

```bash
# Tạo môi trường
conda create -n bot-onmyoji python=3.11
conda activate bot-onmyoji

# Cài dependencies
pip install -r requirements.txt
```

### Chạy tool

```bash
# Tool chính – thân thiện, 1 nút dùng luôn
python ui_tools.py

# Tool dev – đầy đủ tính năng, có script editor
python ui_main.py
```

---

## 📜 DSL Script Reference

Script viết trong file `.dsl` hoặc `.txt`. Dòng bắt đầu bằng `#` là comment.

### Chuột & Bàn phím

| Lệnh | Mô tả |
|---|---|
| `click X Y` | Click trái tại tọa độ (X, Y) |
| `rclick X Y` | Click phải |
| `dclick X Y` | Double click |
| `move X Y` | Di chuyển chuột |
| `drag X1 Y1 X2 Y2` | Kéo thả |
| `drag_to('img1.png', 'img2.png', [THRESHOLD])` | Kéo từ vị trí ảnh 1 tới ảnh 2 |
| `drag_offset('img.png', DX, DY)` | Tìm ảnh, kéo từ tâm ảnh đến điểm (tâm + DX, DY) |
| `scroll N` | Cuộn bánh xe chuột theo số ticks (120 = 1 notch) |
| `key KEYNAME` | Nhấn phím (`enter`, `space`, `f1`…) |
| `type "text"` | Gõ chuỗi ký tự |

### Thời gian

| Lệnh | Mô tả |
|---|---|
| `wait(1.5)` | Chờ 1.5 giây |
| `wait_random(1, 3)` | Chờ ngẫu nhiên từ 1–3 giây |

### Nhận dạng ảnh

Đặt ảnh template vào thư mục `images/`, threshold từ 0.0–1.0 (mặc định 0.8).

| Lệnh | Mô tả |
|---|---|
| `find_and_click('btn.png')` | Tìm ảnh và click vào giữa |
| `find_and_click('a.png', 'b.png', 0.85)` | Tìm nhiều ảnh, click cái nào thấy trước |
| `wait_for('img.png')` | Chờ vô hạn cho đến khi thấy ảnh |
| `wait_for('img.png', 30)` | Chờ tối đa 30 giây |
| `wait_and_click('img.png')` | Chờ rồi click |
| `exists('img.png', 0.85)` | Kiểm tra ảnh có trên màn hình (dùng trong `if`)

> Các điều kiện có thể nối với `and`/`or` (và tiền tố `not`) để tạo biểu thức đơn giản. Ngôn ngữ hiện tại sử dụng cú pháp biểu thức giống Python – bạn có thể viết phép toán, so sánh, gọi hàm `exists('img.png')`, `rand()`, `min()`, `max()` v.v. Các biến số cũng có thể dùng trực tiếp trong biểu thức (0=false, khác 0=true).
> ```dsl
> set ok 0
> set counter 0
> set x counter + 1        # biểu thức Python, phép toán và biến
>
> if ok {
>   log "ok là true"
> }
>
> if counter >= 5 and not done {
>   log "chưa xong"
> }
>
> if exists('a.png') or ready == True {
>   # ...
> }
> ```
> Phép toán đánh giá theo quy tắc Python (có ngoặc, toán tử ưu tiên).

| `exists_exact('img.png')` | Kiểm tra theo màu (không grayscale, chính xác hơn) |
| `count('VAR', 'img.png')` | Đếm số lần ảnh xuất hiện, lưu vào biến `VAR` |

### Điều khiển luồng

```dsl
# Vòng lặp có đếm
loop 10 {
  click 500 300
  wait(1)
}

# Vòng lặp vô hạn
loop forever {
  find_and_click('btn.png')
  wait(2)
}

# Rẽ nhánh
if exists('win.png') {
  log "Thắng rồi!"
} elif exists('lose.png') {
  log "Thua rồi..."
} else {
  wait(1)
}

# Do...until (chạy ít nhất 1 lần)
do {
  find_and_click('attack.png')
  wait(2)
} until exists('victory.png')

# Biến & toán tử
Các biến là số thực và có thể sử dụng biểu thức Python khi gán/so sánh.

```dsl
counter = 0             # gán giá trị
counter += 1            # tăng 1
x = (counter * 3) + 2   # biểu thức phức tạp
```

if counter >= 10 {
  log "Đã farm 10 lần"
}

# Goto / Label
start:
  click 500 300
  wait(1)
  if exists('done.png') {
    goto finish
  }
  goto start

finish:
  log "Xong!"
```

### Tiện ích

| Lệnh | Mô tả |
|---|---|
| `log "message"` | In thông báo ra log |
| `resize 1920 1080` | Resize cửa sổ game về 1920×1080 |

---

## 🖼 Thêm ảnh template

1. Chụp màn hình game (dùng preview trong tool để xem tọa độ)
2. Crop đúng phần muốn nhận dạng
3. Lưu vào thư mục `images/` với tên `.png`
4. Dùng tên file trong script: `find_and_click('ten_anh.png')`

> Template matching hỗ trợ đa tỷ lệ — chụp ở resolution nào cũng match được.

---

## 📋 Requirements

```
opencv-python
numpy
pywin32
PyQt5
psutil
keyboard
mss
```

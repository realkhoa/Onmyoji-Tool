# PPS Engine Command Reference

Tài liệu này hướng dẫn chi tiết các lệnh (commands) và cú pháp của `pps_engine` dùng trong các script tự động hóa.

## 1. Cú pháp chung (General Syntax)

- **Không phân biệt hoa thường**: `click`, `CLICK`, `Click` đều hợp lệ.
- **Linh hoạt về định dạng**: Engine hỗ trợ cả cú pháp lệnh thuần túy và cú pháp giống hàm lập trình.
    - Dạng lệnh: `click 100 200`
    - Dạng hàm: `click(100, 200)`
- **Comment**: Sử dụng dấu `#` để bắt đầu một dòng chú thích. Dòng này sẽ bị engine bỏ qua.
- **Chuỗi ký tự (Strings)**: Có thể bao quanh bằng dấu nháy đơn `'...'` hoặc nháy kép `"..."`.

---

## 2. Các lệnh tương tác (Interaction Commands)

### Chuột (Mouse)
- `click x y`: Click chuột trái vào tọa độ (x, y).
- `rclick x y`: Click chuột phải vào tọa độ (x, y).
- `dclick x y`: Double click chuột trái vào tọa độ (x, y).
- `move x y`: Di chuyển chuột đến tọa độ (x, y).
- `drag x1 y1 x2 y2`: Kéo thả từ (x1, y1) đến (x2, y2).
- `scroll amount`: Cuộn chuột (giá trị dương cuộn lên, âm cuộn xuống).

### Bàn phím (Keyboard)
- `key name`: Nhấn một phím (ví dụ: `key enter`, `key esc`).
- `type "text"`: Nhập một chuỗi ký tự.

#### Ví dụ tương tác:
```
# Click vào nút Bắt đầu
click 960 540

# Kéo thả vật phẩm
drag 400 300 800 300

# Nhập tên nhân vật và nhấn Enter
click 500 500
type "MyHero"
key enter
```


---

## 3. Các lệnh Vision (Hình ảnh)

Các lệnh này dựa trên việc tìm kiếm template hình ảnh trong thư mục `images/`.

- `find_and_click image1 image2 ... [threshold]`: Tìm các hình ảnh theo thứ tự, nếu thấy hình nào thì click vào hình đó và dừng lại. `threshold` mặc định là 0.8.
- `wait_for image1 image2 ... [timeout]`: Đợi cho đến khi một trong các hình ảnh xuất hiện hoặc hết thời gian `timeout` (giây). Nếu `timeout` = 0 hoặc không có, sẽ đợi vô tận.
- `wait_and_click image1 image2 ... [timeout]`: Kết hợp của `wait_for` và `click`. Đợi hình xuất hiện rồi click vào nó.
- `count var image [threshold]`: Đếm số lượng hình ảnh xuất hiện trên màn hình và gán vào biến `var`.
- `drag_to image1 image2 [threshold]`: Tìm `image1` và `image2`, sau đó kéo từ tâm `image1` đến tâm `image2`.
- `drag_image image1 image2 [threshold]`: (Tương tự `drag_to`).
- `drag_offset image dx dy`: Tìm `image` và kéo từ tâm của nó đi một khoảng `(dx, dy)`.

### Lệnh chuyên biệt (Specialized Commands)
- `find_and_click_largest_shiki [dark_thresh]`: Tìm và click vào bóng thức thần (silhouette) lớn nhất. `dark_thresh` mặc định là 50.
- `throw_at_largest_shiki [delay_ms] [motion_thresh]`: Tìm và click vào vật thể đang di chuyển lớn nhất (dùng trong mini-game ném đậu).

#### Ví dụ Vision:
```
# Đợi nút 'Chấp nhận' xuất hiện trong 10 giây rồi click
wait_and_click "accept_btn.png" 10

# Nếu thấy 'win.png' thì click nút 'Next'
if exists("win.png") {
    click "next_btn.png"
}

# Đếm số lượng quái vật trên màn hình
count monster_count "slime.png" 0.7
log "Số lượng quái: " monster_count
```


---

## 4. Điều khiển luồng (Control Flow)

### Vòng lặp (Loops)
- `loop [n | "forever"] { ... }`: Lặp lại khối lệnh `n` lần hoặc lặp vô tận.
    - Kết thúc khối lệnh bằng `}` hoặc `end`.
- `do { ... } until condition`: Chạy khối lệnh cho đến khi điều kiện `condition` thỏa mãn (kiểm tra sau mỗi lần lặp).
- `break`: Thoát khỏi vòng lặp hiện tại.
- `continue`: Nhảy đến lần lặp kế tiếp của vòng lặp hiện tại.

### Điều kiện (Conditionals)
- `if condition { ... } elif condition { ... } else { ... }`: Cấu trúc rẽ nhánh.
    - Kết thúc bằng `}` hoặc `end`.
- `exists("image.png", [threshold])`: Kiểm tra xem hình ảnh có tồn tại không (dùng trong biểu thức).
- `exists_exact("image.png", [threshold])`: Kiểm tra hình ảnh với độ chính xác cao hơn (không scale).

### Nhãn và Nhảy (Labels & Goto)
- `label_name:`: Định nghĩa một nhãn.
- `goto label_name`: Nhảy đến vị trí nhãn đã định nghĩa.

#### Ví dụ Điều khiển luồng:
```
# Lặp lại 5 lần việc đánh quái
loop 5 {
    wait_and_click "attack_btn.png" 30
    wait 2
}

# Vòng lặp kiểm tra cho đến khi hết máu
do {
    click "heal_potion.png"
    wait 1
} until (health > 80)

# Dùng nhãn để tạo vòng lặp thủ công
start_battle:
    click "fight.png"
    wait 5
    if exists("victory.png") {
        goto end_script
    }
    goto start_battle

end_script:
    log "Trận đấu kết thúc"
```


---

## 5. Biến và Tính toán (Variables & Math)

- **Gán biến**:
    - `set var value`
    - `var = expression` (Cú pháp Python-like)
    - `var += value`, `var -= value`, v.v.
- **Toán tử**: `+`, `-`, `*`, `/`, `%` (chia lấy dư), `**` (lũy thừa).
- **So sánh**: `>`, `<`, `==`, `>=`, `<=`, `!=`.
- **Logic**: `and`, `or`, `not`.

### Các hàm có sẵn (Built-in Functions)
Sử dụng được trong các biểu thức hoặc lệnh `set`:
- `rand()`: Trả về số ngẫu nhiên từ 0 đến 1.
- `randint(min, max)`: Trả về số nguyên ngẫu nhiên trong khoảng `[min, max]`.
- `min(a, b)`, `max(a, b)`, `abs(x)`
- `math.sin()`, `math.cos()`, `math.floor()`, v.v. (tương đương module `math` của Python).

#### Ví dụ Biến & Toán học:
```
# Gán biến đơn giản
set gold 1000
price = 250

# Tính toán
total = price * 4
can_afford = (gold >= total)

# Dùng số ngẫu nhiên để click lệch một chút (tránh phát hiện)
x = 500 + randint(-5, 5)
y = 500 + randint(-5, 5)
click x y
```


---

## 6. Hàm tự định nghĩa (User Functions)

- **Định nghĩa**:
  ```
  function MyFunc arg1 arg2 {
      # các lệnh...
      return result
  }
  ```
- **Gọi hàm**: `MyFunc(10, 20)` hoặc `MyFunc 10 20`.
- **Kết quả trả về**: Sau khi gọi hàm, giá trị trả về được lưu vào biến đặc biệt `_return_`.

#### Cách lấy kết quả từ hàm:
Bạn có thể lấy giá trị trả về của hàm bằng hai cách:

1. **Gán trực tiếp (Khuyên dùng)**: Sử dụng dấu `=` hoặc lệnh `set`.
   ```
   # Gán trực tiếp khi gọi hàm
   result = CheckAndHeal(30)
   
   # Hoặc dùng set
   set has_healed CheckAndHeal(30)
   ```

2. **Dùng biến `_return_`**: Sau khi gọi hàm như một lệnh độc lập, kết quả sẽ tự động lưu vào `_return_`.
   ```
   # Gọi như một lệnh
   CheckAndHeal 30
   if _return_ == 1 {
       log "Đã dùng bình máu!"
   }
   ```

#### Ví dụ Hàm:
```
function CalculateDamage base_atk critical {
    damage = base_atk
    if critical == 1 {
        damage = base_atk * 1.5
    }
    return damage
}

# Sử dụng kết quả hàm trong biểu thức khác
final_dmg = CalculateDamage(100, 1) + 50
log "Tổng sát thương: " final_dmg
```


---

## 7. Các lệnh hệ thống khác

- `log "message" var1 var2`: In thông tin ra cửa sổ log. Có thể kết hợp chuỗi và biến.
- `wait seconds`: Tạm dừng script trong một khoảng thời gian (giây).
- `wait_random min max`: Tạm dừng script trong một khoảng ngẫu nhiên từ `min` đến `max`.
- `resize width height`: Thay đổi kích thước cửa sổ game (giả lập). mặc định 1920x1080.
- `return [value]`: Trả về giá trị từ một hàm.

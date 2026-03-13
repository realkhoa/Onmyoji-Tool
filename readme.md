# 🎮 Onmyoji Bot (Âm Dương Sư Bot)

Bot tự động đa năng dành cho game **陰陽師 Onmyoji** (bản Steam/Global). Tool giúp bạn tự động hóa các hoạt động lặp đi lặp lại một cách nhàn rỗi.

## ✨ Tính năng nổi bật

- 🔍 **Tự động nhận dạng** cửa sổ game — Không cần cài đặt đường dẫn hay cấu hình phức tạp, chỉ cần mở game và mở tool là tự kết nối.
- 🖼 **Theo dõi trực tiếp** — Có sẵn màn hình thu nhỏ trong tool để xem tool đang nhìn thấy gì, hỗ trợ hiển thị tọa độ X/Y chi tiết.
- 🧩 **Thông minh & Linh hoạt** — Hoạt động chính xác dù bạn thu phóng hay thu nhỏ (thu nhỏ thì chưa chắc) cửa sổ game. Hỗ trợ đa dạng tính năng: PvP, Phá kết giới, Ném đậu...

---
## LƯU Ý QUAN TRỌNG TRƯỚC KHI SỬ DỤNG
- KHÔNG ĐƯỢC THU NHỎ CỬA SỔ (Minimize) GAME KHI TOOL ĐANG CHẠY. THU NHỎ PHÁT LÀ TOOL KO CHẠY ĐƯỢC LUÔN
- ĐỔI SANG CỬA SỔ KHÁC DÙNG THÌ BÌNH THƯỜNG
---

## 🛠 Hướng dẫn Cài đặt

Vì đây là mã nguồn mở, bạn cần thực hiện một vài bước nhỏ để tải về và chạy lần đầu tiên. Đừng lo, các bước được thiết kế để ai cũng có thể làm được.

### Bước 1: Tải mã nguồn (Source Code)

1. Tải và cài đặt **Git** tại: [https://git-scm.com/downloads](https://git-scm.com/downloads) (cứ ấn Next liên tục là được).
2. Mở ứng dụng **Terminal** (hoặc Command Prompt / PowerShell) trên máy tính.
3. Chạy lệnh sau để tải source code về máy:
   ```bash
   git clone https://github.com/realkhoa/Onmyoji-Tool.git
   cd Onmyoji-Tool
   ```

### Bước 2: Cài đặt Môi trường chạy

Để tool chạy mượt mà, chúng ta cần cài đặt Python. Bạn có thể chọn 1 trong 2 cách dưới đây (Cách 1 khuyên dùng cho người mới):

#### Cách 1: Dùng Python chuẩn (`venv`) - Khuyên dùng

1. Tải và cài đặt **Python 3.11** (hoặc mới hơn) tại: [https://www.python.org/downloads/](https://www.python.org/downloads/).
   *(📌 **Lưu ý quan trọng**: Khi cài đặt, nhớ tích vào ô **"Add python.exe to PATH"** ở màn hình đầu tiên).*
2. Mở Terminal (trong thư mục `Onmyoji-Tool` vừa tải về), chạy lần lượt các lệnh:
   ```bash
   # Tạo môi trường ảo (để không ảnh hưởng tới máy)
   python -m venv venv

   # Kích hoạt môi trường ảo (trên Windows)
   venv\Scripts\activate

   # Cài đặt các thư viện cần thiết cho tool
   pip install -r requirements.txt
   ```

#### Cách 2: Dùng Anaconda / Miniconda (`conda`)

1. Cài đặt Anaconda hoặc Miniconda.
2. Mở chương trình **Anaconda Prompt**, di chuyển (lệnh `cd`) đến thư mục `Onmyoji-Tool`, chạy lệnh:
   ```bash
   # Tạo và kích hoạt môi trường conda
   conda create -n bot-onmyoji python=3.11
   conda activate bot-onmyoji

   # Cài đặt thư viện
   pip install -r requirements.txt
   ```

---

## 🚀 Hướng dẫn Sử dụng (Chạy Tool)

Sau khi cài đặt xong thư viện ở Bước 2, mỗi khi muốn dùng bot, bạn làm như sau:

1. **Mở game Onmyoji** trên máy tính (đợi game load xong vào màn hình chính).
2. Mở Terminal (hoặc Anaconda Prompt nếu dùng Cách 2) trong thư mục `Onmyoji-Tool`.
3. Kích hoạt môi trường (chỉ cần chạy 1 trong 2 lệnh tùy theo cách cài của bạn):
   - Đã cài Cách 1 (`venv`): `venv\Scripts\activate`
   - Đã cài Cách 2 (`conda`): `conda activate bot-onmyoji`
4. **Khởi động tool** bằng lệnh:
   ```bash
   python main.py
   ```
5. Trên giao diện tool hiện ra:
   - Chọn tab chứa chức năng bạn muốn (Ví dụ: ⚔ Phá kết giới guild).
   - Nhấn **▶ Bắt đầu** và thả tay khỏi chuột/bàn phím để theo dõi bot làm việc.
   - Nhấn **■ Dừng lại** bất cứ lúc nào bạn muốn lấy lại quyền điều khiển.

---

## 📚 Dành cho lập trình viên (Advanced / Power Users)

Bot hoạt động dựa trên một ngôn ngữ kịch bản cực kỳ linh hoạt (DSL). Quản trị viên và người dùng nâng cao có thể tự viết các đoạn mã auto của riêng mình.

- Xem cú pháp và chức năng chuyên sâu tại: [📖 Hướng dẫn viết DSL Script (dsl_references.md)](dsl_references.md)
- Để hiển thị giao diện nâng cao có tích hợp công cụ soạn thảo, hãy tìm trong cái tool ấy, t tích hợp sẵn r

---

## 📋 Yêu cầu hệ thống cơ bản
*Tự cài qua `requirements.txt`*
- `opencv-python`, `numpy`, `pywin32`, `PyQt6`, `psutil`, `keyboard`, `mss`.

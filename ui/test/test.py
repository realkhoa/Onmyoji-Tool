import cv2
import numpy as np

img = cv2.imread("image.png")
if img is None:
    print("Không tìm thấy file image.png")
    exit()

# Cắt lấy nguyên 2/3 nửa dưới của ảnh
h, w = img.shape[:2]
img = img[h//3:h, :]

# Bỏ 1/10 dưới cùng của phần vừa cắt (chỉ giữ lại 9/10 phần trên của nó)
h_cut = img.shape[0]
img = img[:(h_cut * 8) // 10, :]

# Lọc màu đen thật sự dựa trên các kênh màu BGR
# Các giá trị Blue, Green, Red đều phải nằm trong khoảng từ 0 đến 50
lower_black = np.array([0, 0, 0], dtype=np.uint8)
upper_black = np.array([50, 50, 50], dtype=np.uint8) # Bạn có thể giảm giá trị 50 này xuống 30 nếu hình vẫn dính màu tối khác

# mask sẽ có giá trị 255 tại những pixel thoả mãn màu đen
mask = cv2.inRange(img, lower_black, upper_black)

# Lúc này mask chứa giá trị 255 ở những pixel màu đen theo điều kiện inRange
# Lọc bỏ các màu không phải màu đen (đổi thành màu trắng cho nền)
result = np.full_like(img, 255)

h_res, w_res = result.shape[:2]
part_w = w_res // 3
counts = []

# Chia làm 3 phần theo chiều ngang để đếm pixel đen
for i in range(3):
    x1 = i * part_w
    x2 = (i + 1) * part_w if i < 2 else w_res
    roi = mask[:, x1:x2]
    black_pixels = cv2.countNonZero(roi)
    counts.append(black_pixels)

best_idx = np.argmax(counts)

# Tô đen hẳn các pixel thuộc mask của ảnh gốc
result[mask == 255] = [0, 0, 0]

# Tạo một lớp phủ (overlay) để tô mờ màu đỏ cho 1/3 vùng chứa nhiều đen nhất
overlay = result.copy()
x1 = best_idx * part_w
x2 = (best_idx + 1) * part_w if best_idx < 2 else w_res

# Tô đỏ vào toàn bộ 1/3 vùng này (cả ô chữ nhật chứa nó)
overlay[:, x1:x2] = (0, 0, 255)

# Trộn lớp overlay dội ánh đỏ mờ vào cùng ảnh đã lọc với opacity 0.4
alpha = 0.4
result = cv2.addWeighted(overlay, alpha, result, 1 - alpha, 0)

print("Số pixel đen theo 3 vùng (trái, giữa, phải):", counts)
print("Vùng lớn nhất nằm ở cột số:", best_idx + 1)

cv2.imshow("Mask (Vung mau den)", mask)
cv2.imshow("Result (Danh dau do)", result)
cv2.waitKey(0)
cv2.destroyAllWindows()
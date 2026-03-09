from screenshot import WindowCapture
import cv2

cap = WindowCapture("陰陽師Onmyoji")

while True:

    frame = cap.capture()

    cv2.imshow("window", frame)

    if cv2.waitKey(1) == 27:
        break
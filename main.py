import cv2
import numpy as np
img1 = cv2.imread('red_+.png')
img2 = cv2.imread('red.png')
diff = cv2.absdiff(img1, img2)

print("shape:", diff.shape)
print("diff max:", diff.max())
print("diff moyenne:", diff.mean())

gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)

for threshold in [1, 5, 10, 20, 50, 100]:
    count = np.count_nonzero(gray > threshold)
    percent = count / gray.size * 100
    print(f"> {threshold:3}: {count:8} pixels ({percent:.4f}%)")

cv2.imwrite('diff.png', diff)
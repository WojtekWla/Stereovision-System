import sys

import cv2 as cv
import numpy as np

if len(sys.argv) != 3:
    raise RuntimeError("Wrong number of arguments")

#images must be rectified to see correct results
image_left = sys.argv[1]
image_right = sys.argv[2]

img_l = cv.imread(image_left)
img_r = cv.imread(image_right)

combined = np.hstack((img_l, img_r))

for y in range(0, combined.shape[0], 30):
    cv.line(combined, (0, y), (combined.shape[1], y), (0, 255, 0), 1)

cv.imshow("Rectification Check", combined)
key = cv.waitKey(0)
cv.destroyAllWindows()



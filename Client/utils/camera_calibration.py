import cv2 as cv
import glob
import numpy as np
import re

CHESSBOARD_SIZE = (8,5)
FRAME_SIZE = (800,600)


criteria = (cv.TERM_CRITERIA_EPS + cv.TERM_CRITERIA_MAX_ITER, 30, 1e-3)

images_left = sorted(
        glob.glob("../images/temp/800_600_4/left/pair_left_*.jpg"),
        key=lambda x: int(re.search(r"pair_left_(\d+)\.jpg", x).group(1))
)

images_right = sorted(
    glob.glob("../images/temp/800_600_4/right/pair_right_*.jpg"),
    key=lambda x: int(re.search(r"pair_right_(\d+)\.jpg", x).group(1))
)

assert len(images_left) == len(images_right)
correct_images = 0
samples_l = []
samples_r = []
for imgLeft, imgRight in zip(images_left, images_right):
    imgL = cv.imread(imgLeft)
    imgR = cv.imread(imgRight)

    grayL = cv.cvtColor(imgL, cv.COLOR_BGR2GRAY)
    grayR = cv.cvtColor(imgR, cv.COLOR_BGR2GRAY)

    retL, cornersL = cv.findChessboardCorners(grayL, CHESSBOARD_SIZE)
    retR, cornersR = cv.findChessboardCorners(grayR, CHESSBOARD_SIZE)

    if retL and retR:
        cornersL = cv.cornerSubPix(grayL, cornersL, (10, 10), (-1, -1), criteria)
        cornersR = cv.cornerSubPix(grayR, cornersR, (10, 10), (-1, -1), criteria)
        samples_l.append(cornersL)
        samples_r.append(cornersR)
        correct_images +=1

print(f"Correct images {correct_images}")


pattern_points = np.zeros((np.prod(CHESSBOARD_SIZE), 3), np.float32)
pattern_points[:, :2] = np.indices(CHESSBOARD_SIZE).T.reshape(-1, 2)
pattern_points = [pattern_points] * len(samples_l)

print("Stereo calibration")
rms, left_camera, left_distortion, right_camera, right_distortion, rotation, translation, E, F = cv.stereoCalibrate(
    pattern_points, samples_l, samples_r, None, None, None, None, FRAME_SIZE, flags=0)

print(f"Rms: {rms}")
print("Saving cameras matrices")
np.save("../camera_parameters/cameraMatrixL.npy", left_camera)
np.save("../camera_parameters/cameraMatrixR.npy", right_camera)

print("Computing optimal new camera matrix")
optimal_camera_matrix_l, valid_roi_l = cv.getOptimalNewCameraMatrix(left_camera, left_distortion, FRAME_SIZE, 0)
optimal_camera_matrix_r, valid_roi_r = cv.getOptimalNewCameraMatrix(right_camera, right_distortion, FRAME_SIZE, 0)

print("Stereo rectification")
R1, R2, P1, P2, Q, validRoi1, validRoi2 = cv.stereoRectify(left_camera, left_distortion, right_camera, right_distortion, FRAME_SIZE, rotation, translation, alpha=1)

print("Saving roiL and roiR")
np.save("../camera_parameters/roiL.npy", validRoi1)
np.save("../camera_parameters/roiR.npy", validRoi2)

print("Init undistort rectify map")
stereoMapL = cv.initUndistortRectifyMap(left_camera, left_distortion, R1, P1, FRAME_SIZE, 5)
stereoMapR = cv.initUndistortRectifyMap(right_camera, right_distortion, R2, P2, FRAME_SIZE, 5)

print("Saving parameters!")
cv_file = cv.FileStorage('../camera_parameters/stereoMap.xml', cv.FILE_STORAGE_WRITE)

cv_file.write('stereoMapL_x', stereoMapL[0])
cv_file.write('stereoMapL_y', stereoMapL[1])
cv_file.write('stereoMapR_x', stereoMapR[0])
cv_file.write('stereoMapR_y', stereoMapR[1])

cv_file.release()
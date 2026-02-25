import cv2 as cv
import numpy as np

class DepthCalculator:
    def __init__(self):
        cv_file = cv.FileStorage()
        cv_file.open('camera_parameters/stereoMap.xml', cv.FILE_STORAGE_READ)

        self.stereoMapL_x = cv_file.getNode('stereoMapL_x').mat()
        self.stereoMapL_y = cv_file.getNode('stereoMapL_y').mat()
        self.stereoMapR_x = cv_file.getNode('stereoMapR_x').mat()
        self.stereoMapR_y = cv_file.getNode('stereoMapR_y').mat()

        self.roi_l = np.load("camera_parameters/roiL.npy")
        self.roi_r = np.load("camera_parameters/roiR.npy")

        P1 = np.load("camera_parameters/cameraMatrixL.npy")
        P2 = np.load("camera_parameters/cameraMatrixR.npy")
        self.focal_length = (P1[0,0] + P2[0,0]) / 2 #average focal length from both cameras in pixels

        self.baseline = 8

    def calculate_depth_qr_code(self, center_l, center_r):
        disparity = abs(center_l - center_r)
        if disparity > 0:
            return round(self.focal_length * self.baseline / disparity, 0)
        else:
            return None

    def rectify_images(self, img_l, img_r):
        img_l = cv.remap(img_l, self.stereoMapL_x, self.stereoMapL_y, cv.INTER_LINEAR)
        img_r = cv.remap(img_r, self.stereoMapR_x, self.stereoMapR_y, cv.INTER_LINEAR)

        return img_l, img_r
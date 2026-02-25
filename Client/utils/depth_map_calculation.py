from traceback import print_exc

import cv2 as cv
import numpy as np
from matplotlib import pyplot as plt
import os
import re
import sys
import time

RESEARCH_DIR = "../research"
SGBM_DIR = "SGBM"
BM_DIR = "BM"

def get_counter(directory):
    counter = 0
    path = os.path.join(RESEARCH_DIR, directory)
    for name in os.listdir(path):
        match = re.search(r"img(\d+)\.jpg", name)
        if match:
            counter = max(counter, int(match.group(1)))

    return counter+1

def calculate_depth_with_SGBM(img_l_num, img_r_num):
    print("Calculating depth map with SGBM")
    img_l_path = f"{RESEARCH_DIR}/test/pair_left_{img_l_num}.jpg"
    img_r_path = f"{RESEARCH_DIR}/test/pair_right_{img_r_num}.jpg"

    img_l = cv.imread(img_l_path)
    img_r = cv.imread(img_r_path)

    window_size = 7
    min_disp = 10
    nDispFactor = 4
    num_disp = 16 * nDispFactor
    left_matcher = cv.StereoSGBM_create(
                minDisparity=min_disp,
                numDisparities=num_disp,
                blockSize=window_size,
                P1=8 * 3 * window_size ** 2,
                P2=32 * 3 * window_size ** 2,
                disp12MaxDiff=1,
                uniquenessRatio=1,
                speckleWindowSize=100,
                speckleRange=35,
                preFilterCap=63,
                mode=cv.STEREO_SGBM_MODE_SGBM_3WAY
            )

    img_l = cv.cvtColor(img_l, cv.COLOR_BGR2GRAY)
    img_r = cv.cvtColor(img_r, cv.COLOR_BGR2GRAY)


    right_matcher = cv.ximgproc.createRightMatcher(left_matcher)
    wls_filter = cv.ximgproc.createDisparityWLSFilter(matcher_left=left_matcher)
    wls_filter.setLambda(8000.0)
    wls_filter.setSigmaColor(2.0)

    t1 = time.perf_counter()
    disp_left = left_matcher.compute(img_r, img_l)
    disp_right = right_matcher.compute(img_l, img_r)
    disp_filtered = wls_filter.filter(disp_left, img_l, disparity_map_right=disp_right)

    disp_real = disp_filtered / 16.0
    scale_factor = 4
    disp_vis = np.clip(disp_real * scale_factor, 0, 255).astype(np.uint8)
    disp_color = cv.applyColorMap(disp_vis, cv.COLORMAP_MAGMA)
    t2 = time.perf_counter()

    counter = get_counter(SGBM_DIR)
    cv.imwrite(f"{RESEARCH_DIR}/{SGBM_DIR}/img{counter}.jpg", disp_color)

    print(f"Saving SGBM image {counter}")
    print(f"Execution time {t2-t1}")

def calculate_depth_with_BM(img_l_num, img_r_num):
    print("Calculating depth map with BM")
    img_l_path = f"{RESEARCH_DIR}/test/pair_left_{img_l_num}.jpg"
    img_r_path = f"{RESEARCH_DIR}/test/pair_right_{img_r_num}.jpg"
    img_l = cv.imread(img_l_path)
    img_r = cv.imread(img_r_path)
    img_l = cv.cvtColor(img_l, cv.COLOR_BGR2GRAY)
    img_r = cv.cvtColor(img_r, cv.COLOR_BGR2GRAY)

    nDispFactory = 4


    left_matcher = cv.StereoBM.create(numDisparities=nDispFactory * 16, blockSize=5)
    left_matcher.setPreFilterCap(31)
    left_matcher.setMinDisparity(0)
    left_matcher.setTextureThreshold(10)
    left_matcher.setUniquenessRatio(15)

    right_matcher = cv.ximgproc.createRightMatcher(left_matcher)

    wls_filter = cv.ximgproc.createDisparityWLSFilter(matcher_left=left_matcher)
    wls_filter.setLambda(8000.0)
    wls_filter.setSigmaColor(2.0)

    t1 = time.perf_counter()
    disp_left = left_matcher.compute(img_r, img_l)
    disp_right = right_matcher.compute(img_l, img_r)

    disp_filtered = wls_filter.filter(disp_left, img_l, disparity_map_right=disp_right)

    disp_real = disp_filtered / 16.0
    scale_factor = 4
    disp_vis = np.clip(disp_real * scale_factor, 0, 255).astype(np.uint8)
    disp_color = cv.applyColorMap(disp_vis, cv.COLORMAP_MAGMA)
    t2 = time.perf_counter()

    counter = get_counter(BM_DIR)
    cv.imwrite(f"{RESEARCH_DIR}/{BM_DIR}/img{counter}.jpg", disp_color)

    print(f"Saving BM image {counter}")
    print(f"Execution time {t2-t1}")

if __name__ == '__main__':
    if len(sys.argv) == 4:
        l = sys.argv[2]
        r = sys.argv[3]
        m = sys.argv[1]

        if m == "sgbm":
            calculate_depth_with_SGBM(l, r)
        else:
            calculate_depth_with_BM(l,r)

    else:
        print("Wrong number of arguments")
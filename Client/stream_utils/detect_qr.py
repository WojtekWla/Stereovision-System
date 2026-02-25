import cv2
import numpy as np

class QrDetector:
    def __init__(self):
        self.points = None
        self.center = None
        self.prev_image = None
        self.qrDetector = cv2.QRCodeDetector()
        self.qr_detected = False
        self.lk_params = dict(winSize=(15, 15),
                         maxLevel=2,
                         criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03))

    async def detect_points(self, img):
        try:
            value, points, qrcode = self.qrDetector.detectAndDecode(img)
            if points is not None or value != "":
                self.prev_image =cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                self.points = points[0].astype(np.float32)
                self.center = self.points.mean(axis=0)
                self.qr_detected = True

                return np.vstack([self.points, self.center])
        except cv2.error as e:
            print("Detecting and decoding error")

        return np.array([])

    async def draw_rectangle(self, img):
        if self.points is None or len(self.points) < 4:
            return

        xs = self.points[:, 0]
        ys = self.points[:, 1]

        x1, y1 = int(xs.min()), int(ys.min())
        x2, y2 = int(xs.max()), int(ys.max())

        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 5)

    async def track_points(self, img):
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        prev_points = self.points.reshape(-1,1,2)

        p1, st, err = cv2.calcOpticalFlowPyrLK(self.prev_image, gray, prev_points, None, **self.lk_params)

        if  p1 is None:
            self.change_to_detect()
            return np.array([])
        self.prev_image = gray
        good_points = p1[st==1]
        if len(good_points) < 4:
            self.change_to_detect()
            return np.array([])

        self.points = good_points[:4]
        self.center = self.points.mean(axis=0)

        return np.vstack([self.points, self.center])

    def change_to_detect(self):
        self.qr_detected = False
        self.points = None
        self.center = None

    @staticmethod
    async def validate_tracking(point_l: np.array, point_r: np.array, tracking_threshold_y: int, tracking_threshold_x: int) -> bool:
        if point_l.size == 0 or point_r.size == 0 or point_l.shape != point_r.shape:
            return False

        center_l, center_r = point_l[4], point_r[4]

        if abs(center_l[1] - center_r[1]) > tracking_threshold_y \
                or abs(center_l[0] - center_r[0]) > tracking_threshold_x:
            return False

        return True
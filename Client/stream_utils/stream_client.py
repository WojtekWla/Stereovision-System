import asyncio, websockets, cv2, numpy as np, time
from dataclasses import dataclass
from stream_utils.detect_qr import QrDetector
from stream_utils.show_depth import DepthCalculator
from matplotlib import pyplot as plt
from rotation_engine_module import rotation_engine as rotation

LEFT_URI  = "{{LEFT_CAMERA_URI}}"
RIGHT_URI = "{{RIGHT_CAMERA_URI}}"
ENGINE_URI = "{{ENGINE_URI}}"
MAX_FRAME_DIFF = 500

LEFT_IMAGE_FILE = "images/temp/800_600_4/pair_left_"
RIGHT_IMAGE_FILE = "images/temp/800_600_4/pair_right_"

@dataclass
class Image:
    arrive_time: np.uint32
    img: np.ndarray

class StreamBuffer:
    def __init__(self): self.frame = None
    def update_frame(self, frame: Image): self.frame = frame
    def get_frame(self): return self.frame
    def remove_frame(self): self.frame = None

class FpsBuffer:
    def __init__(self, l_camera, r_camera):
        self.fps_map = {
            l_camera: 0,
            r_camera: 0
        }

    def set_fps(self, camera_name, fps):
        self.fps_map[camera_name] = fps
    def get_fps(self, camera_name):
        return self.fps_map[camera_name]

class FpsCounter:
    def __init__(self):
        self.fps = 0
        self.prev_time = 0

    def calculate_fps(self, curr_time):
        dt = curr_time - self.prev_time
        self.prev_time = curr_time
        if dt > 0:
            self.fps = self.fps * 0.9 + (1.0 / dt) * 0.1
        return self.fps

class StreamListener:
    def __init__(self, name: str, uri:str, buf: StreamBuffer, fps_buf: FpsBuffer, event: asyncio.Event):
        self.listening = True
        self.sending = True
        self.name = name
        self.uri = uri
        self.buf = buf
        self.event = event
        self.fps_counter = FpsCounter()
        self.fps_buffer = fps_buf

    async def consume_camera(self):
        retry_factor = 1
        while True:
            try:
                print(f"[{self.name}] connect {self.uri}")
                async with websockets.connect(self.uri, ping_interval=15, ping_timeout=10, max_size=None) as ws:
                    print(f"[{self.name}] connected, sending 'start'")
                    await ws.send("start")

                    listening_task = asyncio.create_task(self.listening_task(ws))
                    sending_task = asyncio.create_task(self.sending_task(ws))

                    await asyncio.gather(listening_task, sending_task)

            except (websockets.ConnectionClosed, OSError) as e:
                print(f"[{self.name}] disconnected: {e}; retry in {retry_factor} seconds")
                await asyncio.sleep(retry_factor)
                retry_factor = min(retry_factor*2, 10)
            except Exception as e:
                print(f"[{self.name}] error: {e}")
                await asyncio.sleep(2)

    async def listening_task(self, ws):
        while self.listening:
            msg = await ws.recv()
            if isinstance(msg, bytes):
                arr = np.frombuffer(msg, np.uint8)
                millis = int.from_bytes(arr[0:4], 'big')
                img = cv2.imdecode(arr[4:], cv2.IMREAD_COLOR)
                if img is not None:
                    self.buf.update_frame(Image(millis, img))

                fps = self.fps_counter.calculate_fps(time.time())
                self.fps_buffer.set_fps(self.name, fps)

            await asyncio.sleep(0.001)

    async def sending_task(self, ws):
        while self.sending:
            if self.event.is_set():
                print(f"[{self.name}] Sent to client camera sync command {time.time()}")
                await ws.send("sync")
                self.event.clear()

            await asyncio.sleep(1)

async def main_loop():
    l_camera_name, r_camera_name = "left", "right"
    left_buffer, right_buffer = StreamBuffer(), StreamBuffer()
    fps_buffer = FpsBuffer(l_camera_name, r_camera_name)
    location_buffer = rotation.LocationBuffer()
    command_buffer = rotation.CommandBuffer()


    resynchronize_event = asyncio.Event()
    stream_listener_l = StreamListener(l_camera_name, LEFT_URI, left_buffer, fps_buffer, resynchronize_event)
    stream_listener_r = StreamListener(r_camera_name, RIGHT_URI, right_buffer, fps_buffer, resynchronize_event)
    rotation_engine = rotation.RotationEngineController(command_buffer, location_buffer)
    rotation_communication = rotation.RotationEngineCommunication(ENGINE_URI, command_buffer)

    tasks = [
        asyncio.create_task(stream_listener_l.consume_camera()),
        asyncio.create_task(stream_listener_r.consume_camera()),
        asyncio.create_task(rotation_engine.activate_engine()),
        asyncio.create_task(rotation_communication.consume_engine()) #if rotation engine is not connected change to testing() method
    ]

    qr_detector_l = QrDetector()
    qr_detector_r = QrDetector()
    counter = 1
    depth_calculator = DepthCalculator()
    try:
        while True:
            left_frame, right_frame = left_buffer.get_frame(), right_buffer.get_frame()

            if left_frame and right_frame:
                time_difference = abs(left_frame.arrive_time - right_frame.arrive_time)
                if time_difference > MAX_FRAME_DIFF:
                    # start resynchronization
                    print("Starting synchronization process")
                    print(f"Left frame {left_frame.arrive_time}, right frame {right_frame.arrive_time}, time difference {time_difference}")
                    left_buffer.remove_frame()
                    right_buffer.remove_frame()
                    resynchronize_event.set()
                    continue

                left = left_frame.img
                right = right_frame.img

                left, right = depth_calculator.rectify_images(left, right)

                l_points = []
                r_points = []

                if not qr_detector_l.qr_detected or not qr_detector_r.qr_detected:
                    l_points, r_points = await asyncio.gather(qr_detector_l.detect_points(left), qr_detector_r.detect_points(right))
                else:
                    l_points, r_points = await asyncio.gather(qr_detector_l.track_points(left), qr_detector_r.track_points(right))

                if len(l_points) != 0 and len(r_points) != 0:
                    if await QrDetector.validate_tracking(l_points, r_points, 30, 200):
                        location_buffer.update_location(rotation.Location(l_points[4], r_points[4]))
                        await asyncio.gather(qr_detector_l.draw_rectangle(left), qr_detector_r.draw_rectangle(right))

                        distance = depth_calculator.calculate_depth_qr_code(l_points[4][0], r_points[4][0])
                        cv2.putText(left, f'Distance: {distance}', (30, 70), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 255), 3)
                        cv2.putText(right, f'Distance: {distance}', (30, 70), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 255), 3)
                    else:
                        qr_detector_l.change_to_detect()
                        qr_detector_r.change_to_detect()

                cv2.imshow("left", left)
                cv2.imshow("right", right)

                key = cv2.waitKey(1) & 0xFF
                if key == 27:
                    break
                elif key == ord('s'):
                    cv2.imwrite(f"{LEFT_IMAGE_FILE}{counter}.jpg", left_buffer.get_frame().img)
                    cv2.imwrite(f"{RIGHT_IMAGE_FILE}{counter}.jpg", right_buffer.get_frame().img)

                    print(f"Saved stereo pair for calibration {counter}.")
                    counter += 1

            await asyncio.sleep(0.001)

    finally:
        for t in tasks:
            t.cancel()
        cv2.destroyAllWindows()
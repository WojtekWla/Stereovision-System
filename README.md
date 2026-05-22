# Stereovision System

An active stereovision system capable of real-time depth estimation and autonomous object tracking. Two ESP32-CAM modules stream synchronized video frames to a Python client, which detects a QR code target, calculates its distance, and drives a 3D-printed pan-tilt arm to keep the target centered in the frame.

## System Architecture

```
 ┌────────────────┐     WebSocket      ┌─────────────────────────┐
 │  ESP32-CAM (L) │ ─────────────────► │                         │
 └────────────────┘                    │   Python Client         │
                                       │   (asyncio)             │
 ┌────────────────┐     WebSocket      │                         │
 │  ESP32-CAM (R) │ ─────────────────► │  • Frame sync           │
 └────────────────┘                    │  • QR detection         │
                                       │  • Depth calculation    │
 ┌────────────────┐     WebSocket      │  • Tracking control     │
 │ Rotation Engine│ ◄───────────────── │                         │
 │  (ESP32 + 4×DC)│                    └─────────────────────────┘
 └────────────────┘
        │
  ┌─────┴──────┐
  │ ABENICS arm│
  │ (3D print) │
  └────────────┘
```

## Hardware Components

### ESP32-CAM (×2)
- **Board**: AI Thinker ESP32-CAM
- **Resolution**: SVGA 800×600, JPEG quality 4
- **Transport**: WebSocket binary frames, each prepended with a 4-byte millisecond timestamp
- **Sync**: client sends a `sync` command that pauses capture for 3 s on both cameras simultaneously to re-align frame timestamps
- **Camera settings**: fixed exposure (AEC disabled), fixed gain (AGC disabled), white balance locked — ensures consistent stereo matching conditions

### Rotation Engine (ESP32)
- **MCU**: ESP32 DevKit
- **Drivers**: 4-channel H-bridge controlled via an 8-bit shift register (direction) + 4 PWM pins (speed)
- **Transport**: WebSocket text commands (`left`, `right`, `up`, `down`, `stop`, `alll`, `allr`)
- **Build**: PlatformIO, Arduino framework, `AccelStepper` + `WebSockets` libraries

### 3D-Printed Rotating Arm (ABENICS mechanism)
The pan-tilt arm was designed and printed in-house. Its joint is based on the **ABENICS** (Active Ball Joint Mechanism with ENriched motIon Concept by non-backdrivable Screw mechanism) architecture — a spherical joint mechanism that achieves three-degree-of-freedom rotation by driving a ball gear with intersecting worm screws. This design was chosen because:

- **Non-backdrivable**: the arm holds its position under load without active braking, protecting the motors during imaging pauses
- **Compact**: all actuators mount coaxially near the base, keeping the moving mass low
- **Smooth multi-axis motion**: simultaneous horizontal (pan) and vertical (tilt) movement is possible by combining motor commands

The firmware maps the four DC motors to orthogonal movement directions:

| Command | Motors driven |
|---------|--------------|
| `up`    | M2 backward + M3 forward |
| `down`  | M2 backward + M3 backward |
| `left`  | M1 forward + M2 backward + M3 backward + M4 backward |
| `right` | M1 backward + M2 backward + M3 forward + M4 backward |
| `stop`  | all motors released |

Reference: Tadakuma et al., *"ABENICS: Active Ball Joint Mechanism With Three-DoF Based on the Spherical Gear Meshings"*, IEEE T-RO, 2021.

## Software — Python Client

Located in `Client/`. Entry point: `main.py` → `asyncio.run(main_loop())`.

### Key modules

| Module | Responsibility |
|--------|----------------|
| `stream_utils/stream_client.py` | Async WebSocket listeners for both cameras; exponential-backoff reconnect |
| `stream_utils/detect_qr.py` | QR code detection (OpenCV `QRCodeDetector`) with Lucas-Kanade optical flow tracking fallback |
| `stream_utils/show_depth.py` | Stereo rectification (`cv2.remap`) and disparity-to-depth conversion |
| `rotation_engine_module/rotation_engine.py` | `RotationEngineController` — computes pan/tilt commands from QR center position; `RotationEngineCommunication` — sends commands over WebSocket |
| `utils/camera_calibration.py` | Offline stereo calibration script (chessboard 8×5, 800×600) |
| `utils/depth_map_calculation.py` | Offline dense depth map scripts using SGBM and BM matchers with WLS filtering |

### Frame synchronization

Each frame carries the camera's millisecond uptime. If `|t_left − t_right| > 500 ms` the pair is discarded and a `sync` command is broadcast to both cameras, which pause for 3 s before resuming — realigning their clocks relative to the client connection time.

### Depth estimation

**Online (QR code target)**
```
depth = focal_length × baseline / disparity
```
- `baseline` = 8 cm (physical camera separation)
- `focal_length` = average of calibrated left and right focal lengths (pixels)
- `disparity` = horizontal pixel offset of the QR code centre between left and right images

**Offline (dense maps)**
- `SGBM` — Semi-Global Block Matching with WLS filter post-processing
- `BM` — Block Matching with WLS filter post-processing

### Autonomous tracking

`RotationEngineController` treats the image centre (400, 300) as the target position. When the detected QR code drifts beyond a 70-pixel Euclidean threshold it issues directional motor commands via `CommandBuffer`. It monitors each axis independently and waits for `position_reached()` before stopping — also detecting rapid over-shoots that indicate the target moved unexpectedly.

## Camera Calibration

Run `Client/utils/camera_calibration.py` with a set of synchronised stereo chessboard images (8×5 inner corners). The script outputs:

| File | Contents |
|------|----------|
| `camera_parameters/cameraMatrixL.npy` | Left intrinsic matrix |
| `camera_parameters/cameraMatrixR.npy` | Right intrinsic matrix |
| `camera_parameters/roiL.npy` | Left valid ROI after rectification |
| `camera_parameters/roiR.npy` | Right valid ROI after rectification |
| `camera_parameters/stereoMap.xml` | Rectification maps for `cv2.remap` |

## Configuration

Before flashing, replace the placeholders in the firmware sources:

| File | Placeholder | Value |
|------|-------------|-------|
| `ESP_CAM/src/main.cpp` | `{{SSID}}`, `{{PASSWORD}}` | Wi-Fi credentials |
| `Rotation_Engine/src/main.cpp` | `{{SSID}}`, `{{PASSWORD}}` | Wi-Fi credentials |
| `Client/stream_utils/stream_client.py` | `{{LEFT_CAMERA_URI}}`, `{{RIGHT_CAMERA_URI}}`, `{{ENGINE_URI}}` | `ws://<ip>:7890` for cameras, `ws://<ip>:80` for engine |

## Dependencies

**Firmware** (PlatformIO)
- `links2004/WebSockets ^2.7.1`
- `waspinator/AccelStepper ^1.64` (Rotation Engine only)

**Python Client**
- `opencv-python` (with `opencv-contrib-python` for `ximgproc` WLS filter)
- `websockets`
- `numpy`
- `matplotlib`

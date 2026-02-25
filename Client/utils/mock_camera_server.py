import asyncio
import glob
import random
import re

import websockets
from typing import List
import time

HOST_LEFT  = "localhost"
PORT_LEFT  = 7891
HOST_RIGHT = "localhost"
PORT_RIGHT = 7892

DELAY_MIN_MS = 1
DELAY_MAX_MS = 50

def simulate_delay_ms() -> int:
    return random.randint(DELAY_MIN_MS, DELAY_MAX_MS)

class MockServer:
    def __init__(self, name: str, jpg_paths: List[str]):
        self.name = name
        self.jpg_paths = jpg_paths
        self.idx = 0

    async def handler(self, ws: websockets.WebSocketServerProtocol):
        print(f"[{self.name}] client connected from {ws.remote_address}")
        send_enable = asyncio.Event()
        listen_task = asyncio.create_task(self._listen(ws, send_enable))
        send_task = asyncio.create_task(self._send(ws, send_enable))

        try:
            await asyncio.gather(listen_task, send_task)
        except (websockets.ConnectionClosed, asyncio.CancelledError):
            pass
        except Exception as e:
            print(f"[{self.name}] connection error: {e!r}")
        finally:
            for t in (listen_task, send_task):
                if not t.done():
                    t.cancel()
                    try:
                        await t
                    except asyncio.CancelledError:
                        pass
            try:
                await ws.close()
            except Exception:
                pass
            self.idx = 0
            print(f"[{self.name}] client disconnected")

    async def _listen(self, ws: websockets.WebSocketServerProtocol, send_enable: asyncio.Event):
        while True:
            msg = await ws.recv()
            if not isinstance(msg, str):
                continue
            cmd = msg.strip().lower()
            if cmd == "start":
                send_enable.set()
                await ws.send("ok: start")
                print(f"[{self.name}] start streaming")
            elif cmd == "stop":
                send_enable.clear()
                await ws.send("ok: stop")
                print(f"[{self.name}] stop streaming")
            elif cmd == "sync":
                send_enable.clear()
                await ws.send("ok: sync-begin")
                print(f"[{self.name}] sync pause")
                self.idx = 0
                await asyncio.sleep(5.0)
                send_enable.set()
                print(f"[{self.name}] sync resume")
            else:
                await ws.send(f"err: unknown cmd '{cmd}'")

    async def _send(self, ws: websockets.WebSocketServerProtocol, send_enable: asyncio.Event):
        total = len(self.jpg_paths)
        while True:
            await send_enable.wait()
            try:
                with open(self.jpg_paths[self.idx], "rb") as f:
                    img_bytes = f.read()
                await ws.send(img_bytes)
                print(f"{self.name} Sending image {self.idx}, {time.time()}")
            except (websockets.ConnectionClosed, asyncio.CancelledError):
                raise
            except Exception as e:
                print(f"[{self.name}] send error: {e!r}")
                await asyncio.sleep(0.1)

            self.idx = (self.idx + 1) % total
            await asyncio.sleep(0.033)

async def main():
    left_imgs = sorted(
        glob.glob("../images/mock/pair_left_*.jpg"),
        key=lambda x: int(re.search(r"pair_left_(\d+)\.jpg", x).group(1))
    )

    right_imgs = sorted(
        glob.glob("../images/mock/pair_right_*.jpg"),
        key=lambda x: int(re.search(r"pair_right_(\d+)\.jpg", x).group(1))
    )

    left_server = MockServer("left",  left_imgs)
    right_server = MockServer("right", right_imgs)

    server_left = await websockets.serve(left_server.handler,  HOST_LEFT,  PORT_LEFT, ping_interval=15, ping_timeout=10)
    server_right = await websockets.serve(right_server.handler, HOST_RIGHT, PORT_RIGHT, ping_interval=15, ping_timeout=10)

    print(f"[left ] ws://{HOST_LEFT}:{PORT_LEFT}/")
    print(f"[right] ws://{HOST_RIGHT}:{PORT_RIGHT}/")

    try:
        await asyncio.Future()
    finally:
        server_left.close()
        await server_left.wait_closed()
        server_right.close()
        await server_right.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())

import websockets as ws
import asyncio

IP = "{{ENGINE_URI}}"
PORT = "80"

async def main():
    ws_url = f"ws://{IP}:{PORT}"
    print(f"Connecting to {ws_url}")
    try:
        async with ws.connect(ws_url) as websocket:
            print("Connected to rotation engine")
            while True:
                cmd = await asyncio.to_thread(input)
                print(f"Sending command {cmd}")

                await websocket.send(cmd)
                msg = await websocket.recv()

                print(f"Received {msg}")
    except Exception as e:
        print(f"Error {e}")


if __name__ == "__main__" :
    asyncio.run(main())
import websockets
import asyncio
from rotation_engine import *

IMAGE_CENTER_X = 400
IMAGE_CENTER_Y = 300
ENGINE_URI = "{{ENGINE_URI}}"


async def test_controller(location_buffer: LocationBuffer):
    while True:
        print("Pos X: ", end='', flush=True)
        position_x = int(await asyncio.to_thread(input))
        print("Pos Y: ", end='', flush=True)
        position_y = int(await asyncio.to_thread(input))

        loc = Location([position_x, position_y], [position_x, position_y])
        location_buffer.update_location(loc)

        await asyncio.sleep(1)

async def automate_test_controller(location_buffer: LocationBuffer):
    while True:
        print("Pos X: ", end='', flush=True)
        position_x = int(await asyncio.to_thread(input))
        print("Pos Y: ", end='', flush=True)
        position_y = int(await asyncio.to_thread(input))

        loc = Location([position_x, position_y], [position_x, position_y])
        location_buffer.update_location(loc)

        await imitate_closing(position_x, position_y, location_buffer)
        await asyncio.sleep(0.1)


async def imitate_closing(pos_x: int, pos_y: int, location_buffer: LocationBuffer):
    if pos_x < IMAGE_CENTER_X:
        while pos_x < IMAGE_CENTER_X:
            await asyncio.sleep(1)
            pos_x += 50
            loc = Location([pos_x, pos_y], [pos_x, pos_y])
            location_buffer.update_location(loc)
    elif pos_x > IMAGE_CENTER_X:
        while pos_x > IMAGE_CENTER_X:
            await asyncio.sleep(1)
            pos_x -= 50
            loc = Location([pos_x, pos_y], [pos_x, pos_y])
            location_buffer.update_location(loc)

    if pos_y < IMAGE_CENTER_Y:
        while pos_y < IMAGE_CENTER_Y:
            await asyncio.sleep(1)
            pos_y += 50
            loc = Location([pos_x, pos_y], [pos_x, pos_y])
            location_buffer.update_location(loc)

    elif pos_y > IMAGE_CENTER_Y:
        while pos_y > IMAGE_CENTER_Y:
            await asyncio.sleep(1)
            pos_y -= 50
            loc = Location([pos_x, pos_y], [pos_x, pos_y])
            location_buffer.update_location(loc)

async def main():
    location_buffer = LocationBuffer()
    command_buffer = CommandBuffer()

    rotation_engine = RotationEngineController(command_buffer, location_buffer)
    rotation_communication = RotationEngineCommunication(ENGINE_URI, command_buffer)

    tasks = [
        asyncio.create_task(rotation_communication.consume_engine()),
        asyncio.create_task(automate_test_controller(location_buffer)),
        asyncio.create_task(rotation_engine.activate_engine()),
    ]
    await asyncio.gather(*tasks)

if __name__ == '__main__':
    asyncio.run(main())
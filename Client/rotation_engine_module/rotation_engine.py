import asyncio
from operator import truediv

import numpy as np
import websockets as ws
from enum import Enum
from dataclasses import dataclass


@dataclass()
class Location:
    location_camera_l: np.array
    location_camera_r: np.array


class CommandBuffer:
    def __init__(self):
        self.command = None
    def update(self, comm):
        self.command = comm
    def get(self):
        comm = self.command
        self.command = None
        return comm

class LocationBuffer:
    def __init__(self):
        self.location = None

    def update_location(self, location: Location):
        if location.location_camera_l is None or location.location_camera_r is None:
            self.location = None
            return
        stacked = np.vstack([location.location_camera_l, location.location_camera_r])
        self.location = stacked.mean(axis=0)

    def get_location(self):
        return self.location

class Commands(Enum):
    ROTATE_LEFT = "left"
    ROTATE_RIGHT = "right"
    ROTATE_UP = "up"
    ROTATE_DOWN = "down"
    STOP = "stop"


class RotationEngineController:
    def __init__(self, command_buffer: CommandBuffer, location_buff: LocationBuffer):
        self.center = np.array([400, 300])
        self.current_location = None
        self.rotating = False
        self.distance_threshold = 70
        self.commands = Commands
        self.command_buffer = command_buffer
        self.location_buffer = location_buff

    def rotation_decision(self):
        if self.current_location is None:
            return None
        if self.distance_threshold >= self.euclidean_distance(self.center, self.current_location):
            if self.rotating:
                return [self.commands.STOP]
            else:
                return None

        commands_to_execute = []
        if self.distance_threshold < self.coordinate_distance(self.center[0], self.current_location[0]):
            if self.current_location[0] < self.center[0]:
                commands_to_execute.append(self.commands.ROTATE_LEFT)
            elif self.current_location[0] > self.center[0]:
                commands_to_execute.append(self.commands.ROTATE_RIGHT)

        if self.distance_threshold < self.coordinate_distance(self.center[1], self.current_location[1]):
            if self.current_location[1] < self.center[1]:
                commands_to_execute.append(self.commands.ROTATE_UP)
            if self.current_location[1] > self.center[1]:
                commands_to_execute.append(self.commands.ROTATE_DOWN)

        return commands_to_execute

    async def activate_engine(self):
        while True:
            self.current_location = self.location_buffer.get_location()
            commands_to_execute = self.rotation_decision()
            if not commands_to_execute:
                await asyncio.sleep(0.1)
                continue

            print(f"Commands to execute {commands_to_execute}")
            self.rotating = True
            for command in commands_to_execute:
                self.command_buffer.update(command)
                ok = await self.position_reached(command)
                self.command_buffer.update(self.commands.STOP)
                if not ok:
                    break

            self.rotating = False
            await asyncio.sleep(0.1)

    async def position_reached(self, command: Commands) -> bool:
        dist = float("inf")
        while dist > self.distance_threshold:
            if self.current_location is None:
                break

            self.current_location = self.location_buffer.get_location()
            if self.position_rapidly_changed(command):
                return False

            if command == self.commands.ROTATE_LEFT or command == self.commands.ROTATE_RIGHT:
                dist = self.coordinate_distance(self.center[0], self.current_location[0])
            else:
                dist = self.coordinate_distance(self.center[1], self.current_location[1])

            await asyncio.sleep(0.1)

        return True

    def position_rapidly_changed(self, command: Commands) -> bool:
        if command == self.commands.ROTATE_LEFT and self.current_location[0] > self.center[0] \
            or command == self.commands.ROTATE_RIGHT and self.current_location[0] < self.center[0]:
            return True

        if command == self.commands.ROTATE_UP and self.current_location[1] > self.center[1] \
          or command == self.commands.ROTATE_DOWN and self.current_location[1] < self.center[1]:
            return True

        return False

    @staticmethod
    def euclidean_distance(point_1, point_2):
        return np.linalg.norm(point_1 - point_2)

    @staticmethod
    def coordinate_distance(coordinate_1, coordinate_2):
        return abs(coordinate_1 - coordinate_2)


class RotationEngineCommunication:
    def __init__(self, uri: str, comm: CommandBuffer):
        self.engine_uri = uri
        self.command_buffer = comm
    async def consume_engine(self):   
        retry_factor = 1
        while True:
            try:
                print(f"websocket url {self.engine_uri}")
                async with ws.connect(self.engine_uri) as websocket:
                    print("Connected to rotation engine")
                    while True:
                        command = self.command_buffer.get()
                        if command is None:
                            await asyncio.sleep(0.1)
                            continue

                        print(f"Rotation decision {command}")
                        await websocket.send(command.value)
                        await asyncio.sleep(0.1)

            except (ws.ConnectionClosed, OSError) as e:
                print(f"Disconnected from rotation engine: {e}; retry in {retry_factor} seconds")
                await asyncio.sleep(retry_factor)
                retry_factor += 1
                retry_factor = min(retry_factor, 10)
            except Exception as e:
                print(f"Unexpected error {e}")
                await asyncio.sleep(10)

    async def testing(self):
        prev_command = None
        while True:
            command = self.command_buffer.get()
            if command is None or command == prev_command:
                await asyncio.sleep(0.1)
                continue


            prev_command = command
            print(f"Rotation decision {command}")

            await asyncio.sleep(0.1)
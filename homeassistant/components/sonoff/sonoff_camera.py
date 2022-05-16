import asyncio
import logging
import socket
import time
from dataclasses import dataclass
from threading import Thread
from typing import Union, Dict

_LOGGER = logging.getLogger(__name__)

BROADCAST = ('255.255.255.255', 32108)

CMD_HELLO = 'f130 0000'
CMD_PONG = 'f1e1 0000'
CMD_DATA_ACK = 'f1d1 0006 d100 0001'

COMMANDS = {
    'init': (
        'f1d0 0064 d100 0000 8888767648000000100000000000000000000000'
        '000000003132333435363738000000000000000000000000000000000000'
        '000000000000000000000000000000000000000000000000000000000000'
        '00000000000000000000000000000000'),
    'left': (
        'f1d0 0024 d100 %s 888876760800000001100000000000000000000000'
        '000000 0608000000000000'),
    'right': (
        'f1d0 0024 d100 %s 888876760800000001100000000000000000000000'
        '000000 0308000000000000'),
    'up': (
        'f1d0 0024 d100 %s 888876760800000001100000000000000000000000'
        '000000 0208000000000000'),
    'down': (
        'f1d0 0024 d100 %s 888876760800000001100000000000000000000000'
        '000000 0108000000000000')
}


@dataclass
class Camera:
    addr: tuple = None
    init_data: bytes = None

    last_time: int = 0
    sequence = 0

    wait_event = asyncio.Event()
    wait_data: int = None
    wait_sequence: bytes = b'\x00\x00'

    def init(self):
        self.sequence = 0
        self.wait_sequence = b'\x00\x00'

    def get_sequence(self) -> str:
        self.sequence += 1
        self.wait_sequence = self.sequence.to_bytes(2, byteorder='big')
        return self.wait_sequence.hex()

    async def wait(self, data: int):
        self.wait_data = data
        self.wait_event.clear()
        await self.wait_event.wait()


class EWeLinkCameras(Thread):
    """
    It's better to use `DatagramProtocol` and `create_datagram_endpoint`.
    But it don't supported in win32 with `ProactorEventLoop`.
    """
    devices: Dict[str, Camera] = {}
    sock: socket = None

    def __init__(self):
        super().__init__(name="Sonoff_CAM", daemon=True)

    def datagram_received(self, data: bytes, addr: tuple):
        # _LOGGER.debug(f"<= {addr[0]:15} {data[:80].hex()}")

        cmd = data[1]

        if cmd == 0x41:
            deviceid = int.from_bytes(data[12:16], byteorder='big')
            deviceid = f"{deviceid:06}"
            # EWLK-012345-XXXXX
            # UID = f"EWLK-{deviceid}-{data[16:21]}"

            if deviceid not in self.devices:
                _LOGGER.debug(f"Found new camera {deviceid}: {addr}")
                self.devices[deviceid] = Camera(addr, data)
                return

            else:
                # Update addr of device
                self.devices[deviceid].addr = addr
                self.devices[deviceid].init_data = data

        device = next((p for p in self.devices.values()
                       if p.addr == addr), None)
        if not device:
            # log.debug(f"Response from unknown address: {addr}")
            return

        if cmd != 0xE0:
            device.last_time = time.time()

        if cmd == 0xD0:
            data = bytes.fromhex(CMD_DATA_ACK) + data[6:8]
            self.sendto(data, device)

        elif cmd == 0xE0:
            # TODO:
            # self.sendto(CMD_PONG, device)
            pass

        if device.wait_data == cmd:
            if cmd != 0xD1 or device.wait_sequence == data[8:10]:
                device.wait_event.set()

    def sendto(self, data: Union[bytes, str], device: Camera):
        if isinstance(data, str):
            if '%s' in data:
                data = data % device.get_sequence()
            data = bytes.fromhex(data)
        # _LOGGER.debug(f"=> {device.addr[0]:15} {data[:60].hex()}")
        self.sock.sendto(data, device.addr)

    def start(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.sock.bind(('', 0))

        super().start()

    async def send(self, deviceid: str, command: str):
        device = self.devices.get(deviceid)

        if not device or time.time() - device.last_time > 9:
            # start Thread if first time
            if not self.is_alive():
                self.start()

            if not device:
                # create new device, we want wait for it
                self.devices[deviceid] = device = Camera()
            else:
                device.init()

            _LOGGER.debug("Send HELLO")
            data = bytes.fromhex(CMD_HELLO)
            self.sock.sendto(data, BROADCAST)
            await device.wait(0x41)

            _LOGGER.debug("Send UID Session Open Request")
            self.sendto(device.init_data, device)
            await device.wait(0x42)

            _LOGGER.debug("Send Init Command")
            self.sendto(COMMANDS['init'], device)
            await device.wait(0xD1)

        _LOGGER.debug(f"Send Command {command}")
        self.sendto(COMMANDS[command], device)
        await device.wait(0xD1)

    def run(self):
        while True:
            try:
                data, addr = self.sock.recvfrom(1024)
                self.datagram_received(data, addr)
            except:
                _LOGGER.exception("Camera read exception")

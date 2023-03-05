"""SMA Manager API"""

#  Copyright (c) 2023.
#  All rights reserved to the creator of the following script/program/app, please do not
#  use or distribute without prior authorization from the creator.
#  Creator: Antonio Manuel Nunes Goncalves
#  Email: amng835@gmail.com
#  LinkedIn: https://www.linkedin.com/in/antonio-manuel-goncalves-983926142/
#  Github: https://github.com/DEADSEC-SECURITY

# Built-In Imports
import socket
import struct
from datetime import timedelta
from typing import Any

SMA_BUFFER_SIZE = 10240


def create_multicast_socket(ip: str, port: int, timeout: int = 5):
    """
    Creates and returns a socket
    """

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("", port))
    mreq = struct.pack("4sl", socket.inet_aton(ip), socket.INADDR_ANY)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    sock.settimeout(timeout)
    return sock


def _bytes_to_power(bytes_):
    """
    Converts bytes data into a integer representing power in watts

    @param bytes_:
    @return:
    """

    return int.from_bytes(bytes_, byteorder="big") / 10


class SMA:
    # Passed variables
    _ip: str
    _port: int
    _refresh_time: timedelta

    _data: Any
    # Metadata
    _available: bool
    _sma: str
    _uid: str
    _serial_number: str
    # Sensor data
    _grid_consumption: float
    _grid_feed: float
    _phase_one_consumption: float
    _phase_one_feed: float
    _phase_two_consumption: float
    _phase_two_feed: float
    _phase_three_consumption: float
    _phase_three_feed: float

    def __init__(self, name: str, ip: str, port: int, refresh_time: int = 1):
        self._name = name
        self._ip = ip
        self._port = port
        self._refresh_time = timedelta(seconds=refresh_time)

        self._load_metadata()

    def _load_metadata(self):
        self._load_data()
        self._sma = self._data[0:3].decode("UTF-8")
        self._uid = self._data[4:7].hex()
        self._serial_number = self._data[20:24].hex()
        self._available = True

    def _get_socket(self):
        """
        Creates and returns a socker for the SMA Manager
        """
        return create_multicast_socket(self._ip, self._port)

    def _load_data(self):
        """
        Gets data from socket and saves it

        @return: bool
        """
        sock = self._get_socket()
        try:
            self._data = sock.recv(SMA_BUFFER_SIZE)
        finally:
            sock.close()

    @property
    def sma(self):
        return self._sma

    @property
    def uid(self):
        return self._uid

    @property
    def serial_number(self):
        return self._serial_number

    @property
    def name(self):
        return self._name

    @property
    def refresh_time(self):
        return self._refresh_time.seconds

    @refresh_time.setter
    def refresh_time(self, value: int):
        self._refresh_time = timedelta(seconds=value)

    @property
    def available(self):
        return self._available

    @property
    def grid_consumption(self):
        return self._grid_consumption

    @property
    def grid_feed(self):
        return self._grid_feed

    @property
    def phase_one_consumption(self):
        return self._phase_one_consumption

    @property
    def phase_one_feed(self):
        return self._phase_one_feed

    @property
    def phase_two_consumption(self):
        return self._phase_two_consumption

    @property
    def phase_two_feed(self):
        return self._phase_two_feed

    @property
    def phase_three_consumption(self):
        return self._phase_three_consumption

    @property
    def phase_three_feed(self):
        return self._phase_three_feed

    async def refresh_data(self):
        """
        Refreshes the data

        @return:
        """
        try:
            self._load_data()
        except TimeoutError:
            self._available = False
            return

        self._available = True
        self._grid_consumption = _bytes_to_power(self._data[34:36])
        self._grid_feed = _bytes_to_power(self._data[54:56])
        self._phase_one_consumption = _bytes_to_power(self._data[164:308][6:8])
        self._phase_one_feed = _bytes_to_power(self._data[164:308][26:28])
        self._phase_two_consumption = _bytes_to_power(self._data[308:452][6:8])
        self._phase_two_feed = _bytes_to_power(self._data[308:452][26:28])
        self._phase_three_consumption = _bytes_to_power(self._data[452:596][6:8])
        self._phase_three_feed = _bytes_to_power(self._data[452:596][26:28])

"""Implements SoundbarClient which is the extension of temescal library class"""

from __future__ import annotations

import logging
import socket
from queue import Empty, Queue

from temescal import temescal

from .const import CONFIG_DEVICE_TIMEOUT, CONNECT_DEVICE_TIMEOUT, SOUNDBAR_PORT

_LOGGER = logging.getLogger(__name__)


def config_connect(host, port=SOUNDBAR_PORT):
    try:
        soundbar_client = SoundbarClient(host, port=port)
    except ConnectionError:
        _LOGGER.error(f"Connection timeout with server: {host}:{port}")
        return None
    except OSError:
        _LOGGER.error(f"Cannot resolve hostname: {host}")
        return None

    return soundbar_client


def config_device(soundbar_client):
    device_info = {}

    try:
        uuid_q = Queue(maxsize=1)
        name_q = Queue(maxsize=1)

        def config_callback(response):
            if (
                response["msg"] == "PRODUCT_INFO"
                and uuid_q.empty()
                and "s_uuid" in response["data"]
            ):
                uuid_q.put(response["data"]["s_uuid"])
            elif (
                response["msg"] == "SPK_LIST_VIEW_INFO"
                and name_q.empty()
                and "s_user_name" in response["data"]
            ):
                name_q.put(response["data"]["s_user_name"])

        soundbar_client.set_callback(config_callback)
        if uuid_q.empty():
            soundbar_client.get_product_info()
        if name_q.empty():
            soundbar_client.get_info()

        device_info["name"] = name_q.get(timeout=CONFIG_DEVICE_TIMEOUT)
        device_info["uuid"] = uuid_q.get(timeout=CONFIG_DEVICE_TIMEOUT)
    except Empty:
        pass

    return device_info


class SoundbarClient(temescal):
    """The extended implementation of temescal"""

    def __init__(self, address, port=SOUNDBAR_PORT, callback=None, logger=None):
        self.iv = b"'%^Ur7gy$~t+f)%@"
        self.key = b"T^&*J%^7tr~4^%^&I(o%^!jIJ__+a0 k"
        self.address = address
        self.port = port
        self.callback = callback
        self.logger = logger
        self.socket = None
        self.connect()

    def set_callback(self, callback=None):
        self.callback = callback

    def connect(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.settimeout(CONNECT_DEVICE_TIMEOUT)
        self.socket.connect((self.address, self.port))

    """ extended apis below """

    def set_power_key(self, enable):
        data = {
            "cmd": "set",
            "data": {"b_powerkey": enable},
            "msg": "SPK_LIST_VIEW_INFO",
        }
        self.send_packet(data)

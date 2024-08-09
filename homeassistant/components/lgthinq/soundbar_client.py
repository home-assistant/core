# SPDX-FileCopyrightText: Copyright 2024 LG Electronics Inc.
# SPDX-License-Identifier: LicenseRef-LGE-Proprietary

"""Implements LG Soundbar client."""

from __future__ import annotations

from collections.abc import Callable
import logging
from queue import Empty, Queue
import socket
from typing import Any, TYPE_CHECKING

from temescal import temescal

from .const import CONFIG_DEVICE_TIMEOUT, CONNECT_DEVICE_TIMEOUT, SOUNDBAR_PORT

_LOGGER = logging.getLogger(__name__)


def config_connect(host: str, port: int = SOUNDBAR_PORT) -> SoundbarClient | None:
    """Connect to the Soundbar using SoundbarClient."""
    try:
        return SoundbarClient(address=host, port=port)
    except ConnectionError:
        _LOGGER.error("Connection timeout with server: %s:%d", host, port)
    except OSError:
        _LOGGER.error("Cannot resolve hostname: %s", host)

    return None


def config_device(soundbar_client: SoundbarClient) -> dict[str, Any]:
    """Get device information(name, uuid) through the soundbar client."""
    device_info = {}

    if TYPE_CHECKING:
        BaseQueue = Queue[str]
    else:
        BaseQueue = Queue

    try:
        uuid_q: BaseQueue = BaseQueue(maxsize=1)
        name_q: BaseQueue = BaseQueue(maxsize=1)

        def config_callback(response: dict[str, Any]) -> None:
            msg: str | None = response.get("msg")
            data: dict[str, Any] | None = response.get("data")

            if msg == "PRODUCT_INFO" and uuid_q.empty() and "s_uuid" in data:
                uuid_q.put(data.get("s_uuid"))
            elif (
                msg == "SPK_LIST_VIEW_INFO" and name_q.empty() and "s_user_name" in data
            ):
                name_q.put(data.get("s_user_name"))

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
    """Implement the Soundbar client that extends temescal."""

    def __init__(
        self,
        address: str,
        port: int = SOUNDBAR_PORT,
        callback: Callable[[dict], None] | None = None,
    ):
        """Initialize a Soundbar client."""
        self.iv: bytes = b"'%^Ur7gy$~t+f)%@"
        self.key: bytes = b"T^&*J%^7tr~4^%^&I(o%^!jIJ__+a0 k"
        self.address: str = address
        self.port: int = port
        self.callback: Callable[[dict], None] | None = callback
        self.socket: socket.socket | None = None
        self.connect()

    def set_callback(self, callback: Callable[[dict], None] | None = None) -> None:
        """Set a callback method."""
        self.callback = callback

    def connect(self) -> None:
        """Connect to the device."""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.settimeout(CONNECT_DEVICE_TIMEOUT)
        self.socket.connect((self.address, self.port))

    def set_power_key(self, enable: bool) -> None:
        """Send a packet for power key."""
        self.send_packet(
            {
                "cmd": "set",
                "data": {"b_powerkey": enable},
                "msg": "SPK_LIST_VIEW_INFO",
            }
        )

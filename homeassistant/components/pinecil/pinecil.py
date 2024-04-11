"""Pinecil Device."""

from __future__ import annotations

import logging
import struct
from typing import TYPE_CHECKING

from bleak import BleakClient

if TYPE_CHECKING:
    from bleak.backends.device import BLEDevice

_LOGGER = logging.getLogger(__name__)


class Pinecil:
    """Pinecil Device."""

    def __init__(self, ble_device: BLEDevice) -> None:
        """Initialize Pinecil."""
        self._client = BleakClient(ble_device)

    async def get_device_info(self):
        async with self._client as client:

            # service = client.services.get_service("9eae1000-9d0d-48c5-AA55-33e27f9bc533")

            # live = service.get_characteristic("9eae1001-9d0d-48c5-aa55-33e27f9bc533")
            live = await client.read_gatt_char("9eae1001-9d0d-48c5-aa55-33e27f9bc533")
            # result =  service.characteristics
            # for i in result:
            #      _LOGGER.debug(i.uuid)
            # result = await service.read_gatt_char(
            #     "00000001-0000-1000-8000-00805f9b34fb"
            # )
            # battery = ord(bat_char)
            live = struct.unpack("<14I", live)
            _LOGGER.debug(live)

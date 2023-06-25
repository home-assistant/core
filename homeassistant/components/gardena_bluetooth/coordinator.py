"""Provides the switchbot DataUpdateCoordinator."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import TYPE_CHECKING, Any

from bleak.backends.device import BLEDevice
from bleak.exc import BleakError
from gardena_bluetooth import read_char_raw, write_char
from gardena_bluetooth.client import CachedClient
from gardena_bluetooth.exceptions import CharacteristicNoAccess
from gardena_bluetooth.parse import Characteristic, CharacteristicType

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN

if TYPE_CHECKING:
    pass

SCAN_INTERVAL = timedelta(seconds=60)
DISCONNECT_DELAY = 5
LOGGER = logging.getLogger(__name__)


class DeviceUnavailable(UpdateFailed, HomeAssistantError):
    """Raised if device can't be found."""


class Coordinator(DataUpdateCoordinator[dict[str, bytes]]):
    """Class to manage fetching data."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        address: str,
    ) -> None:
        """Initialize global data updater."""
        super().__init__(
            hass=hass,
            logger=logger,
            name="Gardena Bluetooth Data Update Coordinator",
            update_interval=SCAN_INTERVAL,
        )
        self.address = address
        self.data = {}

        def _device_lookup() -> BLEDevice:
            device = bluetooth.async_ble_device_from_address(
                hass, address, connectable=True
            )
            if not device:
                raise DeviceUnavailable("Unable to find device")
            return device

        self.client = CachedClient(DISCONNECT_DELAY, _device_lookup)
        self.characteristics: set[str] = set()

    async def async_shutdown(self) -> None:
        """Shutdown coordinator and any connection."""
        await super().async_shutdown()
        await self.client.disconnect()

    async def _async_update_data(self) -> dict[str, bytes]:
        """Poll the device."""
        uuids: set[str] = {
            uuid for context in self.async_contexts() for uuid in context
        }
        if not uuids:
            return {}

        data: dict[str, bytes] = {}
        try:
            async with self.client() as client:
                for uuid in uuids:
                    try:
                        data[uuid] = await read_char_raw(client, uuid)
                    except CharacteristicNoAccess as exception:
                        LOGGER.debug(
                            "Unable to get data for %s due to %s", uuid, exception
                        )
        except BleakError as exception:
            raise UpdateFailed(
                f"Unable to update data for {uuid} due to {exception}"
            ) from exception
        return data

    def read_cached(
        self, char: Characteristic[CharacteristicType]
    ) -> CharacteristicType | None:
        """Read cached characteristic."""
        if data := self.data.get(char.uuid):
            return char.decode(data)
        return None

    async def write(
        self, char: Characteristic[CharacteristicType], value: CharacteristicType
    ) -> None:
        """Write characteristic to device."""
        try:
            async with self.client() as client:
                await write_char(client, char, value)
        except (CharacteristicNoAccess, BleakError) as exception:
            raise HomeAssistantError(
                f"Unable to write characteristic {char} dur to {exception}"
            ) from exception

        self.data[char.uuid] = char.encode(value)
        await self.async_refresh()


class GardenaBluetoothEntity(CoordinatorEntity[Coordinator]):
    """Coordinator entity for Gardena Bluetooth."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: Coordinator, context: Any = None) -> None:
        """Initialize coordinator entity."""
        super().__init__(coordinator, context)
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, coordinator.address)})

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and bluetooth.async_address_present(
            self.hass, self.coordinator.address, True
        )

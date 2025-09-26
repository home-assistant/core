"""Provides the DataUpdateCoordinator."""

from __future__ import annotations

from datetime import timedelta
import logging

from gardena_bluetooth.client import Client
from gardena_bluetooth.exceptions import (
    CharacteristicNoAccess,
    GardenaBluetoothException,
)
from gardena_bluetooth.parse import Characteristic, CharacteristicType

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

SCAN_INTERVAL = timedelta(seconds=60)
LOGGER = logging.getLogger(__name__)

type GardenaBluetoothConfigEntry = ConfigEntry[GardenaBluetoothCoordinator]


class DeviceUnavailable(HomeAssistantError):
    """Raised if device can't be found."""


class GardenaBluetoothCoordinator(DataUpdateCoordinator[dict[str, bytes]]):
    """Class to manage fetching data."""

    config_entry: GardenaBluetoothConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: GardenaBluetoothConfigEntry,
        logger: logging.Logger,
        client: Client,
        characteristics: set[str],
        device_info: DeviceInfo,
        address: str,
    ) -> None:
        """Initialize global data updater."""
        super().__init__(
            hass=hass,
            logger=logger,
            config_entry=config_entry,
            name="Gardena Bluetooth Data Update Coordinator",
            update_interval=SCAN_INTERVAL,
        )
        self.address = address
        self.data = {}
        self.client = client
        self.characteristics = characteristics
        self.device_info = device_info

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
        for uuid in uuids:
            try:
                data[uuid] = await self.client.read_char_raw(uuid)
            except CharacteristicNoAccess as exception:
                LOGGER.debug("Unable to get data for %s due to %s", uuid, exception)
            except (GardenaBluetoothException, DeviceUnavailable) as exception:
                raise UpdateFailed(
                    f"Unable to update data for {uuid} due to {exception}"
                ) from exception
        return data

    def get_cached(
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
            await self.client.write_char(char, value)
        except (GardenaBluetoothException, DeviceUnavailable) as exception:
            raise HomeAssistantError(
                f"Unable to write characteristic {char} dur to {exception}"
            ) from exception

        self.data[char.uuid] = char.encode(value)
        await self.async_refresh()

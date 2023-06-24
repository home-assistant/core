"""Provides the switchbot DataUpdateCoordinator."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import timedelta
import logging
from typing import TYPE_CHECKING, Any

from bleak import BleakClient
from bleak.exc import BleakError
from bleak_retry_connector import establish_connection
from gardena_bluetooth import read_char_raw, write_char
from gardena_bluetooth.exceptions import CharacteristicNoAccess
from gardena_bluetooth.parse import Characteristic, CharacteristicType

from homeassistant.components import bluetooth
from homeassistant.core import CALLBACK_TYPE, HassJob, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN

if TYPE_CHECKING:
    pass

SCAN_INTERVAL = timedelta(seconds=60)
DISCONNECT_DELAY = timedelta(seconds=5)
LOGGER = logging.getLogger(__name__)


class DeviceUnavailable(UpdateFailed, HomeAssistantError):
    """Raised if device can't be found."""


class CallLaterJob:
    """Helper to contain a function that is to be called later."""

    def __init__(self, hass: HomeAssistant, fun: Callable[[], Awaitable[None]]) -> None:
        """Initialize a call later job."""
        self._fun = fun
        self._hass = hass
        self._cancel: CALLBACK_TYPE | None = None

        async def _call(_):
            self._cancel = None
            await self.call_now()

        self._job = HassJob(_call)

    def cancel(self):
        """Cancel any pending delay call."""
        if self._cancel:
            self._cancel()
            self._cancel = None

    async def call_now(self):
        """Call function now."""
        self.cancel()
        await self._fun()

    def call_later(self, delay: float | timedelta):
        """Call function sometime later."""
        self.cancel()
        self._cancel = async_call_later(self._hass, delay, self._job)


class CachedClient:
    """Recursive and delay closed client."""

    def __init__(self, hass: HomeAssistant, address: str) -> None:
        """Initialize cached client."""

        self._hass = hass
        self._client: BleakClient | None = None
        self._lock = asyncio.Lock()
        self._count = 0
        self._address = address

        self.disconnect = CallLaterJob(hass, self._disconnect)

    async def _disconnect(self):
        async with self._lock:
            if client := self._client:
                LOGGER.debug("Disconnecting from %s", self._address)
                self._client = None
                await client.disconnect()

    async def _connect(self) -> BleakClient:
        LOGGER.debug("Connecting to %s", self._address)

        ble_device = bluetooth.async_ble_device_from_address(
            self._hass, self._address, connectable=True
        )
        if not ble_device:
            raise DeviceUnavailable("Unable to find device")

        self._client = await establish_connection(
            BleakClient, ble_device, "Gardena Bluetooth", use_services_cache=True
        )
        LOGGER.debug("Connected to %s", self._address)
        return self._client

    @asynccontextmanager
    async def __call__(self):
        """Retrieve a context manager for a cached client."""
        self.disconnect.cancel()

        async with self._lock:
            if not (client := self._client) or not client.is_connected:
                client = await self._connect()

            self._count += 1
            try:
                yield client
            except:
                LOGGER.debug("Disconnecting client due to exception")
                await self.disconnect.call_now()
                raise

            finally:
                self._count -= 1

                if not self._count and self._client:
                    self.disconnect.call_later(DISCONNECT_DELAY)


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
        self.client = CachedClient(hass, address)
        self.characteristics: set[str] = set()

    async def async_shutdown(self) -> None:
        """Shutdown coordinator and any connection."""
        await super().async_shutdown()
        await self.client.disconnect.call_now()

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
                    data[uuid] = await read_char_raw(client, uuid)
        except (CharacteristicNoAccess, BleakError) as exception:
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

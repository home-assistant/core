"""Support for Comelit."""
import asyncio
from collections.abc import Callable
from datetime import timedelta

from aiocomelit import (
    ComeliteSerialBridgeAPi,
    ComelitSerialBridgeObject,
    ComelitVedoObject,
)
import aiohttp

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import _LOGGER, COORDINATOR_CTX_ALARM, COORDINATOR_CTX_DEVICES, DOMAIN


class ComelitSerialBridge(DataUpdateCoordinator):
    """Queries Comelit Serial Bridge."""

    def __init__(self, host: str, pin: int, hass: HomeAssistant) -> None:
        """Initialize the scanner."""

        self._host = host
        self._pin = pin
        self._devices: list[ComelitSerialBridgeObject] = []
        self._alarm: list[ComelitVedoObject] = []
        self._on_close: list[Callable] = []

        self.api = ComeliteSerialBridgeAPi(host, pin)

        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=f"{DOMAIN}-{host}-coordinator",
            update_interval=timedelta(seconds=5),
        )

    @callback
    def async_on_close(self, func: CALLBACK_TYPE) -> None:
        """Add a function to call when router is closed."""
        self._on_close.append(func)

    async def _async_update_data(self) -> dict[str, list]:
        """Update router data."""
        data: dict = {
            COORDINATOR_CTX_DEVICES: [],
            COORDINATOR_CTX_ALARM: [],
        }
        _LOGGER.debug("Polling Comelit Serial Bridge host: %s", self._host)
        try:
            logged = await self.api.login()
        except (asyncio.exceptions.TimeoutError, aiohttp.ClientConnectorError) as err:
            _LOGGER.warning("Connection error for %s", self._host)
            raise UpdateFailed(f"Error fetching data: {repr(err)}") from err

        if not logged:
            raise ConfigEntryAuthFailed

        self._devices = await self.api.get_all_devices()
        data[COORDINATOR_CTX_DEVICES] = self._devices
        await self.api.logout()

        return data

    @property
    def devices(self) -> list[ComelitSerialBridgeObject]:
        """Return a list of devices."""
        return self._devices

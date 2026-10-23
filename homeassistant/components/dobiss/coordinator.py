"""Coordinate REST updates for Dobiss NXT."""

from asyncio import Lock
from datetime import timedelta
import logging
from typing import override

from dobiss_nxt import DobissAuthenticationError, DobissClient, DobissError, Light

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

type DobissConfigEntry = ConfigEntry[DobissCoordinator]


class DobissCoordinator(DataUpdateCoordinator[dict[str, int | None]]):
    """Fetch the installation status once for all lights."""

    def __init__(
        self, hass: HomeAssistant, entry: DobissConfigEntry, client: DobissClient
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name="Dobiss",
            update_interval=timedelta(seconds=10),
            always_update=True,
        )
        self.client = client
        self._request_lock = Lock()
        self.lights: tuple[Light, ...] = ()

    async def async_set_light(
        self, light: Light, *, on: bool, brightness: int | None = None
    ) -> None:
        """Publish accepted commands without waiting for a debounced refresh."""
        async with self._request_lock:
            await self.client.set_light(light, on=on, brightness=brightness)
            if not on:
                value = 0
            elif brightness is not None:
                value = brightness
            elif light.dimmable:
                value = self.data.get(light.key) or 100
            else:
                value = 1
            self.data = {**self.data, light.key: value}
            self.async_update_listeners()

    @override
    async def _async_setup(self) -> None:
        """Discover outputs once before the first state update."""
        try:
            self.lights = await self.client.discover_lights()
        except DobissAuthenticationError as err:
            raise ConfigEntryAuthFailed("Dobiss rejected the API secret") from err
        except DobissError as err:
            raise UpdateFailed("Unable to discover Dobiss outputs") from err

    @override
    async def _async_update_data(self) -> dict[str, int | None]:
        """Refresh output status."""
        try:
            async with self._request_lock:
                return await self.client.light_states(self.lights)
        except DobissAuthenticationError as err:
            raise ConfigEntryAuthFailed("Dobiss rejected the API secret") from err
        except DobissError as err:
            raise UpdateFailed("Unable to fetch Dobiss status") from err

"""Coordinate REST updates for Dobiss NXT."""

from asyncio import Lock
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import override

from dobiss_nxt import DobissAuthenticationError, DobissClient, DobissError, Light

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

type DobissConfigEntry = ConfigEntry[DobissCoordinator]


@dataclass(frozen=True)
class DobissLightData:
    """A discovered light and its available controller state."""

    light: Light
    value: int


class DobissCoordinator(DataUpdateCoordinator[dict[str, DobissLightData]]):
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
                previous = self.data.get(light.key)
                value = previous.value if previous and previous.value else 100
            else:
                value = 1
            self.data = {**self.data, light.key: DobissLightData(light, value)}
            self.async_update_listeners()

    @override
    async def _async_setup(self) -> None:
        """Discover outputs once before the first state update."""
        try:
            self.lights = await self.client.discover_lights()
        except DobissAuthenticationError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="invalid_auth"
            ) from err
        except DobissError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="discovery_failed"
            ) from err

    @override
    async def _async_update_data(self) -> dict[str, DobissLightData]:
        """Refresh output status."""
        try:
            async with self._request_lock:
                states = await self.client.light_states(self.lights)
        except DobissAuthenticationError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="invalid_auth"
            ) from err
        except DobissError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="status_failed"
            ) from err
        return {
            light.key: DobissLightData(light, value)
            for light in self.lights
            if (value := states.get(light.key)) is not None
        }

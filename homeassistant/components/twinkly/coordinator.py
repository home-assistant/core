"""Coordinator for Twinkly."""

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any

from aiohttp import ClientError
from awesomeversion import AwesomeVersion
from ttls.client import Twinkly, TwinklyError

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEV_NAME, DOMAIN, MIN_EFFECT_VERSION

_LOGGER = logging.getLogger(__name__)


@dataclass
class TwinklyData:
    """Class for Twinkly data."""

    device_info: dict[str, Any]
    brightness: int
    is_on: bool
    movies: dict[int, str]
    current_movie: int | None
    current_mode: str | None


class TwinklyCoordinator(DataUpdateCoordinator[TwinklyData]):
    """Class to manage fetching Twinkly data from API."""

    software_version: str
    supports_effects: bool
    device_name: str

    def __init__(self, hass: HomeAssistant, client: Twinkly) -> None:
        """Initialize global Twinkly data updater."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )
        self.client = client

    async def _async_setup(self) -> None:
        """Set up the Twinkly data."""
        try:
            software_version = await self.client.get_firmware_version()
            self.device_name = (await self.client.get_details())[DEV_NAME]
        except (TimeoutError, ClientError) as exception:
            raise UpdateFailed from exception
        self.software_version = software_version["version"]
        self.supports_effects = AwesomeVersion(self.software_version) >= AwesomeVersion(
            MIN_EFFECT_VERSION
        )

    async def _async_update_data(self) -> TwinklyData:
        """Fetch data from Twinkly."""
        movies: list[dict[str, Any]] = []
        current_movie: dict[str, Any] = {}
        try:
            device_info = await self.client.get_details()
            brightness = await self.client.get_brightness()
            is_on = await self.client.is_on()
            mode_data = await self.client.get_mode()
            current_mode = mode_data.get("mode")
            if self.supports_effects:
                movies = (await self.client.get_saved_movies())["movies"]
        except (TimeoutError, ClientError) as exception:
            raise UpdateFailed from exception
        if self.supports_effects:
            try:
                current_movie = await self.client.get_current_movie()
            except (TwinklyError, TimeoutError, ClientError) as exception:
                _LOGGER.debug("Error fetching current movie: %s", exception)
        brightness = (
            int(brightness["value"]) if brightness["mode"] == "enabled" else 100
        )
        brightness = int(round(brightness * 2.55)) if is_on else 0
        if self.device_name != device_info[DEV_NAME]:
            self._async_update_device_info(device_info[DEV_NAME])
        return TwinklyData(
            device_info,
            brightness,
            is_on,
            {movie["id"]: movie["name"] for movie in movies},
            current_movie.get("id"),
            current_mode,
        )

    def _async_update_device_info(self, name: str) -> None:
        """Update the device info."""
        device_registry = dr.async_get(self.hass)
        device = device_registry.async_get_device(
            identifiers={(DOMAIN, self.data.device_info["mac"])},
        )
        if device:
            device_registry.async_update_device(
                device.id,
                name=name,
            )

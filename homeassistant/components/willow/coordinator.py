"""Coordinator for the Willow integration."""

from collections.abc import Mapping
from typing import NotRequired, TypedDict, cast

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import WillowClient
from .const import DOMAIN, LOGGER, SCAN_INTERVAL
from .exceptions import WillowAuthError


class WillowProfile(TypedDict):
    """Willow profile response."""

    id: int
    username: str
    profile_image: str | None


class WillowUserPlant(TypedDict):
    """Willow user plant data."""

    id: int
    name: str
    location: str | None


class WillowReading(TypedDict):
    """Willow latest reading data."""

    timestamp: str
    temperature: float
    humidity: float
    moisture: float
    light: float


class WillowDevice(TypedDict):
    """Willow paired sensor data."""

    id: int
    sensor_id: str
    battery_life: int | float | None
    version: str | None
    user_plant: WillowUserPlant
    latest_reading: WillowReading | None
    profile_image: NotRequired[str | None]


class WillowDataUpdateCoordinator(DataUpdateCoordinator[dict[str, WillowDevice]]):
    """Coordinator for Willow data updates."""

    config_entry: ConfigEntry
    profile: WillowProfile

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        client: WillowClient,
        oauth_session: OAuth2Session,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.client = client
        self._oauth_session = oauth_session

    async def _async_update_data(self) -> dict[str, WillowDevice]:
        """Fetch Willow profile and devices."""
        try:
            await self._oauth_session.async_ensure_token_valid()
            self.client.update_token(self._oauth_session.token[CONF_ACCESS_TOKEN])
            self.profile = cast(WillowProfile, await self.client.get_profile())
            devices = await self.client.get_devices()
        except WillowAuthError as err:
            raise ConfigEntryAuthFailed from err
        except Exception as err:
            raise UpdateFailed(f"Unable to fetch Willow data: {err}") from err

        return {
            str(device["sensor_id"]): cast(WillowDevice, device)
            for device in devices
            if isinstance(device, Mapping) and device.get("sensor_id")
        }

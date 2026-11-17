"""Coordinator for the Willow integration."""

from typing import override

from aiohttp import ClientError
from pywillow import (
    WillowApiError,
    WillowAuthError,
    WillowClient,
    WillowDevice,
    WillowProfile,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, SCAN_INTERVAL

type WillowConfigEntry = ConfigEntry[WillowDataUpdateCoordinator]


class WillowDataUpdateCoordinator(DataUpdateCoordinator[dict[str, WillowDevice]]):
    """Coordinator for Willow data updates."""

    config_entry: WillowConfigEntry
    profile: WillowProfile

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: WillowConfigEntry,
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

    @override
    async def _async_setup(self) -> None:
        """Fetch the Willow profile once."""
        await self._oauth_session.async_ensure_token_valid()
        self.client.update_token(self._oauth_session.token[CONF_ACCESS_TOKEN])
        try:
            self.profile = await self.client.get_profile()
        except WillowAuthError as err:
            raise ConfigEntryAuthFailed from err
        except (ClientError, WillowApiError) as err:
            raise UpdateFailed(f"Unable to fetch Willow profile: {err}") from err

    @override
    async def _async_update_data(self) -> dict[str, WillowDevice]:
        """Fetch Willow devices."""
        await self._oauth_session.async_ensure_token_valid()
        self.client.update_token(self._oauth_session.token[CONF_ACCESS_TOKEN])
        try:
            devices = await self.client.get_devices()
        except WillowAuthError as err:
            raise ConfigEntryAuthFailed from err
        except (ClientError, WillowApiError) as err:
            raise UpdateFailed(f"Unable to fetch Willow data: {err}") from err

        return {device["sensor_id"]: device for device in devices}

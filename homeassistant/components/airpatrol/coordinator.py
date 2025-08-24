"""Data update coordinator for AirPatrol."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from airpatrol.api import AirPatrolAPI, AirPatrolAuthenticationError, AirPatrolError

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, SCAN_INTERVAL

if TYPE_CHECKING:
    from . import AirPatrolConfigEntry


class AirPatrolDataUpdateCoordinator(DataUpdateCoordinator[list[dict[str, Any]]]):
    """Class to manage fetching AirPatrol data."""

    config_entry: AirPatrolConfigEntry
    api: AirPatrolAPI | None = None

    def __init__(self, hass: HomeAssistant, config_entry: AirPatrolConfigEntry) -> None:
        """Initialize."""

        super().__init__(
            hass,
            LOGGER,
            name=f"{DOMAIN.capitalize()} {config_entry.data['email']}",
            update_interval=SCAN_INTERVAL,
            config_entry=config_entry,
        )

    async def _async_update_data(self) -> list[dict[str, Any]]:
        """Fetch data from API."""
        try:
            client = await self.async_get_api_client()
            return await client.get_data()
        except AirPatrolAuthenticationError:
            try:
                await self._async_refresh_client()
                client = await self.async_get_api_client()
                return await client.get_data()
            except AirPatrolAuthenticationError as refresh_err:
                raise ConfigEntryAuthFailed(
                    "Authentication with AirPatrol failed after token refresh"
                ) from refresh_err
        except AirPatrolError as err:
            raise UpdateFailed(
                f"Error communicating with AirPatrol API: {err}"
            ) from err

    async def async_get_api_client(self) -> AirPatrolAPI:
        """Get the AirPatrol API client."""
        if self.api:
            return self.api

        session = async_get_clientsession(self.hass)
        # Check if we have a stored access token
        if "access_token" in self.config_entry.data:
            # Use stored access token for authentication
            token = self.config_entry.data["access_token"]
            uid = self.config_entry.unique_id  # Set the UID from the config entry
            api = AirPatrolAPI(session, token, uid)
            # Validate the token is still valid by making a test API call
            await api.get_data()
            LOGGER.debug("Using stored access token for authentication")
            self.api = api
        else:
            api = await self._async_refresh_client()

        return api

    async def _async_refresh_client(self) -> AirPatrolAPI:
        session = async_get_clientsession(self.hass)
        api = await AirPatrolAPI.authenticate(
            session,
            self.config_entry.data["email"],
            self.config_entry.data["password"],
        )
        # Store the new access token using the proper method
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            data={
                **self.config_entry.data,
                "access_token": api.get_access_token(),
            },
        )

        self.api = api
        return api

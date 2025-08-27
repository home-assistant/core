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


class AirPatrolDataUpdateCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Class to manage fetching AirPatrol data."""

    config_entry: AirPatrolConfigEntry
    api: AirPatrolAPI

    def __init__(self, hass: HomeAssistant, config_entry: AirPatrolConfigEntry) -> None:
        """Initialize."""

        super().__init__(
            hass,
            LOGGER,
            name=f"{DOMAIN.capitalize()} {config_entry.title}",
            update_interval=SCAN_INTERVAL,
            config_entry=config_entry,
        )

    async def _async_setup(self):
        try:
            await self._update_token()
        except AirPatrolError as api_err:
            raise UpdateFailed(
                f"Error communicating with AirPatrol API: {api_err}"
            ) from api_err

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Update unit data from AirPatrol API."""
        return {unit_data["unit_id"]: unit_data for unit_data in await self._get_data()}

    async def _get_data(self, retry: bool = False) -> list[dict[str, Any]]:
        """Fetch data from API."""
        try:
            return await self.api.get_data()
        except AirPatrolAuthenticationError as auth_err:
            if retry:
                raise ConfigEntryAuthFailed(
                    "Authentication with AirPatrol failed"
                ) from auth_err
            await self._update_token()
            return await self._get_data(retry=True)
        except AirPatrolError as err:
            raise UpdateFailed(
                f"Error communicating with AirPatrol API: {err}"
            ) from err

    async def _update_token(self) -> None:
        """Refresh the AirPatrol API client and update the access token."""
        session = async_get_clientsession(self.hass)
        try:
            self.api = await AirPatrolAPI.authenticate(
                session,
                self.config_entry.data["email"],
                self.config_entry.data["password"],
            )
        except AirPatrolAuthenticationError as auth_err:
            raise ConfigEntryAuthFailed(
                "Authentication with AirPatrol failed"
            ) from auth_err

        # Store the new access token
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            data={
                **self.config_entry.data,
                "access_token": self.api.get_access_token(),
            },
        )

"""Coordinator to update data from Aquacell API."""

import asyncio
import logging
import time
from typing import override

from aioaquacell import (
    AquacellApi,
    AquacellApiException,
    AuthenticationFailed,
    Softener,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_REFRESH_TOKEN,
    CONF_REFRESH_TOKEN_CREATION_TIME,
    DOMAIN,
    REFRESH_TOKEN_EXPIRY_TIME,
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

type AquacellConfigEntry = ConfigEntry[AquacellCoordinator]


class AquacellCoordinator(DataUpdateCoordinator[dict[str, Softener]]):
    """My aquacell coordinator."""

    config_entry: AquacellConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: AquacellConfigEntry,
        aquacell_api: AquacellApi,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name="Aquacell Coordinator",
            update_interval=UPDATE_INTERVAL,
        )

        self.refresh_token = self.config_entry.data[CONF_REFRESH_TOKEN]
        self.refresh_token_creation_time = self.config_entry.data[
            CONF_REFRESH_TOKEN_CREATION_TIME
        ]
        self.email = self.config_entry.data[CONF_EMAIL]
        self.password = self.config_entry.data[CONF_PASSWORD]
        self.aquacell_api = aquacell_api

    @override
    async def _async_update_data(self) -> dict[str, Softener]:
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """

        async with asyncio.timeout(30):
            # Check if the refresh token is expired
            expiry_time = (
                self.refresh_token_creation_time
                + REFRESH_TOKEN_EXPIRY_TIME.total_seconds()
            )
            try:
                if time.time() >= expiry_time:
                    await self._reauthenticate()
                else:
                    await self.aquacell_api.authenticate_refresh(self.refresh_token)
                _LOGGER.debug("Logged in using: %s", self.refresh_token)

                softeners = await self.aquacell_api.get_all_softeners()
            except AuthenticationFailed as err:
                raise ConfigEntryAuthFailed from err
            except (AquacellApiException, TimeoutError) as err:
                raise UpdateFailed(f"Error communicating with API: {err}") from err

        data = {softener.dsn: softener for softener in softeners}
        # An empty list is more likely a cloud error than all softeners being removed
        if data:
            self._remove_stale_devices(data)
        return data

    def _remove_stale_devices(self, softeners: dict[str, Softener]) -> None:
        """Remove devices of softeners that are no longer returned by the API."""
        device_registry = dr.async_get(self.hass)
        for device in dr.async_entries_for_config_entry(
            device_registry, self.config_entry.entry_id
        ):
            if not any(
                identifier[0] == DOMAIN and identifier[1] in softeners
                for identifier in device.identifiers
            ):
                _LOGGER.debug("Removing stale device %s", device.name)
                device_registry.async_remove_device(device.id)

    async def _reauthenticate(self) -> None:
        _LOGGER.debug("Attempting to renew refresh token")
        refresh_token = await self.aquacell_api.authenticate(self.email, self.password)
        self.refresh_token = refresh_token
        data = {
            **self.config_entry.data,
            CONF_REFRESH_TOKEN: self.refresh_token,
            CONF_REFRESH_TOKEN_CREATION_TIME: time.time(),
        }

        self.hass.config_entries.async_update_entry(self.config_entry, data=data)

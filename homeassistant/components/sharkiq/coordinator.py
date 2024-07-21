"""Data update coordinator for shark iq vacuums."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from sharkiq import (
    AylaApi,
    SharkIqAuthError,
    SharkIqAuthExpiringError,
    SharkIqNotAuthedError,
    SharkIqVacuum,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import API_TIMEOUT, DOMAIN, LOGGER, UPDATE_INTERVAL


class SharkIqUpdateCoordinator(DataUpdateCoordinator[bool]):
    """Define a wrapper class to update Shark IQ data."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        ayla_api: AylaApi,
        shark_vacs: list[SharkIqVacuum],
    ) -> None:
        """Set up the SharkIqUpdateCoordinator class."""
        self.ayla_api = ayla_api
        self.shark_vacs: dict[str, SharkIqVacuum] = {
            sharkiq.serial_number: sharkiq for sharkiq in shark_vacs
        }
        self._config_entry = config_entry
        self._online_dsns: set[str] = set()

        super().__init__(hass, LOGGER, name=DOMAIN, update_interval=UPDATE_INTERVAL)

    @property
    def online_dsns(self) -> set[str]:
        """Get the set of all online DSNs."""
        return self._online_dsns

    def device_is_online(self, dsn: str) -> bool:
        """Return the online state of a given vacuum dsn."""
        return dsn in self._online_dsns

    @staticmethod
    async def _async_update_vacuum(sharkiq: SharkIqVacuum) -> None:
        """Asynchronously update the data for a single vacuum."""
        dsn = sharkiq.serial_number
        LOGGER.debug("Updating sharkiq data for device DSN %s", dsn)
        async with asyncio.timeout(API_TIMEOUT):
            await sharkiq.async_update()

    async def _async_update_data(self) -> bool:
        """Update data device by device."""
        try:
            if (
                self.ayla_api.token_expiring_soon
                or datetime.now()
                > self.ayla_api.auth_expiration - timedelta(seconds=600)
            ):
                await self.ayla_api.async_refresh_auth()

            all_vacuums = await self.ayla_api.async_list_devices()
            self._online_dsns = {
                v["dsn"]
                for v in all_vacuums
                if v["connection_status"] == "Online" and v["dsn"] in self.shark_vacs
            }

            LOGGER.debug("Updating sharkiq data")
            online_vacs = (self.shark_vacs[dsn] for dsn in self.online_dsns)
            await asyncio.gather(*(self._async_update_vacuum(v) for v in online_vacs))
        except (
            SharkIqAuthError,
            SharkIqNotAuthedError,
            SharkIqAuthExpiringError,
        ) as err:
            LOGGER.debug("Bad auth state.  Attempting re-auth", exc_info=err)
            raise ConfigEntryAuthFailed from err
        except Exception as err:
            LOGGER.exception("Unexpected error updating SharkIQ.  Attempting re-auth")
            raise UpdateFailed(err) from err

        return True

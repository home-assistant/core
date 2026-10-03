"""Cloud polling coordinator for DRIQON devices."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import TYPE_CHECKING, cast

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    DriqonApi,
    DriqonApiError,
    DriqonAuthError,
    DriqonInvalidApiKeyError,
)
from .const import DOMAIN, UPDATE_INTERVAL_SECONDS
from .types import DeviceMap, DriqonConfigEntryData

if TYPE_CHECKING:
    from . import DriqonConfigEntry

_LOGGER = logging.getLogger(__name__)


class DriqonCoordinator(DataUpdateCoordinator[DeviceMap]):
    """Fetch account-visible devices and keep the config token current."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: DriqonApi,
        entry: DriqonConfigEntry,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL_SECONDS),
            always_update=False,
        )
        self.api = api
        self.entry = entry

    async def _async_update_data(self) -> DeviceMap:
        """Fetch devices, recover automatically, and initiate reauth if needed."""
        try:
            devices = await self.api.devices()
        except (DriqonAuthError, DriqonInvalidApiKeyError) as err:
            raise ConfigEntryAuthFailed from err
        except DriqonApiError as err:
            raise UpdateFailed("Could not update DRIQON devices") from err

        entry_data = cast(DriqonConfigEntryData, self.entry.data)
        if entry_data["refresh_token"] != self.api.refresh_token:
            self.hass.config_entries.async_update_entry(
                self.entry,
                data={**self.entry.data, "refresh_token": self.api.refresh_token},
            )
        return {device["device_id"]: device for device in devices}

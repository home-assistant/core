"""Coordinator for the vizio component."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from pyvizio.const import APPS
from pyvizio.util import gen_apps_list_from_url

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class VizioAppsDataUpdateCoordinator(DataUpdateCoordinator[list[dict[str, Any]]]):
    """Define an object to hold Vizio app config data."""

    def __init__(self, hass: HomeAssistant, store: Store[list[dict[str, Any]]]) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(days=1),
        )
        self.fail_count = 0
        self.fail_threshold = 10
        self.store = store

    async def async_config_entry_first_refresh(self) -> None:
        """Refresh data for the first time when a config entry is setup."""
        self.data = await self.store.async_load() or APPS
        await super().async_config_entry_first_refresh()

    async def _async_update_data(self) -> list[dict[str, Any]]:
        """Update data via library."""
        if data := await gen_apps_list_from_url(
            session=async_get_clientsession(self.hass)
        ):
            # Reset the fail count and threshold when the data is successfully retrieved
            self.fail_count = 0
            self.fail_threshold = 10
            # Store the new data if it has changed so we have it for the next restart
            if data != self.data:
                await self.store.async_save(data)
            return data
        # For every failure, increase the fail count until we reach the threshold.
        # We then log a warning, increase the threshold, and reset the fail count.
        # This is here to prevent silent failures but to reduce repeat logs.
        if self.fail_count == self.fail_threshold:
            _LOGGER.warning(
                (
                    "Unable to retrieve the apps list from the external server for the "
                    "last %s days"
                ),
                self.fail_threshold,
            )
            self.fail_count = 0
            self.fail_threshold += 10
        else:
            self.fail_count += 1
        return self.data

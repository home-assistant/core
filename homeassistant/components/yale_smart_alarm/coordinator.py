"""DataUpdateCoordinator for the Yale integration."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from yalesmartalarmclient.client import AuthenticationError, YaleSmartAlarmClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CODE, CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers.storage import STORAGE_DIR
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import Throttle

from .const import (
    CONF_AREA_ID,
    DEFAULT_AREA_ID,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LOGGER,
)


class YaleDataUpdateCoordinator(DataUpdateCoordinator):
    """A Yale Data Update Coordinator."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the Verisure hub."""
        self._entry = entry
        self._hass = hass
        self._yale = None

        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    async def _async_update_data(self) -> dict:
        """Fetch data from Yale."""

        if self._yale == None:
            self._yale = await self._hass.async_add_executor_job(
                YaleSmartAlarmClient,
                self._entry.data[CONF_USERNAME],
                self._entry.data[CONF_PASSWORD],
            )

        try:
            arm_status = await self._hass.async_add_executor_job(
                self._yale.get_armed_status
            )
            door_locks = await self._hass.async_add_executor_job(
                self._yale.get_locks_status
            )
            door_status = await self._hass.async_add_executor_job(
                self._yale.get_doors_status
            )

        except AuthenticationError as ae:
            LOGGER.error("Authentication failed. Check credentials %s", ae)
            raise

        return {
            "alarm": arm_status,
            "lock": door_locks,
            "door_window": door_status,
        }

"""Provides the switchbot DataUpdateCoordinator."""
from __future__ import annotations

from datetime import timedelta
import json
import logging

import switchbot

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def flatten_sensors_data(sensor):
    """Deconstruct SwitchBot library temp object C/Fº readings from dictionary."""

    _LOGGER.debug(
        "Sensor '%s' data retrieved from API: %s",
        sensor["mac_address"],
        json.dumps(sensor["data"]),
    )

    if "temp" in sensor["data"]:
        sensor["data"]["temperature"] = sensor["data"]["temp"]["c"]
        _LOGGER.debug(
            "Enriched sensor '%s' data: %s",
            sensor["mac_address"],
            json.dumps(sensor["data"]),
        )

    return sensor


class SwitchbotDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching switchbot data."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        update_interval: int,
        api: switchbot,
        retry_count: int,
        scan_timeout: int,
    ) -> None:
        """Initialize global switchbot data updater."""
        self.switchbot_api = api
        self.switchbot_data = self.switchbot_api.GetSwitchbotDevices()
        self.retry_count = retry_count
        self.scan_timeout = scan_timeout
        self.update_interval = timedelta(seconds=update_interval)

        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=self.update_interval
        )

    async def _async_update_data(self) -> dict | None:
        """Fetch data from switchbot."""

        switchbot_data = await self.switchbot_data.discover(
            retry=self.retry_count, scan_timeout=self.scan_timeout
        )

        if not switchbot_data:
            raise UpdateFailed("Unable to fetch switchbot services data")

        return {
            identifier: flatten_sensors_data(sensor)
            for identifier, sensor in switchbot_data.items()
        }

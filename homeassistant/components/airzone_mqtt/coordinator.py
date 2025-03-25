"""Coordinator classes for Airzone MQTT integration."""

from __future__ import annotations

from asyncio import timeout
from datetime import timedelta
import logging
from typing import Any

from airzone_mqtt.exceptions import AirzoneMqttError
from airzone_mqtt.mqttapi import AirzoneMqttApi

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import AIRZONE_TIMEOUT_SEC, DOMAIN

SCAN_INTERVAL = timedelta(seconds=60)

_LOGGER = logging.getLogger(__name__)

type AirzoneMqttConfigEntry = ConfigEntry[AirzoneUpdateCoordinator]


class AirzoneUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching data from the Airzone device."""

    config_entry: AirzoneMqttConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: AirzoneMqttConfigEntry,
        airzone: AirzoneMqttApi,
    ) -> None:
        """Initialize."""
        self.airzone = airzone
        self.airzone.set_update_callback(self.async_set_updated_data)

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        async with timeout(AIRZONE_TIMEOUT_SEC):
            try:
                await self.airzone.update()
            except AirzoneMqttError as error:
                raise UpdateFailed(error) from error
            return self.airzone.data()

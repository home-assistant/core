"""Coordinator for the SensorPush Cloud integration."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_ID,
    ATTR_MODEL,
    ATTR_NAME,
    ATTR_TEMPERATURE,
    CONF_EMAIL,
    CONF_PASSWORD,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import SensorPushCloudApi, SensorPushCloudError
from .const import (
    ATTR_ALTITUDE,
    ATTR_ATMOSPHERIC_PRESSURE,
    ATTR_BATTERY_VOLTAGE,
    ATTR_DEWPOINT,
    ATTR_HUMIDITY,
    ATTR_LAST_UPDATE,
    ATTR_SIGNAL_STRENGTH,
    ATTR_VAPOR_PRESSURE,
    LOGGER,
    UPDATE_INTERVAL,
)

type SensorPushCloudConfigEntry = ConfigEntry[SensorPushCloudCoordinator]


class SensorPushCloudCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """SensorPush Cloud coordinator."""

    api: SensorPushCloudApi
    devices: dict[str, Any]

    def __init__(self, hass: HomeAssistant, entry: SensorPushCloudConfigEntry) -> None:
        """Initialize the coordinator."""
        email, password = entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD]
        self.api = SensorPushCloudApi(email, password)
        self.devices = {}
        super().__init__(
            hass, LOGGER, name=entry.title, update_interval=UPDATE_INTERVAL
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API endpoints."""
        data: dict[str, Any] = {}
        try:
            # Sensor data is spread across two endpoints, which are requested
            # in parallel and denormalized before handing off to entities.
            sensors, samples = await asyncio.gather(
                self.api.async_sensors(),
                self.api.async_samples(limit=1),
            )
            for device_id, sensor in sensors.items():
                sample = samples.sensors[device_id][0]

                if device_id not in self.devices:
                    self.devices[device_id] = {
                        ATTR_DEVICE_ID: sensor.device_id,
                        ATTR_MODEL: sensor.type,
                        ATTR_NAME: sensor.name,
                    }

                data[device_id] = {
                    ATTR_ALTITUDE: sample.altitude,
                    ATTR_ATMOSPHERIC_PRESSURE: sample.barometric_pressure,
                    ATTR_BATTERY_VOLTAGE: sensor.battery_voltage,
                    ATTR_DEWPOINT: sample.dewpoint,
                    ATTR_HUMIDITY: sample.humidity,
                    ATTR_LAST_UPDATE: sample.observed,
                    ATTR_SIGNAL_STRENGTH: sensor.rssi,
                    ATTR_TEMPERATURE: sample.temperature,
                    ATTR_VAPOR_PRESSURE: sample.vpd,
                }
        except SensorPushCloudError:
            LOGGER.exception("Unexpected exception")
        return data

    async def async_get_device_ids(self) -> Iterable[str]:
        """Return the list of active device IDs."""
        return (await self.api.async_sensors()).keys()

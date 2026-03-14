"""Support for retrieving status info from Google Wifi/OnHub routers."""
from __future__ import annotations

import logging
from typing import cast

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.device_registry import DeviceInfo

from .const import (
    ATTR_CURRENT_VERSION,
    ATTR_LAST_RESTART,
    ATTR_LOCAL_IP,
    ATTR_NEW_VERSION,
    ATTR_STATUS,
    ATTR_UPTIME,
    DOMAIN,
    CONF_IP_ADDRESS,
)
# Import the type alias from __init__
from . import GoogleWifiConfigEntry, GoogleWifiSensorEntityDescription

_LOGGER = logging.getLogger(__name__)

# SENSOR_TYPES remains the same as your original file
SENSOR_TYPES: tuple[GoogleWifiSensorEntityDescription, ...] = (
    GoogleWifiSensorEntityDescription(
        key=ATTR_CURRENT_VERSION,
        name="Software Version",
        primary_key="software",
        sensor_key="softwareVersion",
        icon="mdi:checkbox-marked-circle-outline",
    ),
    GoogleWifiSensorEntityDescription(
        key=ATTR_NEW_VERSION,
        name="New Version",
        primary_key="software",
        sensor_key="updateNewVersion",
        icon="mdi:update",
    ),
    GoogleWifiSensorEntityDescription(
        key=ATTR_UPTIME,
        name="Uptime",
        primary_key="system",
        sensor_key="uptime",
        native_unit_of_measurement="d",
        icon="mdi:timelapse",
    ),
    GoogleWifiSensorEntityDescription(
        key=ATTR_LAST_RESTART,
        name="Last Restart",
        primary_key="system",
        sensor_key="uptime",
        icon="mdi:restart",
    ),
    GoogleWifiSensorEntityDescription(
        key=ATTR_LOCAL_IP,
        name="Local IP",
        primary_key="wan",
        sensor_key="localIpAddress",
        icon="mdi:access-point-network",
    ),
    GoogleWifiSensorEntityDescription(
        key=ATTR_STATUS,
        name="Status",
        primary_key="wan",
        sensor_key="online",
        icon="mdi:google",
    ),
)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: GoogleWifiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Google Wifi sensor from a config entry."""
    # Access the API directly from runtime_data
    api = entry.runtime_data.api
    
    entities = [
        GoogleWifiSensor(entry, description) 
        for description in SENSOR_TYPES
    ]
    async_add_entities(entities)

class GoogleWifiSensor(SensorEntity):
    """Representation of a Google Wifi sensor."""

    _attr_has_entity_name = True

    def __init__(
        self, 
        entry: GoogleWifiConfigEntry, 
        description: GoogleWifiSensorEntityDescription
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        self._entry = entry
        self._api = entry.runtime_data.api
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    @property
    def available(self) -> bool:
        """Return if the API is available."""
        return self._api.available

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=self._entry.title,
            manufacturer="Google",
            configuration_url=f"http://{self._entry.data[CONF_IP_ADDRESS]}/api/v1/status",
            sw_version=self._api.data.get(ATTR_CURRENT_VERSION),
        )

    async def async_update(self) -> None:
        """Fetch new state data via the API class."""
        # Use executor because the class update method is synchronous
        await self.hass.async_add_executor_job(self._api.update)

    @property
    def native_value(self):
        """Return the state of the sensor from the API's formatted data."""
        # The API class data_format() method has already processed this
        return self._api.data.get(self.entity_description.key)
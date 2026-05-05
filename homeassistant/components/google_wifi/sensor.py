"""Support for retrieving status info from Google Wifi/OnHub routers."""
from __future__ import annotations

import logging
from typing import cast

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_IP_ADDRESS
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
    SENSOR_TYPES,
    GoogleWifiSensorEntityDescription,
)
# Import the Config Entry from __init__
from . import GoogleWifiConfigEntry

_LOGGER = logging.getLogger(__name__)


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
"""Platform for sensor integration."""
from __future__ import annotations
import logging
import voluptuous as vol
from datetime import timedelta


from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.helpers.config_validation as cv


from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_NAME,
    CONF_ACCESS_TOKEN,
    CONF_NAME,
    CONF_PATH,
    CONF_URL,
)

_LOGGER = logging.getLogger(__name__)
# Time between updating data from GitHub
#SCAN_INTERVAL = timedelta(seconds=1)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_URL): cv.url,
    }
)


def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None
) -> None:
    """Set up the sensor platform."""
    async_add_entities([IntercomSensor()])


class IntercomSensor(SensorEntity):
    """Representation of a Sensor."""

    _attr_name = "Example Intercom"
    #_attr_native_unit_of_measurement = TEMP_CELSIUS
    _attr_device_class = SensorDeviceClass.INTERCOM
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_available: bool

    @property
    def should_poll(self) -> bool:
        """No polling needed for a sensor."""
        return False
    

    def update(self) -> None:
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
        self._attr_native_value = "Ringinggg"
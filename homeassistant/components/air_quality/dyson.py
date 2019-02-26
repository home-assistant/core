"""
Support for Dyson Pure Cool Air Quality Sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/dyson/
"""
import asyncio
import logging

from homeassistant.components.air_quality import (
    AirQualityEntity, ATTR_ATTRIBUTION, ATTR_NO2, ATTR_PM_10, ATTR_PM_2_5)
from homeassistant.components.dyson import DYSON_DEVICES

DEPENDENCIES = ['dyson']

ATTRIBUTION = 'Dyson purifier air quality sensor'

_LOGGER = logging.getLogger(__name__)

ATTR_VOC = 'volatile_organic_compounds'

PROP_TO_ATTR = {
    'attribution': ATTR_ATTRIBUTION,
    'nitrogen_dioxide': ATTR_NO2,
    'particulate_matter_10': ATTR_PM_10,
    'particulate_matter_2_5': ATTR_PM_2_5,
    'volatile_organic_compounds': ATTR_VOC,
}


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Dyson Sensors."""
    _LOGGER.debug("Creating new Dyson fans")
    devices = []
    unit = hass.config.units.temperature_unit
    # Get Dyson Devices from parent component
    from libpurecool.dyson_pure_cool import DysonPureCool

    for device in hass.data[DYSON_DEVICES]:
        if isinstance(device, DysonPureCool):
            devices.append(DysonAirSensor(device))
    add_entities(devices)


class DysonAirSensor(AirQualityEntity):
    """Representation of a generic Dyson air quality sensor."""

    def __init__(self, device):
        """Create a new generic air quality Dyson sensor."""
        self._device = device
        self._old_value = None
        self._name = device.name

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Call when entity is added to hass."""
        self.hass.async_add_job(
            self._device.add_message_listener, self.on_message)

    def on_message(self, message):
        """Handle new messages which are received from the fan."""
        # Prevent refreshing if not needed
        if self._old_value is None or self._old_value != self.state:
            _LOGGER.debug("Message received for %s device: %s", self.name,
                          message)
            self._old_value = self.state
            self.schedule_update_ha_state()

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the name of the Dyson sensor name."""
        return self._name

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def particulate_matter_2_5(self):
        """Return the particulate matter 2.5 level."""
        if self._device.environmental_state:
            return self._device.environmental_state.particulate_matter_25
        return None

    @property
    def particulate_matter_10(self):
        """Return the particulate matter 10 level."""
        if self._device.environmental_state:
            return self._device.environmental_state.particulate_matter_10
        return None

    @property
    def nitrogen_dioxide(self):
        """Return the NO2 (nitrogen dioxide) level."""
        if self._device.environmental_state:
            return self._device.environmental_state.nitrogen_dioxide
        return None

    @property
    def volatile_organic_compounds(self):
        """Return the VOC (Volatile Organic Compounds) level."""
        if self._device.environmental_state:
            return self._device.environmental_state.volatile_organic_compounds
        return None

    @property
    def state_attributes(self):
        """Return the state attributes."""
        data = {}

        for prop, attr in PROP_TO_ATTR.items():
            value = getattr(self, prop)
            if value is not None:
                data[attr] = value

        return data

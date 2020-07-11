"""Support for ADS binary sensors."""
import logging

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA,
    PLATFORM_SCHEMA,
    BinarySensorEntity,
)
from homeassistant.const import CONF_DEVICE_CLASS, CONF_NAME
import homeassistant.helpers.config_validation as cv

from . import CONF_ADS_VAR, DATA_ADS, STATE_KEY_STATE, AdsEntity

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "ADS binary sensor"
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ADS_VAR): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Binary Sensor platform for ADS."""
    ads_hub = hass.data.get(DATA_ADS)

    ads_var = config[CONF_ADS_VAR]
    name = config[CONF_NAME]
    device_class = config.get(CONF_DEVICE_CLASS)

    ads_sensor = AdsBinarySensor(ads_hub, name, ads_var, device_class)
    add_entities([ads_sensor])


class AdsBinarySensor(AdsEntity, BinarySensorEntity):
    """Representation of ADS binary sensors."""

    def __init__(self, ads_hub, name, ads_var, device_class):
        """Initialize ADS binary sensor."""
        super().__init__(ads_hub, name, ads_var)
        self._device_class = device_class or "moving"

    async def async_added_to_hass(self):
        """Register device notification."""
        await self.async_initialize_device(self._ads_var, self._ads_hub.PLCTYPE_BOOL)

    @property
    def is_on(self):
        """Return True if the entity is on."""
        return self._state_dict[STATE_KEY_STATE]

    @property
    def device_class(self):
        """Return the device class."""
        return self._device_class

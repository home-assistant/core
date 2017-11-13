"""
Parse prices of a item from gearbest.
For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.gearbest/
"""
import logging
import asyncio
from datetime import timedelta

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['gearbest_parser==1.0.4']
_LOGGER = logging.getLogger(__name__)

CONF_ITEMS = 'items'
CONF_CURRENCY = 'currency'

ICON = 'mdi:coin'
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=2*60*60) #2h * 60min * 60sec

_ITEM_SCHEMA = vol.Schema({
    vol.Optional("url"): cv.string,
    vol.Optional("id"): cv.string,
    vol.Optional("name"): cv.string,
    vol.Optional("currency"): cv.string
})

_ITEMS_SCHEMA = vol.Schema([_ITEM_SCHEMA])

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ITEMS): _ITEMS_SCHEMA,
    vol.Required(CONF_CURRENCY): cv.string,
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Gearbest sensor."""

    del discovery_info #unused

    hass.loop.run_in_executor(None, _add_items, hass, config, async_add_devices)

def _add_items(hass, config, async_add_devices):
    currency = config.get(CONF_CURRENCY)

    sensors = []
    items = config.get(CONF_ITEMS)
    for item in items:
        try:
            sensor = GearbestSensor(hass, item, currency)
            if sensor is not None:
                sensors.append(sensor)
        except AttributeError as exc:
            _LOGGER.error(exc)

    async_add_devices(sensors)


class GearbestSensor(Entity):
    """Implementation of the sensor."""

    def __init__(self, hass, item, currency):
        """Initialize the sensor."""

        from gearbest_parser import GearbestParser

        self._hass = hass
        self._name = item.get("name", None)
        self._parser = GearbestParser()
        self._parser.update_conversion_list()
        self._item = self._parser.load(item.get("id", None),
                                       item.get("url", None),
                                       item.get("currency", currency))
        if self._item is None:
            raise AttributeError("id and url could not be resolved")
        self._item.update()

    @property
    def name(self):
        """Return the name of the item."""
        return self._name if self._name is not None else self._item.name

    @property
    def icon(self):
        """Return the icon for the frontend."""
        return ICON

    @property
    def state(self):
        """Return the price of the selected product."""
        return self._item.price

    @property
    def unit_of_measurement(self):
        """Return the currency """
        return self._item.currency

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attrs = {'name': self._item.name,
                 'description': self._item.description,
                 'image': self._item.image,
                 'price': self._item.price,
                 'currency': self._item.currency,
                 'url': self._item.url}
        return attrs

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest price from gearbest and updates the state."""
        self._hass.loop.run_in_executor(None, self._parser.update_conversion_list)
        self._hass.loop.run_in_executor(None, self._item.update)

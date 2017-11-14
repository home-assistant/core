"""
Parse prices of a item from gearbest.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.gearbest/
"""
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import track_time_interval

REQUIREMENTS = ['gearbest_parser==1.0.5']
_LOGGER = logging.getLogger(__name__)

CONF_ITEMS = 'items'
CONF_URL = 'url'
CONF_ID = 'id'
CONF_NAME = 'name'
CONF_CURRENCY = 'currency'

ICON = 'mdi:coin'
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=2*60*60)  # 2h
MIN_TIME_BETWEEN_CURRENCY_UPDATES = timedelta(seconds=12*60*60)  # 12h

DOMAIN = 'gearbest'


_ITEM_SCHEMA = vol.All(
    vol.Schema({
        vol.Exclusive(CONF_URL, 'XOR'): cv.string,
        vol.Exclusive(CONF_ID, 'XOR'): cv.string,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_CURRENCY): cv.string
    }), cv.has_at_least_one_key(CONF_URL, CONF_ID)
)

_ITEMS_SCHEMA = vol.Schema([_ITEM_SCHEMA])

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ITEMS): _ITEMS_SCHEMA,
    vol.Required(CONF_CURRENCY): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Gearbest sensor."""
    from gearbest_parser import CurrencyConverter
    currency = config.get(CONF_CURRENCY)

    sensors = []
    items = config.get(CONF_ITEMS)

    hass.data[DOMAIN] = CurrencyConverter()
    hass.data[DOMAIN].update()

    for item in items:
        try:
            sensor = GearbestSensor(hass, item, currency)
            if sensor is not None:
                sensors.append(sensor)
        except ValueError as exc:
            _LOGGER.error(exc)

    def currency_update(event_time):
        """Update currency list."""
        hass.data[DOMAIN].update()

    track_time_interval(hass,
                        currency_update,
                        MIN_TIME_BETWEEN_CURRENCY_UPDATES)

    add_devices(sensors)


class GearbestSensor(Entity):
    """Implementation of the sensor."""

    def __init__(self, hass, item, currency):
        """Initialize the sensor."""
        from gearbest_parser import GearbestParser

        self._hass = hass
        self._name = item.get(CONF_NAME, None)
        self._parser = GearbestParser()
        self._parser.set_currency_converter(hass.data[DOMAIN])
        self._item = self._parser.load(item.get(CONF_ID, None),
                                       item.get(CONF_URL, None),
                                       item.get(CONF_CURRENCY, currency))
        if self._item is None:
            raise ValueError("id and url could not be resolved")
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
        """Return the currency."""
        return self._item.currency

    @property
    def entity_picture(self):
        """Return the image."""
        return self._item.image

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attrs = {'name': self._item.name,
                 'description': self._item.description,
                 'price': self._item.price,
                 'currency': self._item.currency,
                 'url': self._item.url}
        return attrs

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest price from gearbest and updates the state."""
        self._item.update()

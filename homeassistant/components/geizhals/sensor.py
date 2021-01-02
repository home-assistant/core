"""Parse prices of a device from geizhals."""
from datetime import timedelta

from geizhals import Device, Geizhals
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

CONF_DESCRIPTION = "description"
CONF_PRODUCT_ID = "product_id"
CONF_LOCALE = "locale"

ICON = "mdi:currency-usd-circle"

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=120)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_PRODUCT_ID): cv.positive_int,
        vol.Optional(CONF_DESCRIPTION, default="Price"): cv.string,
        vol.Optional(CONF_LOCALE, default="DE"): vol.In(["AT", "EU", "DE", "UK", "PL"]),
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Geizwatch sensor."""
    name = config.get(CONF_NAME)
    description = config.get(CONF_DESCRIPTION)
    product_id = config.get(CONF_PRODUCT_ID)
    domain = config.get(CONF_LOCALE)

    add_entities([Geizwatch(name, description, product_id, domain)], True)


class Geizwatch(Entity):
    """Implementation of Geizwatch."""

    def __init__(self, name, description, product_id, domain):
        """Initialize the sensor."""

        # internal
        self._name = name
        self._geizhals = Geizhals(product_id, domain)
        self._device = Device()

        # external
        self.description = description
        self.product_id = product_id

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Return the icon for the frontend."""
        return ICON

    @property
    def state(self):
        """Return the best price of the selected product."""
        if not self._device.prices:
            return None

        return self._device.prices[0]

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        while len(self._device.prices) < 4:
            self._device.prices.append("None")
        attrs = {
            "device_name": self._device.name,
            "description": self.description,
            "unit_of_measurement": self._device.price_currency,
            "product_id": self.product_id,
            "price1": self._device.prices[0],
            "price2": self._device.prices[1],
            "price3": self._device.prices[2],
            "price4": self._device.prices[3],
        }
        return attrs

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest price from geizhals and updates the state."""
        self._device = self._geizhals.parse()

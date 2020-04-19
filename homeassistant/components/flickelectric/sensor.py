"""Support for Flick Electric Pricing data."""
from datetime import timedelta
import logging

import async_timeout
from pyflick import FlickAPI, FlickPrice
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_FRIENDLY_NAME,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util.dt import utcnow

from .const import ATTR_END_AT, ATTR_START_AT, DOMAIN

_LOGGER = logging.getLogger(__name__)
_AUTH_URL = "https://api.flick.energy/identity/oauth/token"
_RESOURCE = "https://api.flick.energy/customer/mobile_provider/price"

SCAN_INTERVAL = timedelta(minutes=5)

ATTRIBUTION = "Data provided by Flick Electric"
FRIENDLY_NAME = "Flick Power Price"
UNIT_NAME = "cents"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_CLIENT_ID): cv.string,
        vol.Optional(CONF_CLIENT_SECRET): cv.string,
    }
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Flick Sensor Setup."""
    api: FlickAPI = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([FlickPricingSensor(api)], True)


class FlickPricingSensor(Entity):
    """Entity object for Flick Electric sensor."""

    def __init__(self, api: FlickAPI):
        """Entity object for Flick Electric sensor."""
        self._api: FlickAPI = api
        self._price: FlickPrice = None
        self._attributes = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return FRIENDLY_NAME

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._price.price

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return UNIT_NAME

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    async def async_update(self):
        """Get the Flick Pricing data from the web service."""
        if self._price and self._price.end_at >= utcnow():
            return  # Power price data is still valid

        with async_timeout.timeout(60):
            self._price = await self._api.getPricing()

        # Update Attributes
        self._attributes = {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_FRIENDLY_NAME: FRIENDLY_NAME,
        }

        self._attributes[ATTR_START_AT] = self._price.start_at
        self._attributes[ATTR_END_AT] = self._price.end_at
        for component in self._price.components:
            self._attributes[component.charge_setter] = float(component.value)

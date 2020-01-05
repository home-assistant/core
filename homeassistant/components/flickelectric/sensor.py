"""Support for Flick Electric Pricing data."""
import asyncio
from datetime import datetime as dt, timedelta
import logging

import aiohttp
import async_timeout
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_FRIENDLY_NAME,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)
_AUTH_URL = "https://api.flick.energy/identity/oauth/token"
_RESOURCE = "https://api.flick.energy/customer/mobile_provider/price"

SCAN_INTERVAL = timedelta(minutes=1)

_TOKEN_REFRESH_INTERVAL = timedelta(days=1)

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


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Flick sensor."""
    websession = async_get_clientsession(hass)

    async_add_entities(
        [
            FlickPricingSensor(
                hass.loop,
                websession,
                config[CONF_USERNAME],
                config[CONF_PASSWORD],
                config.get(CONF_CLIENT_ID),
                config.get(CONF_CLIENT_SECRET),
            )
        ],
        True,
    )


class FlickPricingSensor(Entity):
    """Implementation of the Flick Pricing sensor."""

    def __init__(
        self,
        loop,
        websession: aiohttp.ClientSession,
        username: str,
        password: str,
        client_id: str,
        client_secret: str,
    ):
        """Initialize the sensor."""

        self.loop = loop
        self._username: str = username
        self._password: str = password
        self.websession: aiohttp.ClientSession = websession

        if client_id:
            self._client_id: str = client_id
        else:
            self._client_id: str = "le37iwi3qctbduh39fvnpevt1m2uuvz"

        if client_secret:
            self._client_secret: str = client_secret
        else:
            self._client_secret: str = "ignwy9ztnst3azswww66y9vd9zt6qnt"

        self._name: str = FRIENDLY_NAME
        self._state = None
        self._unit_of_measurement: str = UNIT_NAME
        self._attributes = {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_FRIENDLY_NAME: FRIENDLY_NAME,
        }

        self._token = None
        self._token_next_refresh = dt.now()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    async def _refresh_token(self):
        try:
            with async_timeout.timeout(60):

                data = aiohttp.FormData()
                data.add_field("grant_type", "password")
                data.add_field("client_id", self._client_id)
                data.add_field("client_secret", self._client_secret)
                data.add_field("username", self._username)
                data.add_field("password", self._password)

                response = await self.websession.post(_AUTH_URL, data=data)
                response = await response.json()

                self._token = response["id_token"]
                self._token_next_refresh = dt.now() + _TOKEN_REFRESH_INTERVAL
        except (asyncio.TimeoutError, aiohttp.ClientError, ValueError, KeyError) as err:
            _LOGGER.error("Could not get auth token from FlickElectric API: %s", err)

    async def async_update(self):
        """Get the Flick Pricing data from the web service."""

        next_refresh = self._token_next_refresh
        if next_refresh < dt.now():
            await self._refresh_token()

        try:
            with async_timeout.timeout(60):
                headers = {"Authorization": f"Bearer {self._token}"}
                response = await self.websession.get(_RESOURCE, headers=headers)

                data = await response.json()
                needle = data["needle"]
                self._state = float(needle["price"])

                attributes = {
                    ATTR_ATTRIBUTION: ATTRIBUTION,
                    ATTR_FRIENDLY_NAME: FRIENDLY_NAME,
                }

                attributes["start_at"] = needle["start_at"]
                attributes["end_at"] = needle["end_at"]
                for component in needle["components"]:
                    attributes[component["charge_setter"]] = float(component["value"])

                self._attributes = attributes

        except (asyncio.TimeoutError, aiohttp.ClientError) as err:
            _LOGGER.error("Could not get data from Flick API: %s", err)
        except (ValueError, KeyError):
            _LOGGER.warning("Could not update status for %s", self.name)

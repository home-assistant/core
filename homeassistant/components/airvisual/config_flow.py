"""Define a config flow manager for AirVisual."""
from collections import OrderedDict

from pyairvisual import Client
from pyairvisual.errors import InvalidKeyError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_SCAN_INTERVAL,
    CONF_SHOW_ON_MAP,
)
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client, config_validation as cv

from .const import CONF_GEOGRAPHIES, DEFAULT_SCAN_INTERVAL, DOMAIN


@callback
def configured_instances(hass):
    """Return a set of configured AirVisual instances."""
    return set(
        entry.data[CONF_API_KEY] for entry in hass.config_entries.async_entries(DOMAIN)
    )


@config_entries.HANDLERS.register(DOMAIN)
class AirVisualFlowHandler(config_entries.ConfigFlow):
    """Handle a AirVisual config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize the config flow."""
        self.data_schema = OrderedDict()
        self.data_schema[vol.Required(CONF_API_KEY)] = str
        self.data_schema[vol.Optional(CONF_LATITUDE)] = cv.latitude
        self.data_schema[vol.Optional(CONF_LONGITUDE)] = cv.longitude
        self.data_schema[vol.Optional(CONF_SHOW_ON_MAP, default=True)] = bool

    @callback
    async def _show_form(self, errors=None):
        """Show the form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(self.data_schema),
            errors=errors or {},
        )

    async def async_step_import(self, import_config):
        """Import a config entry from configuration.yaml."""
        return await self.async_step_user(import_config)

    async def async_step_user(self, user_input=None):
        """Handle the start of the config flow."""
        if not user_input:
            return await self._show_form()

        if user_input[CONF_API_KEY] in configured_instances(self.hass):
            return await self._show_form({CONF_API_KEY: "identifier_exists"})

        websession = aiohttp_client.async_get_clientsession(self.hass)

        client = Client(websession, api_key=user_input[CONF_API_KEY])

        try:
            await client.api.nearest_city()
        except InvalidKeyError:
            return await self._show_form({CONF_API_KEY: "invalid_api_key"})

        data = {
            CONF_API_KEY: user_input[CONF_API_KEY],
            CONF_GEOGRAPHIES: user_input.get(CONF_GEOGRAPHIES, []),
            CONF_SCAN_INTERVAL: user_input.get(
                CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL.total_seconds()
            ),
            CONF_SHOW_ON_MAP: user_input.get(CONF_SHOW_ON_MAP, True),
        }
        if user_input.get(CONF_LATITUDE):
            data[CONF_GEOGRAPHIES].append(
                {
                    CONF_LATITUDE: user_input[CONF_LATITUDE],
                    CONF_LONGITUDE: user_input[CONF_LONGITUDE],
                }
            )

        return self.async_create_entry(
            title=f"Cloud API (API key: {user_input[CONF_API_KEY][:4]}...)", data=data,
        )

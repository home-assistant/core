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
    CONF_SHOW_ON_MAP,
)
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client, config_validation as cv

from .const import CONF_GEOGRAPHIES, DOMAIN


@callback
def configured_instances(hass):
    """Return a set of configured AirVisual instances."""
    return set(
        entry.data[CONF_API_KEY] for entry in hass.config_entries.async_entries(DOMAIN)
    )


class AirVisualFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a AirVisual config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    @property
    def cloud_api_schema(self):
        """Return the data schema for the cloud API."""
        schema = OrderedDict()
        schema[vol.Required(CONF_API_KEY)] = str
        schema[
            vol.Required(CONF_LATITUDE, default=self.hass.config.latitude)
        ] = cv.latitude
        schema[
            vol.Required(CONF_LONGITUDE, default=self.hass.config.longitude)
        ] = cv.longitude
        schema[vol.Optional(CONF_SHOW_ON_MAP, default=True)] = bool

        return schema

    @callback
    async def _show_form(self, errors=None):
        """Show the form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(self.cloud_api_schema),
            errors=errors or {},
        )

    async def async_step_import(self, import_config):
        """Import a config entry from configuration.yaml."""
        data = {**import_config}
        if not data.get(CONF_GEOGRAPHIES):
            data[CONF_GEOGRAPHIES] = [
                {
                    CONF_LATITUDE: self.hass.config.latitude,
                    CONF_LONGITUDE: self.hass.config.longitude,
                }
            ]

        return self.async_create_entry(
            title=f"Cloud API (API key: {import_config[CONF_API_KEY][:4]}...)",
            data=data,
        )

    async def async_step_user(self, user_input=None):
        """Handle the start of the config flow."""
        if not user_input:
            return await self._show_form()

        if user_input[CONF_API_KEY] in configured_instances(self.hass):
            return await self._show_form(errors={CONF_API_KEY: "identifier_exists"})

        websession = aiohttp_client.async_get_clientsession(self.hass)

        client = Client(websession, api_key=user_input[CONF_API_KEY])

        try:
            await client.api.nearest_city()
        except InvalidKeyError:
            return await self._show_form(errors={CONF_API_KEY: "invalid_api_key"})

        return self.async_create_entry(
            title=f"Cloud API (API key: {user_input[CONF_API_KEY][:4]}...)",
            data={
                CONF_API_KEY: user_input[CONF_API_KEY],
                CONF_GEOGRAPHIES: [
                    {
                        CONF_LATITUDE: user_input[CONF_LATITUDE],
                        CONF_LONGITUDE: user_input[CONF_LONGITUDE],
                    }
                ],
                CONF_SHOW_ON_MAP: user_input[CONF_SHOW_ON_MAP],
            },
        )

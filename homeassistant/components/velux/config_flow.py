"""Velux component config flow."""
# https://developers.home-assistant.io/docs/config_entries_config_flow_handler#defining-your-config-flow
import logging

from pyvlx import PyVLX, PyVLXException
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

RESULT_AUTH_FAILED = "connection_failed"
RESULT_SUCCESS = "success"


class VeluxConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Velux config flow."""

    def __init__(self):
        """Initialize."""
        self._velux = None
        self._host = None
        self._password = None
        self._hostname = None
        self.bridge = None

    def _get_entry(self):
        return self.async_create_entry(
            title=self._host,
            data={CONF_HOST: self._host, CONF_PASSWORD: self._password},
        )

    async def async_step_import(self, user_input=None):
        """Handle configuration by yaml file."""
        return await self.async_step_user(user_input)

    async def async_step_user(self, user_input=None):
        """Handle configuration via user input."""
        errors = {}
        if user_input is not None:
            self._host = user_input[CONF_HOST]
            self._password = user_input[CONF_PASSWORD]
            await self.async_set_unique_id(self._host)
            self._abort_if_unique_id_configured()
            self.bridge = PyVLX(host=self._host, password=self._password)
            try:
                await self.bridge.connect()
                await self.bridge.disconnect()
                return self._get_entry()
            except PyVLXException:
                errors["base"] = "invalid_auth"
            except OSError:
                errors["base"] = "invalid_host"
            else:
                errors["base"] = "cannot_connect"

        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=self._host): str,
                vol.Required(CONF_PASSWORD, default=self._password): str,
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def async_step_unignore(self, user_input):
        """Rediscover a previously ignored discover."""
        unique_id = user_input["unique_id"]
        await self.async_set_unique_id(unique_id)
        return await self.async_step_user()

    async def async_step_zeroconf(self, info):
        """Handle discovery by zeroconf."""
        if (
            info is None
            or not info.get("hostname")
            or not info["hostname"].startswith("VELUX_KLF_LAN")
        ):
            return self.async_abort(reason="no_devices_found")

        self._host = info.get("host")

        await self.async_set_unique_id(self._host)
        self._abort_if_unique_id_configured()

        return await self.async_step_user()

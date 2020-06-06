"""Config flow for Spider."""
import logging

from spiderpy.spiderapi import SpiderApi, SpiderApiException, UnauthorizedException
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class SpiderConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Spider config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize the Spider flow."""
        self.data = {
            CONF_USERNAME: "",
            CONF_PASSWORD: "",
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
            "login_response": None,
        }

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        errors = {}
        if user_input is not None:
            self.data[CONF_USERNAME] = user_input["username"]
            self.data[CONF_PASSWORD] = user_input["password"]

            try:
                SpiderApi(
                    self.data[CONF_USERNAME],
                    self.data[CONF_PASSWORD],
                    self.data[CONF_SCAN_INTERVAL],
                )
                return self.async_create_entry(title=DOMAIN, data=self.data,)
            except UnauthorizedException:
                errors["base"] = "invalid_auth"
            except SpiderApiException:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        data_schema = {
            vol.Required("username"): str,
            vol.Required("password"): str,
        }

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(data_schema), errors=errors,
        )

    async def async_step_import(self, import_data):
        """Import spider config from configuration.yaml."""
        return await self.async_step_user(import_data)

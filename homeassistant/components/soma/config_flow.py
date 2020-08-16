"""Config flow for Soma."""
import logging

from api.soma_api import SomaApi
from requests import RequestException
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 3000


class SomaFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Instantiate config flow."""

    async def async_step_user(self, user_input=None):
        """Handle a flow start."""
        if user_input is None:
            data = {
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
            }

            return self.async_show_form(step_id="user", data_schema=vol.Schema(data))

        return await self.async_step_creation(user_input)

    async def async_step_creation(self, user_input=None):
        """Finish config flow."""
        api = SomaApi(user_input["host"], user_input["port"])
        try:
            result = await self.hass.async_add_executor_job(api.list_devices)
            _LOGGER.info("Successfully set up Soma Connect")
            if result["result"] == "success":
                return self.async_create_entry(
                    title="Soma Connect",
                    data={"host": user_input["host"], "port": user_input["port"]},
                )
            _LOGGER.error(
                "Connection to SOMA Connect failed (result:%s)", result["result"]
            )
            return self.async_abort(reason="result_error")
        except RequestException:
            _LOGGER.error("Connection to SOMA Connect failed with RequestException")
            return self.async_abort(reason="connection_error")
        except KeyError:
            _LOGGER.error("Connection to SOMA Connect failed with KeyError")
            return self.async_abort(reason="connection_error")

    async def async_step_import(self, user_input=None):
        """Handle flow start from existing config section."""
        if self.hass.config_entries.async_entries(DOMAIN):
            return self.async_abort(reason="already_setup")
        return await self.async_step_creation(user_input)

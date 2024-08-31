"""Config flow for Soma."""

import logging
from typing import Any

from api.soma_api import SomaApi
from requests import RequestException
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 3000


class SomaFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Instantiate config flow."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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
        try:
            api = await self.hass.async_add_executor_job(
                SomaApi, user_input["host"], user_input["port"]
            )
        except RequestException:
            _LOGGER.error("Connection to SOMA Connect failed with RequestException")
            return self.async_abort(reason="connection_error")
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

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle flow start from existing config section."""
        if self._async_current_entries():
            return self.async_abort(reason="already_setup")
        return await self.async_step_creation(import_data)

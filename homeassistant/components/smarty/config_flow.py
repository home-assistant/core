"""Config flow for Smarty integration."""

import logging
from typing import Any

from pysmarty2 import Smarty
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class SmartyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Smarty config flow."""

    def _test_connection(self, host: str) -> str | None:
        """Test the connection to the Smarty API."""
        smarty = Smarty(host=host)
        try:
            if smarty.update():
                return None
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return "unknown"
        else:
            return "cannot_connect"

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._async_abort_entries_match(user_input)
            error = await self.hass.async_add_executor_job(
                self._test_connection, user_input[CONF_HOST]
            )
            if not error:
                return self.async_create_entry(
                    title=user_input[CONF_HOST], data=user_input
                )
            errors["base"] = error
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors,
        )

    async def async_step_import(
        self, import_config: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle a flow initialized by import."""
        error = await self.hass.async_add_executor_job(
            self._test_connection, import_config[CONF_HOST]
        )
        if not error:
            return self.async_create_entry(
                title=import_config[CONF_NAME],
                data={CONF_HOST: import_config[CONF_HOST]},
            )
        return self.async_abort(reason=error)

"""Config flow for the Niko home control integration."""

from __future__ import annotations

import logging
from typing import Any

from nhc.controller import NHCController
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
    }
)


async def test_connection(host: str) -> str | None:
    """Test if we can connect to the Niko Home Control controller."""

    controller = NHCController(host, 8000)
    try:
        await controller.connect()
    except Exception:
        _LOGGER.exception("Unexpected exception")
        return "cannot_connect"
    return None


class NikoHomeControlConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Niko Home Control."""

    MINOR_VERSION = 2

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the integration."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
            error = await test_connection(user_input[CONF_HOST])
            if not error:
                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(),
                    data_updates=user_input,
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="reconfigure", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
            error = await test_connection(user_input[CONF_HOST])
            if not error:
                return self.async_create_entry(
                    title="Niko Home Control",
                    data=user_input,
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

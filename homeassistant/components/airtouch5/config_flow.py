"""Config flow for Airtouch 5 integration."""

from __future__ import annotations

import logging
from typing import Any

from airtouch5py.airtouch5_simple_client import Airtouch5SimpleClient
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})


class AirTouch5ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Airtouch 5."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] | None = None
        if user_input is not None:
            client = Airtouch5SimpleClient(user_input[CONF_HOST])
            try:
                await client.test_connection()
            except Exception:  # noqa: BLE001
                errors = {"base": "cannot_connect"}
            else:
                await self.async_set_unique_id(user_input[CONF_HOST])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_HOST], data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

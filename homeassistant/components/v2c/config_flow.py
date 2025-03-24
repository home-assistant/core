"""Config flow for V2C integration."""

from __future__ import annotations

import logging
from typing import Any

from pytrydan import Trydan
from pytrydan.exceptions import TrydanError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers.httpx_client import get_async_client

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
    }
)


class V2CConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for V2C."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            evse = Trydan(
                user_input[CONF_HOST],
                client=get_async_client(self.hass, verify_ssl=False),
            )

            try:
                data = await evse.get_data()

            except TrydanError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if data.ID:
                    await self.async_set_unique_id(data.ID)
                    self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"EVSE {user_input[CONF_HOST]}", data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

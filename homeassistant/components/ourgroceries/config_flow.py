"""Config flow for OurGroceries integration."""

from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientError
from ourgroceries import OurGroceries
from ourgroceries.exceptions import InvalidLoginException
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class OurGroceriesConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OurGroceries."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            og = OurGroceries(user_input[CONF_USERNAME], user_input[CONF_PASSWORD])
            try:
                await og.login()
            except (TimeoutError, ClientError):
                errors["base"] = "cannot_connect"
            except InvalidLoginException:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME], data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

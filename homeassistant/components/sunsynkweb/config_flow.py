"""Config flow for Sunsynk Inverter Web integration."""

from __future__ import annotations

import logging
import traceback
from typing import Any

import aiohttp
from pysunsynkweb.const import BASE_API
from pysunsynkweb.exceptions import AuthenticationFailed
from pysunsynkweb.session import SunsynkwebSession
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow as BaseConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class SunsynkConfigFlow(BaseConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sunsynk Inverter Web."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            swebsession = SunsynkwebSession(
                async_get_clientsession(self.hass), user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
            )
            try:
                await swebsession.get(BASE_API)
            except AuthenticationFailed:
                errors["base"] = "invalid_auth"
            except aiohttp.ClientConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception %s", traceback.format_exc())
                errors["base"] = "unknown"

            else:
                return self.async_create_entry(
                    title="Sunsynk web data", data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

"""Config flow for Sharp COCORO Air integration."""

from __future__ import annotations

import logging
from typing import Any

from aiosharp_cocoro_air import SharpAuthError, SharpCOCOROAir, SharpConnectionError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class SharpCocoroAirConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sharp COCORO Air."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle the initial step -- email/password entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                async with SharpCOCOROAir(
                    user_input[CONF_EMAIL],
                    user_input[CONF_PASSWORD],
                    session=async_get_clientsession(self.hass),
                ) as client:
                    await client.authenticate()
            except SharpAuthError:
                errors["base"] = "invalid_auth"
            except SharpConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during Sharp login")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(user_input[CONF_EMAIL].lower())
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Sharp COCORO Air ({user_input[CONF_EMAIL]})",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )

"""Config flow for the Happiest Baby Snoo integration."""

from __future__ import annotations

import logging
from typing import Any

import jwt
from python_snoo.exceptions import InvalidSnooAuth, SnooAuthException
from python_snoo.snoo import Snoo
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
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


class SnooConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Happiest Baby Snoo."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            hub = Snoo(
                email=user_input[CONF_USERNAME],
                password=user_input[CONF_PASSWORD],
                clientsession=async_get_clientsession(self.hass),
            )

            try:
                tokens = await hub.authorize()
            except SnooAuthException:
                errors["base"] = "cannot_connect"
            except InvalidSnooAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception %s")
                errors["base"] = "unknown"
            else:
                user_uuid = jwt.decode(
                    tokens.aws_access, options={"verify_signature": False}
                )["username"]
                await self.async_set_unique_id(user_uuid)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=user_input[CONF_USERNAME], data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

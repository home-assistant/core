"""Config flow for the Ouman EH-800 integration."""

from __future__ import annotations

import logging
from typing import Any, override

from ouman_eh_800_api import (
    OumanClientAuthenticationError,
    OumanClientCommunicationError,
    OumanEh800Client,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


def _normalize_url(url: str) -> str:
    """Normalize URL by stripping whitespace, trailing slashes, and /eh800.html."""
    return url.strip().removesuffix("/").removesuffix("/eh800.html").removesuffix("/")


class OumanEh800ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ouman EH-800."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input[CONF_URL] = _normalize_url(user_input[CONF_URL])
            self._async_abort_entries_match({CONF_URL: user_input[CONF_URL]})
            client = OumanEh800Client(
                session=async_get_clientsession(self.hass),
                username=user_input[CONF_USERNAME],
                password=user_input[CONF_PASSWORD],
                address=user_input[CONF_URL],
            )
            try:
                await client.login()
            except OumanClientCommunicationError:
                errors["base"] = "cannot_connect"
            except OumanClientAuthenticationError:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title="Ouman EH-800", data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

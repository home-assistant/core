"""Config flow for the liebherr integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from pyliebherrhomeapi import LiebherrClient
from pyliebherrhomeapi.exceptions import (
    LiebherrAuthenticationError,
    LiebherrConnectionError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
    }
)


class LiebherrConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for liebherr."""

    async def _validate_api_key(self, api_key: str) -> tuple[list, dict[str, str]]:
        """Validate the API key and return devices and errors."""
        errors: dict[str, str] = {}
        devices: list = []
        client = LiebherrClient(
            api_key=api_key,
            session=async_get_clientsession(self.hass),
        )
        try:
            devices = await client.get_devices()
        except LiebherrAuthenticationError:
            errors["base"] = "invalid_auth"
        except LiebherrConnectionError:
            errors["base"] = "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        return devices, errors

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input[CONF_API_KEY] = user_input[CONF_API_KEY].strip()

            self._async_abort_entries_match({CONF_API_KEY: user_input[CONF_API_KEY]})

            devices, errors = await self._validate_api_key(user_input[CONF_API_KEY])
            if not errors:
                if not devices:
                    return self.async_abort(reason="no_devices")

                return self.async_create_entry(
                    title="Liebherr",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm re-authentication."""
        errors: dict[str, str] = {}

        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()

            _, errors = await self._validate_api_key(api_key)
            if not errors:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data_updates={CONF_API_KEY: api_key},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

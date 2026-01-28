"""Config flow for the liebherr integration."""

from __future__ import annotations

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
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
    }
)


class LiebherrConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for liebherr."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input[CONF_API_KEY] = user_input[CONF_API_KEY].strip()

            self._async_abort_entries_match({CONF_API_KEY: user_input[CONF_API_KEY]})

            try:
                # Create a client and test the connection
                client = LiebherrClient(
                    api_key=user_input[CONF_API_KEY],
                    session=async_get_clientsession(self.hass),
                )
                devices = await client.get_devices()
            except LiebherrAuthenticationError:
                errors["base"] = "invalid_auth"
            except LiebherrConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if not devices:
                    return self.async_abort(reason="no_devices")

                return self.async_create_entry(
                    title="Liebherr",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        # Abort if any Liebherr entry already exists (cloud API covers all devices)
        self._async_abort_entries_match()

        # Set unique ID to prevent duplicate discovery notifications for the same device
        await self.async_set_unique_id(discovery_info.name)
        self._abort_if_unique_id_configured()

        return await self.async_step_user()

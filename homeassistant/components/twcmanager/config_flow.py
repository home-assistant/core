"""Config flow for TWCManager integration."""
from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientConnectorError
from twcmanager_client.client import TWCManagerClient
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("host"): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for TWCManager."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            api = TWCManagerClient(user_input["host"])
            uuid = await api.async_get_uuid()
        except ClientConnectorError:
            errors["base"] = "cannot_connect"
        except Exception as exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception: " + type(exception).__name__)
            errors["base"] = "unknown"
        else:
            await self.async_set_unique_id(uuid)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=user_input["host"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

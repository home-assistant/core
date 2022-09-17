"""Config flow for Volvo On Call integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from volvooncall import Connection

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_REGION, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from . import VolvoData
from .const import CONF_MUTABLE, CONF_SCANDINAVIAN_MILES, DOMAIN
from .errors import InvalidAuth

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_REGION, default=None): vol.In(
            {"na": "North America", "cn": "China", None: "Rest of world"}
        ),
        vol.Optional(CONF_MUTABLE, default=True): cv.boolean,
        vol.Optional(CONF_SCANDINAVIAN_MILES, default=False): cv.boolean,
    },
)


class VolvoOnCallConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """VolvoOnCall config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle user step."""
        errors = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_USERNAME])
            self._abort_if_unique_id_configured()

            try:
                await self.is_valid(user_input)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unhandled exception in user step")
                errors["base"] = "unknown"
            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME], data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=USER_SCHEMA, errors=errors
        )

    async def async_step_import(self, import_data) -> FlowResult:
        """Import volvooncall config from configuration.yaml."""
        return await self.async_step_user(import_data)

    async def is_valid(self, user_input):
        """Check for user input errors."""

        session = async_get_clientsession(self.hass)

        region: str | None = user_input.get(CONF_REGION)

        connection = Connection(
            session=session,
            username=user_input[CONF_USERNAME],
            password=user_input[CONF_PASSWORD],
            service_url=None,
            region=region,
        )

        test_volvo_data = VolvoData(self.hass, connection, user_input)

        await test_volvo_data.auth_is_valid()

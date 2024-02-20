"""Adds config flow for 17track.net."""
from __future__ import annotations

import logging
from typing import Any

from py17track import Client as SeventeenTrackClient
from py17track.errors import SeventeenTrackError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class SeventeenTrackConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """17track config flow."""

    VERSION = 1

    async def _async_validate_input(self, user_input):
        """Validate the user input allows us to connect."""

        session = aiohttp_client.async_get_clientsession(self.hass)

        client = SeventeenTrackClient(session=session)

        try:
            login_result = await client.profile.login(
                user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
            )

            if not login_result:
                _LOGGER.error("Invalid username and password provided")
                return {"base": "invalid_credentials"}
        except SeventeenTrackError as err:
            _LOGGER.error("There was an error while logging in: %s", err)
            return {"base": "cannot_connect"}

        return {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""

        errors = {}
        if user_input is not None:
            errors = await self._async_validate_input(user_input)

            if not errors:
                return self.async_create_entry(title="17Track", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=USER_SCHEMA,
            errors=errors,
        )

    async def async_step_import(self, import_data):
        """Import 17Track config from configuration.yaml."""
        return await self.async_step_user(import_data)

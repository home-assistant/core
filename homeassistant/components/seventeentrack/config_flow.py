"""Adds config flow for 17track.net."""

from __future__ import annotations

import logging
from typing import Any

from pyseventeentrack import Client as SeventeenTrackClient
from pyseventeentrack.errors import SeventeenTrackError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaFlowFormStep,
    SchemaOptionsFlowHandler,
)

from .const import (
    CONF_SHOW_ARCHIVED,
    CONF_SHOW_DELIVERED,
    DEFAULT_SHOW_ARCHIVED,
    DEFAULT_SHOW_DELIVERED,
    DOMAIN,
)

CONF_SHOW = {
    vol.Optional(CONF_SHOW_ARCHIVED, default=DEFAULT_SHOW_ARCHIVED): bool,
    vol.Optional(CONF_SHOW_DELIVERED, default=DEFAULT_SHOW_DELIVERED): bool,
}

_LOGGER = logging.getLogger(__name__)

OPTIONS_SCHEMA = vol.Schema(CONF_SHOW)
OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(OPTIONS_SCHEMA),
}

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class SeventeenTrackConfigFlow(ConfigFlow, domain=DOMAIN):
    """17track config flow."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> SchemaOptionsFlowHandler:
        """Get options flow for this handler."""
        return SchemaOptionsFlowHandler(config_entry, OPTIONS_FLOW)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""

        errors = {}
        if user_input:
            client = self._get_client()

            try:
                if not await client.profile.login(
                    user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
                ):
                    errors["base"] = "invalid_auth"
            except SeventeenTrackError as err:
                _LOGGER.error("There was an error while logging in: %s", err)
                errors["base"] = "cannot_connect"

            if not errors:
                account_id = client.profile.account_id
                await self.async_set_unique_id(account_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=user_input[CONF_USERNAME],
                    data=user_input,
                    options={
                        CONF_SHOW_ARCHIVED: DEFAULT_SHOW_ARCHIVED,
                        CONF_SHOW_DELIVERED: DEFAULT_SHOW_DELIVERED,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=USER_SCHEMA,
            errors=errors,
        )

    @callback
    def _get_client(self):
        session = aiohttp_client.async_get_clientsession(self.hass)
        return SeventeenTrackClient(session=session)

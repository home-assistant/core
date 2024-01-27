"""Config flow for WittIOT integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from wittiot import API
from wittiot.errors import WittiotError

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for WittIOT."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the local step."""
        errors = {}

        if user_input is not None:
            api = API(
                user_input[CONF_HOST],
                session=aiohttp_client.async_get_clientsession(self.hass),
            )

            try:
                devices = await api.request_loc_info()
            except WittiotError:
                errors["base"] = "cannot_connect"
            _LOGGER.debug("New data received: %s", devices)

            if not devices:
                errors["base"] = "no_devices"

            if not errors:
                unique_id = devices["dev_name"]
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(title=unique_id, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors,
        )

"""Config flow for the Jellyfin integration."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.util.uuid import random_uuid_hex

from .client_wrapper import CannotConnect, InvalidAuth, create_client, validate_input
from .const import CONF_CLIENT_DEVICE_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): str,
        vol.Required(CONF_USERNAME): str,
        vol.Optional(CONF_PASSWORD, default=""): str,
    }
)

REAUTH_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_PASSWORD, default=""): str,
    }
)


def _generate_client_device_id() -> str:
    """Generate a random UUID4 string to identify ourselves."""
    return random_uuid_hex()


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Jellyfin."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the Jellyfin config flow."""
        self.client_device_id: str | None = None
        self.entry: config_entries.ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a user defined configuration."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors: dict[str, str] = {}

        if user_input is not None:
            if self.client_device_id is None:
                self.client_device_id = _generate_client_device_id()

            client = create_client(device_id=self.client_device_id)
            try:
                user_id, connect_result = await validate_input(
                    self.hass, user_input, client
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception as ex:  # pylint: disable=broad-except
                errors["base"] = "unknown"
                _LOGGER.exception(ex)
            else:
                entry_title = user_input[CONF_URL]

                server_info: dict[str, Any] = connect_result["Servers"][0]

                if server_name := server_info.get("Name"):
                    entry_title = server_name

                await self.async_set_unique_id(user_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=entry_title,
                    data={CONF_CLIENT_DEVICE_ID: self.client_device_id, **user_input},
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Perform reauth upon an API authentication error."""
        self.entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Dialog that informs the user that reauth is required."""
        errors: dict[str, str] = {}

        if user_input is not None:
            assert self.entry is not None
            new_input = self.entry.data | user_input

            if self.client_device_id is None:
                self.client_device_id = _generate_client_device_id()

            client = create_client(device_id=self.client_device_id)
            try:
                await validate_input(self.hass, new_input, client)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception as ex:  # pylint: disable=broad-except
                errors["base"] = "unknown"
                _LOGGER.exception(ex)
            else:
                self.hass.config_entries.async_update_entry(self.entry, data=new_input)

                await self.hass.config_entries.async_reload(self.entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm", data_schema=REAUTH_DATA_SCHEMA, errors=errors
        )

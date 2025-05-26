"""Config flow for the Jellyfin integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.util.uuid import random_uuid_hex

from .client_wrapper import CannotConnect, InvalidAuth, create_client, validate_input
from .const import CONF_CLIENT_DEVICE_ID, DOMAIN, SUPPORTED_AUDIO_CODECS
from .coordinator import JellyfinConfigEntry

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


OPTIONAL_DATA_SCHEMA = vol.Schema(
    {vol.Optional("audio_codec"): vol.In(SUPPORTED_AUDIO_CODECS)}
)


def _generate_client_device_id() -> str:
    """Generate a random UUID4 string to identify ourselves."""
    return random_uuid_hex()


class JellyfinConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Jellyfin."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the Jellyfin config flow."""
        self.client_device_id: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a user defined configuration."""
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
            except Exception:
                errors["base"] = "unknown"
                _LOGGER.exception("Unexpected exception")
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
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        errors: dict[str, str] = {}

        if user_input is not None:
            reauth_entry = self._get_reauth_entry()
            new_input = reauth_entry.data | user_input

            if self.client_device_id is None:
                self.client_device_id = _generate_client_device_id()

            client = create_client(device_id=self.client_device_id)
            try:
                await validate_input(self.hass, new_input, client)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                errors["base"] = "unknown"
                _LOGGER.exception("Unexpected exception")
            else:
                return self.async_update_reload_and_abort(reauth_entry, data=new_input)

        return self.async_show_form(
            step_id="reauth_confirm", data_schema=REAUTH_DATA_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: JellyfinConfigEntry,
    ) -> OptionsFlowHandler:
        """Create the options flow."""
        return OptionsFlowHandler()


class OptionsFlowHandler(OptionsFlow):
    """Handle an option flow for jellyfin."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONAL_DATA_SCHEMA, self.config_entry.options
            ),
        )

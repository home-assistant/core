"""Config flow for Splunk integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from hass_splunk import hass_splunk
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_SSL,
    CONF_TOKEN,
    CONF_VERIFY_SSL,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DEFAULT_HOST, DEFAULT_NAME, DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

SPLUNK_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TOKEN): str,
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_SSL, default=False): bool,
        vol.Optional(CONF_VERIFY_SSL, default=True): bool,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
    }
)


class SplunkConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Splunk."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = await self._async_validate_input(user_input)

            if not errors:
                await self.async_set_unique_id(
                    f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}"
                )
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=user_input.get(CONF_NAME, DEFAULT_NAME),
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=SPLUNK_SCHEMA,
            errors=errors,
        )

    async def async_step_import(
        self, import_config: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle import from YAML configuration."""
        # Set unique ID to prevent duplicate imports
        host = import_config.get(CONF_HOST, DEFAULT_HOST)
        port = import_config.get(CONF_PORT, DEFAULT_PORT)
        await self.async_set_unique_id(f"{host}:{port}")
        self._abort_if_unique_id_configured()

        # Validate the imported configuration
        errors = await self._async_validate_input(import_config)

        if errors:
            _LOGGER.error("Failed to import Splunk configuration from YAML: %s", errors)
            return self.async_abort(reason="invalid_config")

        return self.async_create_entry(
            title=import_config.get(CONF_NAME, DEFAULT_NAME),
            data=import_config,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth dialog."""
        errors: dict[str, str] = {}

        if user_input is not None:
            reauth_entry = self._get_reauth_entry()

            # Test the new token with existing config
            test_config = {**reauth_entry.data, CONF_TOKEN: user_input[CONF_TOKEN]}
            errors = await self._async_validate_input(test_config)

            if not errors:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={CONF_TOKEN: user_input[CONF_TOKEN]},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_TOKEN): str}),
            errors=errors,
        )

    async def _async_validate_input(self, user_input: dict[str, Any]) -> dict[str, str]:
        """Validate user input and return errors if any."""
        errors: dict[str, str] = {}

        event_collector = hass_splunk(
            session=async_get_clientsession(self.hass),
            host=user_input.get(CONF_HOST, DEFAULT_HOST),
            port=user_input.get(CONF_PORT, DEFAULT_PORT),
            token=user_input[CONF_TOKEN],
            use_ssl=user_input.get(CONF_SSL, False),
            verify_ssl=user_input.get(CONF_VERIFY_SSL, True),
        )

        try:
            # First check connectivity
            connectivity_ok = await event_collector.check(
                connectivity=True, token=False, busy=False
            )
            if not connectivity_ok:
                errors["base"] = "cannot_connect"
                return errors

            # Then check token validity
            token_ok = await event_collector.check(
                connectivity=False, token=True, busy=False
            )
            if not token_ok:
                errors["base"] = "invalid_auth"
                return errors

        except Exception:
            _LOGGER.exception("Unexpected error validating Splunk connection")
            errors["base"] = "unknown"

        return errors

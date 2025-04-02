"""Config flow for KAT Bulgaria integration."""

from __future__ import annotations

import logging
from typing import Any

from kat_bulgaria.errors import KatError, KatErrorType
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import CONF_DRIVING_LICENSE, CONF_PERSON_EGN, CONF_PERSON_NAME, DOMAIN
from .kat_client import KatClient

_LOGGER = logging.getLogger(__name__)

CONFIG_FLOW_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PERSON_NAME): str,
        vol.Required(CONF_PERSON_EGN): str,
        vol.Required(CONF_DRIVING_LICENSE): str,
    }
)


class ConfigFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for kat_bulgaria."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        errors: dict[str, str] = {}

        # If no Input
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=CONFIG_FLOW_DATA_SCHEMA
            )

        # Init user input values & init KatClient
        user_name = user_input[CONF_PERSON_NAME]
        user_egn = user_input[CONF_PERSON_EGN]
        user_license_number = user_input[CONF_DRIVING_LICENSE]

        # Verify user input
        try:
            kat_client = KatClient(self.hass, user_name, user_egn, user_license_number)
            await kat_client.validate_credentials()
        except KatError as err:
            if err.error_type in (
                KatErrorType.VALIDATION_EGN_INVALID,
                KatErrorType.VALIDATION_LICENSE_INVALID,
                KatErrorType.VALIDATION_USER_NOT_FOUND_ONLINE,
            ):
                _LOGGER.warning(
                    "Invalid credentials, unable to setup: %s", err.error_type
                )
                errors["base"] = "invalid_config"

            if err.error_type in (
                KatErrorType.API_TIMEOUT,
                KatErrorType.API_ERROR_READING_DATA,
                KatErrorType.API_INVALID_SCHEMA,
                KatErrorType.API_TOO_MANY_REQUESTS,
                KatErrorType.API_UNKNOWN_ERROR,
            ):
                _LOGGER.warning("KAT API down, unable to setup: %s", err.error_type)
                errors["base"] = "cannot_connect"

        # If this person (EGN) is already configured, abort
        await self.async_set_unique_id(user_egn)
        self._abort_if_unique_id_configured()

        if errors:
            return self.async_show_form(
                step_id="user", data_schema=CONFIG_FLOW_DATA_SCHEMA, errors=errors
            )

        return self.async_create_entry(title=f"KAT - {user_name}", data=user_input)

"""Config flow for KAT Bulgaria integration."""
from __future__ import annotations

import logging
from typing import Any

from kat_bulgaria.obligations import KatApi, KatErrorType
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .common import generate_entity_name
from .const import CONF_DRIVING_LICENSE, CONF_PERSON_EGN, CONF_PERSON_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

CONFIG_FLOW_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PERSON_NAME): str,
        vol.Required(CONF_PERSON_EGN): str,
        vol.Required(CONF_DRIVING_LICENSE): str,
    }
)


class ConfigFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for kat_bulgaria."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""

        # If no Input
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=CONFIG_FLOW_DATA_SCHEMA
            )

        # Init user input values
        user_egn = user_input[CONF_PERSON_EGN]
        user_name = user_input[CONF_PERSON_NAME]
        user_license_number = user_input[CONF_DRIVING_LICENSE]

        # If this person (EGN) is already configured, abort
        await self.async_set_unique_id(user_egn)
        self._abort_if_unique_id_configured()

        # Verify user creds
        verify = await KatApi().async_verify_credentials(user_egn, user_license_number)

        if not verify.success:
            if verify.error_type == KatErrorType.VALIDATION_ERROR:
                return self.async_abort(reason="invalid_config")

            if verify.error_type in (
                KatErrorType.API_UNAVAILABLE,
                KatErrorType.TIMEOUT,
            ):
                return self.async_abort(reason="cannot_connect")

            return self.async_abort(reason="unknown")

        # All good, set up entry
        title = generate_entity_name(user_name)

        return self.async_create_entry(title=title, data=user_input)

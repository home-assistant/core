"""Config flow to configure the Obihai integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .connectivity import validate_auth
from .const import DEFAULT_PASSWORD, DEFAULT_USERNAME, DOMAIN

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default=""): str,
        vol.Optional(
            CONF_USERNAME,
            default=DEFAULT_USERNAME,
        ): str,
        vol.Optional(
            CONF_PASSWORD,
            default=DEFAULT_PASSWORD,
        ): str,
    }
)


async def async_validate_credentials(
    hass: HomeAssistant, user_input: dict[str, Any]
) -> dict[str, str]:
    """Manage Obihai options."""
    errors = {}
    result = await hass.async_add_executor_job(
        validate_auth,
        user_input[CONF_HOST],
        user_input[CONF_USERNAME],
        user_input[CONF_PASSWORD],
    )

    if not result:
        errors["base"] = "cannot_connect"

    return errors


class ObihaiFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for Obihai."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}
        if user_input is not None and not (
            errors := await async_validate_credentials(self.hass, user_input)
        ):
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
            return self.async_create_entry(
                title=user_input.get(CONF_NAME, user_input[CONF_HOST]),
                data={
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                    CONF_USERNAME: user_input[CONF_USERNAME],
                },
            )

        data_schema = self.add_suggested_values_to_schema(DATA_SCHEMA, user_input)
        return self.async_show_form(
            step_id="user",
            errors=errors,
            data_schema=data_schema,
        )

    # DEPRECATED
    async def async_step_import(self, config: dict[str, Any]) -> FlowResult:
        """Handle a flow initialized by importing a config."""
        self._async_abort_entries_match({CONF_HOST: config[CONF_HOST]})
        return self.async_create_entry(
            title=config.get(CONF_NAME, config[CONF_HOST]),
            data={
                CONF_HOST: config[CONF_HOST],
                CONF_PASSWORD: config[CONF_PASSWORD],
                CONF_USERNAME: config[CONF_USERNAME],
            },
        )

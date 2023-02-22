"""Config flow to configure the Obihai integration."""
from __future__ import annotations

from types import MappingProxyType
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_OBIHAI_HOST, DEFAULT_PASSWORD, DEFAULT_USERNAME, DOMAIN
from .obihai_api import validate_auth


@callback
def async_get_schema(
    defaults: dict[str, Any] | MappingProxyType[str, Any]
) -> vol.Schema:
    """Return Obihai schema."""
    schema = {
        vol.Required(CONF_HOST, default=defaults.get(CONF_OBIHAI_HOST, "")): str,
        vol.Optional(
            CONF_USERNAME,
            description={
                "suggested_value": defaults.get(CONF_USERNAME, DEFAULT_USERNAME)
            },
        ): str,
        vol.Optional(
            CONF_PASSWORD,
            default=defaults.get(CONF_PASSWORD, DEFAULT_PASSWORD),
        ): str,
    }

    return vol.Schema(schema)


async def async_validate_credentials(
    hass: HomeAssistant, user_input: dict[str, Any]
) -> dict[str, str]:
    """Manage Obihai options."""
    errors = {}
    result = await hass.async_add_executor_job(
        validate_auth,
        user_input.get(CONF_OBIHAI_HOST),
        user_input.get(CONF_USERNAME),
        user_input[CONF_PASSWORD],
    )

    if not result:
        errors["base"] = "cannot_connect"

    return errors


class ObihaiFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for Obihai."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self._host: str | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> ObihaiOptionsFlowHandler:
        """Get the options flow for this handler."""
        return ObihaiOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        if user_input is not None:
            return await self.async_validate_input(user_input)

        user_input = {CONF_OBIHAI_HOST: self._host or ""}
        return self.async_show_form(
            step_id="user",
            data_schema=async_get_schema(user_input),
        )

    async def async_validate_input(self, user_input: dict[str, Any]) -> FlowResult:
        """Check form inputs for errors."""
        errors = await async_validate_credentials(self.hass, user_input)
        if not errors:
            self._async_abort_entries_match(
                {CONF_OBIHAI_HOST: user_input[CONF_OBIHAI_HOST]}
            )

            # Storing data in option, to allow for changing them later
            # using an options flow.
            return self.async_create_entry(
                title=user_input.get(CONF_NAME, user_input[CONF_OBIHAI_HOST]),
                data={},
                options={
                    CONF_OBIHAI_HOST: user_input[CONF_OBIHAI_HOST],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                    CONF_USERNAME: user_input.get(CONF_USERNAME),
                },
            )

        return self.async_show_form(
            step_id="user",
            data_schema=async_get_schema(user_input),
            errors=errors,
        )

    # DEPRECATED
    async def async_step_import(self, config: dict[str, Any]) -> FlowResult:
        """Handle a flow initialized by importing a config."""
        self._async_abort_entries_match({CONF_OBIHAI_HOST: config[CONF_OBIHAI_HOST]})
        return self.async_create_entry(
            title=config.get(CONF_NAME, config[CONF_OBIHAI_HOST]),
            data={},
            options={
                CONF_OBIHAI_HOST: config[CONF_OBIHAI_HOST],
                CONF_PASSWORD: config[CONF_PASSWORD],
                CONF_USERNAME: config.get(CONF_USERNAME),
            },
        )


class ObihaiOptionsFlowHandler(OptionsFlow):
    """Handle Obihai options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize Obihai options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage Obihai options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = await async_validate_credentials(self.hass, user_input)
            if not errors:
                for entry in self.hass.config_entries.async_entries(DOMAIN):
                    if (
                        entry.entry_id != self.config_entry.entry_id
                        and entry.options[CONF_OBIHAI_HOST]
                        == user_input[CONF_OBIHAI_HOST]
                    ):
                        errors = {CONF_OBIHAI_HOST: "already_configured"}

                if not errors:
                    return self.async_create_entry(
                        title=user_input.get(CONF_NAME, user_input[CONF_OBIHAI_HOST]),
                        data={
                            CONF_OBIHAI_HOST: user_input[CONF_OBIHAI_HOST],
                            CONF_PASSWORD: user_input[CONF_PASSWORD],
                            CONF_USERNAME: user_input.get(CONF_USERNAME),
                        },
                    )
        else:
            user_input = {}

        return self.async_show_form(
            step_id="init",
            data_schema=async_get_schema(user_input or self.config_entry.options),
            errors=errors,
        )

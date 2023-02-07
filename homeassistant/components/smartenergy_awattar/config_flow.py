"""Awattar config flow and options flow setup."""

from typing import Any, Literal

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_COUNTRY, CONF_COUNTRY_LIST, DOMAIN


def _get_config_values(data_input: dict) -> dict:
    data: dict = {}
    config: list[str] = [CONF_COUNTRY, CONF_SCAN_INTERVAL]

    for config_name in config:
        data[config_name] = data_input.get(config_name)

    return data


def _get_config_schema(default_values: dict) -> dict:
    return vol.Schema(
        {
            vol.Required(
                CONF_COUNTRY,
                default=default_values.get(CONF_COUNTRY, CONF_COUNTRY_LIST[0]),
            ): vol.In(sorted(CONF_COUNTRY_LIST)),
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=default_values.get(CONF_SCAN_INTERVAL, 10),
            ): vol.All(vol.Coerce(int), vol.Range(10, 60000)),
        }
    )


class AwattarConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for the Awattar component."""

    VERSION: Literal[1] = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Get the options flow for this handler."""
        return AwattarOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        errors: dict = {}
        data_schema: dict = _get_config_schema({CONF_SCAN_INTERVAL: 10})

        if user_input is not None:
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()

            # set default values to the current so the user is still within the same context,
            # otherwise it makes each input empty
            data_schema = _get_config_schema(
                {
                    CONF_COUNTRY: user_input.get(CONF_COUNTRY),
                    CONF_SCAN_INTERVAL: user_input.get(CONF_SCAN_INTERVAL),
                }
            )

            if not errors:
                return self.async_create_entry(
                    title="Awattar",
                    data=_get_config_values(user_input),
                    options=_get_config_values(user_input),
                )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=None if not errors else errors,
        )


class AwattarOptionsFlowHandler(OptionsFlow):
    """Config flow options handler for the Awattar component."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry: ConfigEntry = config_entry
        self.options: dict[str, Any] = dict(config_entry.options)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        errors: dict = {}
        data_schema: dict = _get_config_schema(
            {
                CONF_COUNTRY: self.config_entry.options.get(CONF_COUNTRY),
                CONF_SCAN_INTERVAL: self.config_entry.options.get(CONF_SCAN_INTERVAL),
            }
        )

        if user_input is not None:
            # set default values to the current so the user is still within the same context,
            # otherwise it makes each input empty
            data_schema = _get_config_schema(
                {
                    CONF_COUNTRY: user_input.get(CONF_COUNTRY),
                    CONF_SCAN_INTERVAL: user_input.get(CONF_SCAN_INTERVAL),
                }
            )

            if not errors:
                self.options.update(user_input)
                return self.async_create_entry(title="", data=self.options)

        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
            errors=None if not errors else errors,
        )

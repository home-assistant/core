"""Awattar config flow and options flow setup."""

from typing import Any, Literal

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_COUNTRY, CONF_COUNTRY_LIST, DOMAIN


def _get_config_schema(default_values: dict) -> vol.Schema:
    """Define a schema with default values and return it."""
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

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
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

            return self.async_create_entry(
                title="Awattar",
                data=user_input,
                options=user_input,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
        )

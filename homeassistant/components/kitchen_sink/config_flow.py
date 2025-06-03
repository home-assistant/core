"""Config flow to configure the Kitchen Sink component."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from . import DOMAIN

CONF_BOOLEAN = "bool"
CONF_INT = "int"


class KitchenSinkConfigFlow(ConfigFlow, domain=DOMAIN):
    """Kitchen Sink configuration flow."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler()

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this handler."""
        return {"entity": SubentryFlowHandler}

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Set the config entry up from yaml."""
        return self.async_create_entry(title="Kitchen Sink", data=import_data)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Reauth step."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reauth confirm step."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return self.async_abort(reason="reauth_successful")


class OptionsFlowHandler(OptionsFlow):
    """Handle options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        return await self.async_step_options_1()

    async def async_step_options_1(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=self.config_entry.options | user_input)

        data_schema = vol.Schema(
            {
                vol.Required("section_1"): data_entry_flow.section(
                    vol.Schema(
                        {
                            vol.Optional(
                                CONF_BOOLEAN,
                                default=self.config_entry.options.get(
                                    CONF_BOOLEAN, False
                                ),
                            ): bool,
                            vol.Optional(CONF_INT): cv.positive_int,
                        }
                    ),
                    {"collapsed": False},
                ),
            }
        )
        self.add_suggested_values_to_schema(
            data_schema,
            {"section_1": {"int": self.config_entry.options.get(CONF_INT, 10)}},
        )

        return self.async_show_form(step_id="options_1", data_schema=data_schema)


class SubentryFlowHandler(ConfigSubentryFlow):
    """Handle subentry flow."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """User flow to create a sensor subentry."""
        return await self.async_step_add_sensor()

    async def async_step_add_sensor(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add a new sensor."""
        if user_input is not None:
            title = user_input.pop("name")
            return self.async_create_entry(data=user_input, title=title)

        return self.async_show_form(
            step_id="add_sensor",
            data_schema=vol.Schema(
                {
                    vol.Required("name"): str,
                    vol.Required("state"): int,
                }
            ),
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Reconfigure a sensor subentry."""
        return await self.async_step_reconfigure_sensor()

    async def async_step_reconfigure_sensor(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Reconfigure a sensor."""
        if user_input is not None:
            title = user_input.pop("name")
            return self.async_update_and_abort(
                self._get_entry(),
                self._get_reconfigure_subentry(),
                data=user_input,
                title=title,
            )

        return self.async_show_form(
            step_id="reconfigure_sensor",
            data_schema=vol.Schema(
                {
                    vol.Required("name"): str,
                    vol.Required("state"): int,
                }
            ),
        )

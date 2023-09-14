"""Config flow for EnergyZero integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowHandler, FlowResult
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.template import Template

from .const import (
    CONF_ENERGY_MODIFIER,
    CONF_GAS_MODIFIER,
    DEFAULT_MODIFIER,
    DOMAIN,
    LOGGER,
)


class EnergyZeroFlowHandlerMixin:
    """Mixin class with shared methods for EnergyZero config flow handlers."""

    _gas_modifier: str | None = None
    _energy_modifier: str | None = None

    async def async_validate_data(self) -> str | None:
        """Validate the user input."""
        data = self._get_data()

        for modifier in (CONF_GAS_MODIFIER, CONF_ENERGY_MODIFIER):
            if not await self._valid_template(data[modifier]):
                return "invalid_template"

            if "price" not in data[modifier]:
                return "missing_price"

        return None

    def _get_schema(self):
        return vol.Schema(
            {
                vol.Optional(CONF_GAS_MODIFIER, default=self._gas_modifier): vol.All(
                    vol.Coerce(str)
                ),
                vol.Optional(
                    CONF_ENERGY_MODIFIER, default=self._energy_modifier
                ): vol.All(vol.Coerce(str)),
            }
        )

    async def _valid_template(self, user_template):
        try:
            value = Template(user_template, self.hass).async_render(price=0)

            if isinstance(value, float):
                return True
        except TemplateError as exception:
            LOGGER.exception(exception)

        return False

    async def async_shared_step(
        self, original: FlowHandler, user_input: dict[str, Any] | None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if (
            user_input is None
            and self._energy_modifier is not None
            and self._gas_modifier is not None
        ):
            return original.async_show_form(
                step_id="init",
                data_schema=self._get_schema(),
                errors=errors,
            )

        self._set_data(user_input)
        if user_input is not None:
            error = await self.async_validate_data()

            if error is None:
                return original.async_create_entry(
                    title="EnergyZero",
                    data=self._get_data(),
                )

            errors["base"] = error

        return original.async_show_form(
            step_id="init", data_schema=self._get_schema(), errors=errors
        )

    def _set_data(self, user_input: dict[str, Any] | None):
        self._gas_modifier = (
            user_input[CONF_GAS_MODIFIER]
            if user_input is not None
            and CONF_GAS_MODIFIER in user_input
            and user_input[CONF_GAS_MODIFIER] not in (None, "")
            else DEFAULT_MODIFIER
        )
        self._energy_modifier = (
            user_input[CONF_ENERGY_MODIFIER]
            if user_input is not None
            and CONF_ENERGY_MODIFIER in user_input
            and user_input[CONF_ENERGY_MODIFIER] not in (None, "")
            else DEFAULT_MODIFIER
        )

    def _get_data(self) -> dict[str, Any]:
        return {
            CONF_GAS_MODIFIER: self._gas_modifier,
            CONF_ENERGY_MODIFIER: self._energy_modifier,
        }


class EnergyZeroFlowHandler(ConfigFlow, EnergyZeroFlowHandlerMixin, domain=DOMAIN):
    """Config flow for EnergyZero integration."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> EnergyZeroOptionFlowHandler:
        """Get the options flow for this handler."""
        return EnergyZeroOptionFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user step."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        return await self.async_shared_step(self, user_input)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        return await self.async_shared_step(self, user_input)


class EnergyZeroOptionFlowHandler(OptionsFlow, EnergyZeroFlowHandlerMixin):
    """EnergyZero config flow options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize EnergyZero options flow."""
        self.config_entry = config_entry
        self._set_data(dict(config_entry.options))

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        return await self.async_shared_step(self, user_input)

"""Config flow for EnergyZero integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.template import Template

from .const import (
    CONF_ENERGY_MODIFYER,
    CONF_GAS_MODIFYER,
    DEFAULT_MODIFYER,
    DOMAIN,
    LOGGER,
)


class EnergyZeroFlowHandlerMixin:
    """Mixin class with shared methods for EnergyZero config flow handlers."""

    def __init__(self):
        """Initialize flow."""
        self._gas_modifyer = None
        self._energy_modifyer = None

    async def async_validate_data(self) -> str | None:
        """Validate the user input."""
        data = self._get_data()

        for modifyer in [CONF_GAS_MODIFYER, CONF_ENERGY_MODIFYER]:
            if not await self._valid_template(data[modifyer]):
                return "invalid_template"

            if "price" not in data[modifyer]:
                return "missing_price"

        return None

    def _get_schema(self):
        return vol.Schema(
            {
                vol.Optional(CONF_GAS_MODIFYER, default=self._gas_modifyer): vol.All(
                    vol.Coerce(str)
                ),
                vol.Optional(
                    CONF_ENERGY_MODIFYER, default=self._energy_modifyer
                ): vol.All(vol.Coerce(str)),
            }
        )

    async def _valid_template(self, user_template):
        try:
            value = Template(user_template, self.hass).async_render(price=0)

            if isinstance(value, float):
                return True
        except Exception as exception:
            LOGGER.exception(exception)

        return False

    async def async_shared_step(
        self, user_input: dict[str, Any] | None, is_initial_setup: bool = True
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if (
            user_input is None
            and self._energy_modifyer is not None
            and self._gas_modifyer is not None
        ):
            return self.async_show_form(
                step_id="init",
                data_schema=self._get_schema(),
                errors=errors,
            )

        self._set_data(user_input)
        if user_input is not None:
            errors["base"] = await self.async_validate_data()

            if errors["base"] is None:
                if is_initial_setup:
                    await self.async_set_unique_id(DOMAIN)
                    self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title="EnergyZero",
                    data=self._get_data(),
                )

        return self.async_show_form(
            step_id="init", data_schema=self._get_schema(), errors=errors
        )

    def _set_data(self, user_input: dict[str, Any] | None):
        self._gas_modifyer = (
            user_input[CONF_GAS_MODIFYER]
            if user_input is not None
            and CONF_GAS_MODIFYER in user_input
            and user_input[CONF_GAS_MODIFYER] not in (None, "")
            else DEFAULT_MODIFYER
        )
        self._energy_modifyer = (
            user_input[CONF_ENERGY_MODIFYER]
            if user_input is not None
            and CONF_ENERGY_MODIFYER in user_input
            and user_input[CONF_ENERGY_MODIFYER] not in (None, "")
            else DEFAULT_MODIFYER
        )

    def _get_data(self) -> dict[str, Any]:
        return {
            CONF_GAS_MODIFYER: self._gas_modifyer,
            CONF_ENERGY_MODIFYER: self._energy_modifyer,
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
        """Handle the initial step."""
        return await self.async_shared_step(user_input)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        return await self.async_shared_step(user_input)


class EnergyZeroOptionFlowHandler(OptionsFlow, EnergyZeroFlowHandlerMixin):
    """EnergyZero config flow options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize EnergyZero options flow."""
        self.config_entry = config_entry
        self._set_data(dict(config_entry.options))

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Manage the options."""
        return await self.async_shared_step(user_input, is_initial_setup=False)

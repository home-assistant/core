"""Config flow for the Home Assistant Green integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.components.hassio import (
    HassioAPIError,
    async_get_green_settings,
    async_set_green_settings,
    is_hassio,
)
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_HW_SETTINGS_SCHEMA = vol.Schema(
    {
        # Sorted to match front panel left to right
        vol.Required("power_led"): selector.BooleanSelector(),
        vol.Required("activity_led"): selector.BooleanSelector(),
        vol.Required("system_health_led"): selector.BooleanSelector(),
    }
)


class HomeAssistantGreenConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Home Assistant Green."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> HomeAssistantGreenOptionsFlow:
        """Return the options flow."""
        return HomeAssistantGreenOptionsFlow()

    async def async_step_system(self, data: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial step."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        return self.async_create_entry(title="Home Assistant Green", data={})


class HomeAssistantGreenOptionsFlow(OptionsFlow):
    """Handle an option flow for Home Assistant Green."""

    _hw_settings: dict[str, bool] | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if not is_hassio(self.hass):
            return self.async_abort(reason="not_hassio")

        return await self.async_step_hardware_settings()

    async def async_step_hardware_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle hardware settings."""

        if user_input is not None:
            if self._hw_settings == user_input:
                return self.async_create_entry(data={})
            try:
                async with asyncio.timeout(10):
                    await async_set_green_settings(self.hass, user_input)
            except (aiohttp.ClientError, TimeoutError, HassioAPIError) as err:
                _LOGGER.warning("Failed to write hardware settings", exc_info=err)
                return self.async_abort(reason="write_hw_settings_error")
            return self.async_create_entry(data={})

        try:
            async with asyncio.timeout(10):
                self._hw_settings: dict[str, bool] = await async_get_green_settings(
                    self.hass
                )
        except (aiohttp.ClientError, TimeoutError, HassioAPIError) as err:
            _LOGGER.warning("Failed to read hardware settings", exc_info=err)
            return self.async_abort(reason="read_hw_settings_error")

        schema = self.add_suggested_values_to_schema(
            STEP_HW_SETTINGS_SCHEMA, self._hw_settings
        )

        return self.async_show_form(step_id="hardware_settings", data_schema=schema)

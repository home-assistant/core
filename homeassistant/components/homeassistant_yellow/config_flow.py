"""Config flow for the Home Assistant Yellow integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.components.hassio import (
    HassioAPIError,
    async_get_yellow_settings,
    async_reboot_host,
    async_set_yellow_settings,
)
from homeassistant.components.homeassistant_hardware import silabs_multiprotocol_addon
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import DOMAIN, ZHA_HW_DISCOVERY_DATA

_LOGGER = logging.getLogger(__name__)

STEP_HW_SETTINGS_SCHEMA = vol.Schema(
    {
        vol.Required("disk_led"): selector.BooleanSelector(),
        vol.Required("heartbeat_led"): selector.BooleanSelector(),
        vol.Required("power_led"): selector.BooleanSelector(),
    }
)


class HomeAssistantYellowConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Home Assistant Yellow."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> HomeAssistantYellowOptionsFlow:
        """Return the options flow."""
        return HomeAssistantYellowOptionsFlow(config_entry)

    async def async_step_system(self, data: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial step."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        return self.async_create_entry(title="Home Assistant Yellow", data={})


class HomeAssistantYellowOptionsFlow(silabs_multiprotocol_addon.OptionsFlowHandler):
    """Handle an option flow for Home Assistant Yellow."""

    _hw_settings: dict[str, bool] | None = None

    async def async_step_on_supervisor(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle logic when on Supervisor host."""
        return self.async_show_menu(
            step_id="main_menu",
            menu_options=[
                "hardware_settings",
                "multipan_settings",
            ],
        )

    async def async_step_hardware_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle hardware settings."""

        if user_input is not None:
            if self._hw_settings == user_input:
                return self.async_create_entry(data={})
            try:
                async with asyncio.timeout(10):
                    await async_set_yellow_settings(self.hass, user_input)
            except (aiohttp.ClientError, TimeoutError, HassioAPIError) as err:
                _LOGGER.warning("Failed to write hardware settings", exc_info=err)
                return self.async_abort(reason="write_hw_settings_error")
            return await self.async_step_confirm_reboot()

        try:
            async with asyncio.timeout(10):
                self._hw_settings: dict[str, bool] = await async_get_yellow_settings(
                    self.hass
                )
        except (aiohttp.ClientError, TimeoutError, HassioAPIError) as err:
            _LOGGER.warning("Failed to read hardware settings", exc_info=err)
            return self.async_abort(reason="read_hw_settings_error")

        schema = self.add_suggested_values_to_schema(
            STEP_HW_SETTINGS_SCHEMA, self._hw_settings
        )

        return self.async_show_form(step_id="hardware_settings", data_schema=schema)

    async def async_step_confirm_reboot(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm reboot host."""
        return self.async_show_menu(
            step_id="reboot_menu",
            menu_options=[
                "reboot_now",
                "reboot_later",
            ],
        )

    async def async_step_reboot_now(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Reboot now."""
        await async_reboot_host(self.hass)
        return self.async_create_entry(data={})

    async def async_step_reboot_later(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Reboot later."""
        return self.async_create_entry(data={})

    async def async_step_multipan_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle multipan settings."""
        return await super().async_step_on_supervisor(user_input)

    async def _async_serial_port_settings(
        self,
    ) -> silabs_multiprotocol_addon.SerialPortSettings:
        """Return the radio serial port settings."""
        return silabs_multiprotocol_addon.SerialPortSettings(
            device="/dev/ttyAMA1",
            baudrate="115200",
            flow_control=True,
        )

    async def _async_zha_physical_discovery(self) -> dict[str, Any]:
        """Return ZHA discovery data when multiprotocol FW is not used.

        Passed to ZHA do determine if the ZHA config entry is connected to the radio
        being migrated.
        """
        return {"hw": ZHA_HW_DISCOVERY_DATA}

    def _zha_name(self) -> str:
        """Return the ZHA name."""
        return "Yellow Multi-PAN"

    def _hardware_name(self) -> str:
        """Return the name of the hardware."""
        return "Home Assistant Yellow"

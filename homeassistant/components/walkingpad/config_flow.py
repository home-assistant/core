"""Config flow for WalkingPad."""
from __future__ import annotations

from typing import Any

from bleak.exc import BleakError
from miio.exceptions import DeviceException
from miio.walkingpad import Walkingpad
import numpy as np
from ph4_walkingpad.pad import Scanner
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_IP_ADDRESS, CONF_TOKEN
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.device_registry import format_mac

from .const import (
    CONF_CONN_TYPE,
    CONF_DEFAULT_SPEED,
    CONF_TYPE_BLE,
    CONF_TYPE_WIFI,
    CONF_UUID,
    DEFAULT_SPEED,
    DOMAIN,
    MAX_SPEED,
    MIN_SPEED,
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a WalkingPad config flow."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        if user_input:
            if user_input.get(CONF_CONN_TYPE) == CONF_TYPE_BLE:
                if not user_input.get(CONF_UUID):
                    return await self.async_step_ble_device()
            elif user_input.get(CONF_CONN_TYPE) == CONF_TYPE_WIFI:
                if not user_input.get(CONF_IP_ADDRESS):
                    return await self.async_step_wifi_device()

        conn_types = {CONF_TYPE_BLE: "Bluetooth", CONF_TYPE_WIFI: "WiFi"}
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_CONN_TYPE): vol.In(conn_types)}),
        )

    async def async_step_ble_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the step to configure BLE device."""
        if user_input:
            if user_input.get(CONF_UUID):
                unique_id = format_mac(user_input[CONF_UUID])
                await self.async_set_unique_id(unique_id, raise_on_progress=False)
                self._abort_if_unique_id_configured()
                user_input[CONF_CONN_TYPE] = CONF_TYPE_BLE
                return self.async_create_entry(
                    title=f"WalkingPad BLE {user_input[CONF_UUID]}",
                    data=user_input,
                )

        configured_devices = {
            entry.data[CONF_UUID]
            for entry in self._async_current_entries()
            if entry.data.get(CONF_UUID)
        }
        devices_name = {}
        try:
            scanner = Scanner()
            await scanner.scan()
        except BleakError:
            return self.async_abort(reason="ble_not_available")

        devices = scanner.devices_dict
        devices = {uuid: dat for uuid, dat in devices.items() if "Walkingpad" in dat[0]}

        for uuid in devices:
            name = devices[uuid][0]
            if uuid in configured_devices:
                continue
            devices_name[uuid] = f"{name}: {uuid}"

        # Check if there is at least one device
        if not devices_name:
            return self.async_abort(reason="no_devices_found")
        return self.async_show_form(
            step_id="ble_device",
            data_schema=vol.Schema({vol.Required(CONF_UUID): vol.In(devices_name)}),
        )

    async def async_step_wifi_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the step to configure WiFi device."""
        errors = {}
        if user_input:
            if user_input.get(CONF_IP_ADDRESS):
                try:
                    device = Walkingpad(
                        user_input[CONF_IP_ADDRESS], user_input[CONF_TOKEN]
                    )
                    device.quick_status()
                except (ValueError, DeviceException):
                    errors["base"] = "cannot connect"
                unique_id = format_mac(device.info().data["mac"])
                await self.async_set_unique_id(unique_id, raise_on_progress=False)
                self._abort_if_unique_id_configured()

            user_input[CONF_CONN_TYPE] = CONF_TYPE_WIFI

            if not errors:
                return self.async_create_entry(
                    title=f"WalkingPad WiFi {user_input[CONF_IP_ADDRESS]}",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="wifi_device",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_IP_ADDRESS): str,
                    vol.Required(CONF_TOKEN): str,
                }
            ),
            errors=errors,
        )


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle WalkingPad options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize Hue options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage WalkingPad options."""
        if user_input:
            user_input[CONF_DEFAULT_SPEED] = user_input[CONF_DEFAULT_SPEED]
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_DEFAULT_SPEED,
                        default=self.config_entry.options.get(
                            CONF_DEFAULT_SPEED, DEFAULT_SPEED
                        ),
                    ): vol.In(np.arange(MIN_SPEED + 0.5, MAX_SPEED + 0.5, 0.5))
                }
            ),
        )

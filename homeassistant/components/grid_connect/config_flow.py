"""Config flow for the Grid Connect integration in Home Assistant.

This module handles the UI configuration flow, allowing users to
set up and manage their integration settings.
"""

import asyncio
import logging
import time
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class GridConnectConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Grid Connect."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        """Entry step: start BLE scan or manual add."""
        errors = {}
        if user_input is not None:
            if user_input.get("action") == "scan":
                return await self.async_step_ble_scan()
            if user_input.get("action") == "manual":
                return await self.async_step_manual()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required("action", default="scan"): vol.In({"scan": "Scan for Devices", "manual": "Specify Device Manually"})}),
            errors=errors,
        )

    async def async_step_ble_scan(self, user_input=None) -> config_entries.ConfigFlowResult:
        """Scan for Grid Connect devices via BLE and present selection."""
        errors = {}
        # Grid Connect BLE service UUID (replace with actual UUID if known)
        GRID_CONNECT_SERVICE_UUID = "0000fd88-0000-1000-8000-00805f9b34fb"
        devices = []
        seen_addresses = set()

        # Use Home Assistant's bluetooth.async_discovered_service_info to get BLE advertisements
        # We'll scan for 10 seconds and collect devices advertising the Grid Connect UUID
        start_time = time.monotonic()
        scan_duration = 10  # seconds
        try:
            while time.monotonic() - start_time < scan_duration:
                for service_info in self.hass.data.get("bluetooth", {}).get("discovered_service_info", []):
                    if (
                        hasattr(service_info, "service_uuids")
                        and GRID_CONNECT_SERVICE_UUID in service_info.service_uuids
                        and service_info.address not in seen_addresses
                    ):
                        devices.append({
                            "id": service_info.address,
                            "name": service_info.name or "Grid Connect Device",
                            "address": service_info.address,
                        })
                        seen_addresses.add(service_info.address)
                await asyncio.sleep(1)
        except (TimeoutError, AttributeError) as e:
            _LOGGER.warning("BLE scan error: %s", e)
        except Exception as e:
            _LOGGER.error("Unexpected BLE scan error: %s", e)
            raise

        if not devices:
            errors["base"] = "no_devices"
            return await self.async_step_manual()
        self.context["devices"] = devices
        return await self.async_step_select_device()



    async def async_step_manual(self, user_input=None) -> config_entries.ConfigFlowResult:
        """Fallback: let user manually specify device details."""
        errors = {}
        if user_input is not None:
            # Accept manual entry and create config entry
            return self.async_create_entry(
                title=user_input["device_name"],
                data={
                    "device_id": user_input["device_id"],
                    "device_name": user_input["device_name"],
                    "device_address": user_input["device_address"],
                },
            )
        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema({
                vol.Required("device_id"): str,
                vol.Required("device_name"): str,
                vol.Required("device_address"): str,
            }),
            errors=errors,
        )

    async def async_step_select_device(self, user_input=None):
        """Let user select a device from their Grid Connect account."""
        devices = self.context.get("devices", [])
        device_names = {d["id"]: f"{d['name']} ({d['model']})" for d in devices}
        errors = {}

        if user_input is not None:
            selected_id = user_input["device"]
            selected = next((d for d in devices if d["id"] == selected_id), None)
            if selected is not None:
                # Save credentials and selected device in config entry
                return self.async_create_entry(
                    title=selected["name"],
                    data={
                        "username": self.context["username"],
                        "password": self.context["password"],
                        "device_id": selected_id,
                        "device_name": selected["name"],
                        "device_model": selected["model"],
                    },
                )
        if selected is None:
            errors["base"] = "device_not_found"

        return self.async_show_form(
            step_id="select_device",
            data_schema=vol.Schema(
                {vol.Required("device"): vol.In(device_names)}
            ),
            description_placeholders=device_names,
            errors=errors,
        )


    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow handler for Grid Connect."""
        return GridConnectOptionsFlowHandler(config_entry)


class GridConnectOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Grid Connect."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None) -> config_entries.ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        "option1", default=self.config_entry.options.get("option1", "")
                    ): str
                }
            ),
        )


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""


class InvalidAuth(Exception):
    """Error to indicate there is invalid auth."""

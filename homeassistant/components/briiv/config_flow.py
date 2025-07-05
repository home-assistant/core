"""Config flow for Briiv integration."""

from __future__ import annotations

import logging
from typing import Any

from pybriiv import BriivAPI, BriivError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT

from .const import CONF_SERIAL_NUMBER, DEFAULT_PORT, DISCOVERY_TIMEOUT, DOMAIN, LOGGER


class BriivConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Briiv Air Purifier."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_devices: dict[str, dict[str, Any]] = {}
        self._configured_devices: set[str] = set()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user initiated discovery."""
        errors: dict[str, str] = {}

        # Get already configured devices
        self._configured_devices = {
            entry.unique_id
            for entry in self._async_current_entries()
            if entry.unique_id is not None
        }

        # Do discovery if no devices or user asked to search again
        if not self._discovered_devices or (
            user_input and user_input.get("action") == "search"
        ):
            try:
                LOGGER.debug("Starting device discovery")

                # Configure debug logging for pybriiv
                pybriiv_logger = logging.getLogger("pybriiv")
                pybriiv_logger.setLevel(logging.DEBUG)
                handler = logging.StreamHandler()
                handler.setLevel(logging.DEBUG)
                pybriiv_logger.addHandler(handler)

                # Run discovery
                devices = await BriivAPI.discover(timeout=DISCOVERY_TIMEOUT)

                LOGGER.debug("Discovery returned %d devices", len(devices))

                self._discovered_devices.clear()
                for device in devices:
                    serial = device["serial_number"]
                    model_name = "Briiv Pro" if device.get("is_pro") else "Briiv"

                    # Include device even if already configured
                    self._discovered_devices[serial] = {
                        "host": device["host"],
                        "is_pro": device.get("is_pro", False),
                        "model": model_name,
                        "configured": serial in self._configured_devices,
                    }
                    LOGGER.debug(
                        "Found device: %s (already configured: %s)",
                        serial,
                        serial in self._configured_devices,
                    )

            except (TimeoutError, BriivError, OSError) as err:
                LOGGER.debug("Discovery error: %s", err)
                errors["base"] = "discovery_error"

        if user_input is None or user_input.get("action") == "search":
            options = []
            configured_options = []

            # Sort devices by serial number
            for serial, info in sorted(self._discovered_devices.items()):
                model = info["model"]
                device_str = f"{model} ({serial})"

                if serial in self._configured_devices:
                    configured_options.append(device_str)
                else:
                    options.append(device_str)

            # Add manual option
            options.extend(["Search Again", "Manual Configuration"])

            schema = {
                vol.Required(
                    "action", default=options[0] if options else "Search Again"
                ): vol.In(options)
            }

            # Show configured devices if any exist
            if configured_options:
                configured_devices_str = "\n".join(
                    [f"• {device}" for device in configured_options]
                )
            else:
                configured_devices_str = "None"

            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(schema),
                errors=errors,
                description_placeholders={
                    "configured_devices": configured_devices_str,
                    "new_devices": str(
                        len(options) - 2
                    ),  # Subtract Search/Manual options
                },
            )

        selected_device = user_input["action"]

        if selected_device == "Search Again":
            return await self.async_step_user({"action": "search"})

        if selected_device == "Manual Configuration":
            return await self.async_step_manual()

        # Extract serial number from selection string
        serial = selected_device.split("(")[1].rstrip(")")
        device_info = self._discovered_devices[serial]

        await self.async_set_unique_id(serial)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=f"{device_info['model']} ({serial})",
            data={
                CONF_HOST: device_info["host"],
                CONF_PORT: DEFAULT_PORT,
                CONF_SERIAL_NUMBER: serial,
            },
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual device entry."""
        errors: dict[str, str] = {}

        if user_input is None:
            return self.async_show_form(
                step_id="manual",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_HOST): str,
                        vol.Required(CONF_SERIAL_NUMBER): str,
                    }
                ),
                errors=errors,
            )

        # Check if device is already configured
        serial = user_input[CONF_SERIAL_NUMBER]
        await self.async_set_unique_id(serial)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=f"Briiv {serial}",
            data={
                CONF_HOST: user_input[CONF_HOST],
                CONF_PORT: DEFAULT_PORT,
                CONF_SERIAL_NUMBER: serial,
            },
        )

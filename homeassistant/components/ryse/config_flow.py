"""Config flow for RYSE BLE integration."""

import logging
from typing import Any, cast

from ryseble.bluetoothctl import filter_ryse_devices_pairing, pair_with_ble_device
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.bluetooth import async_discovered_service_info
from homeassistant.config_entries import ConfigFlowResult

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class RyseBLEDeviceConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow for RYSE BLE Device."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Triggered when user clicks 'Add Integration'."""
        if user_input is None:
            _LOGGER.debug("User started RYSE setup flow")
            return self.async_show_form(
                step_id="user",
                description_placeholders={
                    "instruction": "Press the PAIR button on your RYSE device, then Submit"
                },
                data_schema=vol.Schema({}),
            )

        _LOGGER.debug("User submitted pairing search trigger")
        return await self.async_step_pairing_search()

    async def async_step_pairing_search(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Check already discovered BLE devices for pairing mode."""
        _LOGGER.info("Checking already discovered BLE devices for RYSE in pairing mode")

        devices = async_discovered_service_info(self.hass)
        existing_addresses = {
            entry.data["address"]
            for entry in self._async_current_entries()
            if "address" in entry.data
        }

        device_options = await filter_ryse_devices_pairing(devices, existing_addresses)
        if not device_options:
            _LOGGER.info("No RYSE devices in pairing mode found")
            return self.async_show_form(
                step_id="pairing_search",
                data_schema=vol.Schema({}),
            )

        context = cast(dict[str, Any], self.context)
        context["device_options"] = device_options
        return await self.async_step_select_device()

    async def async_step_select_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let user select one of the discovered pairing devices."""
        context = cast(dict[str, Any], self.context)
        device_options = context.get("device_options", {})

        if user_input is None:
            return self.async_show_form(
                step_id="select_device",
                data_schema=vol.Schema(
                    {vol.Required("device"): vol.In(device_options)}
                ),
                description_placeholders={},
            )

        selected_device = user_input["device"]
        address = selected_device.split("(")[-1].rstrip(")")
        name = selected_device.split("(")[0].strip()

        await self.async_set_unique_id(address)
        self._abort_if_unique_id_configured()

        _LOGGER.info("User selected device %s (%s)", name, address)
        context["selected_device"] = {"name": name, "address": address}
        return await self.async_step_pair()

    async def async_step_pair(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Perform BLE pairing."""
        context = cast(dict[str, Any], self.context)
        device = context["selected_device"]
        name = device["name"]
        address = device["address"]

        _LOGGER.info("Attempting to pair with %s (%s)", name, address)

        try:
            success = await pair_with_ble_device(name, address)
            if not success:
                _LOGGER.warning("Pairing failed for %s (%s)", name, address)
                return self.async_show_form(
                    step_id="pair",
                    data_schema=vol.Schema({}),
                )

            _LOGGER.info("Successfully paired with RYSE device %s (%s)", name, address)
            return self.async_create_entry(
                title=f"RYSE gear {name}",
                data={"address": address},
            )

        except (TimeoutError, OSError):
            _LOGGER.error("Bluetooth error during pairing")
            return self.async_abort(reason="Bluetooth error")

        except Exception:
            _LOGGER.exception("Unexpected error during pairing")
            return self.async_abort(reason="Unexpected error")

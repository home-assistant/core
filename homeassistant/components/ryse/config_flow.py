"""Config flow for RYSE BLE integration."""

import logging
from typing import Any

from ryseble.bluetoothctl import is_pairing_ryse_device, pair_with_ble_device
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_ADDRESS

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class RyseBLEDeviceConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow for RYSE BLE Device."""

    def __init__(self) -> None:
        """Initialize flow attributes."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, str] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle bluetooth discovery step."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()

        # Store discovery info for later use
        self._discovery_info = discovery_info

        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovered BLE device."""
        assert self._discovery_info is not None
        discovery_info = self._discovery_info
        name = discovery_info.name or "RYSE device"

        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                # You can use your existing pairing function here
                success = await pair_with_ble_device(name, discovery_info.address)
                if not success:
                    errors["base"] = "cannot_connect"
                else:
                    return self.async_create_entry(
                        title=name,
                        data={},
                    )
            except Exception:
                _LOGGER.exception("Unexpected error during bluetooth confirm")
                errors["base"] = "unknown"

        self._set_confirm_only()
        self.context["title_placeholders"] = {"name": name}
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={"name": name},
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual 'Add Integration'."""

        errors: dict[str, str] = {}

        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            name = self._discovered_devices[address]

            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()

            try:
                success = await pair_with_ble_device(name, address)
                if success:
                    return self.async_create_entry(title=name, data={})
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        current_ids = self._async_current_ids(include_ignore=False)

        self._discovered_devices.clear()

        for info in async_discovered_service_info(self.hass, connectable=True):
            if info.address in current_ids:
                continue
            if not info.name:  # Skip no-name devices
                continue

            if not await is_pairing_ryse_device(info.address):
                continue

            # Add device to selection list
            self._discovered_devices[info.address] = info.name

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        # Show dropdown form
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): vol.In(self._discovered_devices),
                }
            ),
            errors=errors,
        )

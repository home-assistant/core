"""Config flow for RYSE BLE integration."""

import logging
from typing import Any

from ryseble.bluetoothctl import pair_with_ble_device

from homeassistant import config_entries
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.config_entries import ConfigFlowResult

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class RyseBLEDeviceConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow for RYSE BLE Device."""

    def __init__(self) -> None:
        """Initialize flow attributes."""
        self.device_options: dict[str, str] = {}
        self.selected_device: dict[str, str] | None = None
        self._discovery_info: BluetoothServiceInfoBleak | None = None

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

        errors = {}

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

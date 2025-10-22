"""Config flow for RYSE integration."""

import logging

from bleak import BleakScanner
from bleak.exc import BleakError
from ryseble.bluetoothctl import filter_ryse_devices_pairing, pair_with_ble_device
from ryseble.constants import HARDCODED_UUIDS
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult

_LOGGER = logging.getLogger(__name__)

DOMAIN = "ryse"


class RyseBLEDeviceConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for RYSE BLE Device."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.device_options: dict[str, str] = {}

    async def async_step_user(self, user_input: dict | None = None) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            return await self.async_step_scan()

        return self.async_show_form(
            step_id="user",
            description_placeholders={
                "info": "Press OK to start scanning for RYSE BLE devices"
            },
            data_schema=vol.Schema({}),
            last_step=False,
        )

    async def async_step_scan(self, user_input: dict | None = None) -> ConfigFlowResult:
        """Handle the BLE device scanning step."""
        if user_input is not None:
            selected_device = next(
                (
                    name
                    for addr, name in self.device_options.items()
                    if addr == user_input["device_address"]
                ),
                None,
            )
            if not selected_device:
                return self.async_abort(reason="invalid_selected_device")

            device_name = selected_device.split(" (")[0]
            device_address = user_input["device_address"]

            try:
                _LOGGER.debug(
                    "Attempting to pair with BLE device: %s (%s)",
                    device_name,
                    device_address,
                )

                success = await pair_with_ble_device(device_name, device_address)
                if not success:
                    return self.async_abort(reason="pairing_failed")

                _LOGGER.debug(
                    "Successfully connected and bonded with BLE device: %s (%s)",
                    device_name,
                    device_address,
                )
                return self.async_create_entry(
                    title=f"RYSE gear {device_name}",
                    data={"address": device_address, **HARDCODED_UUIDS},
                )

            except (BleakError, TimeoutError, OSError, ValueError) as err:
                _LOGGER.error(
                    "BLE pairing failed for device %s (%s): %s",
                    device_name,
                    device_address,
                    err,
                )
                return self.async_abort(reason="pairing_failed")

            except Exception:
                _LOGGER.exception(
                    "Unexpected error during pairing for device %s (%s)",
                    device_name,
                    device_address,
                )
                return self.async_abort(reason="unexpected_error")

        # Scan for BLE devices
        devices = await BleakScanner.discover()

        for device in devices:
            _LOGGER.debug(
                "Device Name: %s - Device Address: %s",
                device.name,
                device.address,
            )

        existing_entries = self._async_current_entries()
        existing_addresses = {entry.data["address"] for entry in existing_entries}

        self.device_options = await filter_ryse_devices_pairing(
            devices,
            existing_addresses,
        )

        if not self.device_options:
            _LOGGER.warning("No BLE devices found in pairing mode")
            return self.async_abort(reason="no_ryse_devices_found")

        return self.async_show_form(
            step_id="scan",
            data_schema=vol.Schema(
                {
                    vol.Required("device_address"): vol.In(self.device_options),
                }
            ),
            description_placeholders={"info": "Select a RYSE BLE device to pair"},
        )

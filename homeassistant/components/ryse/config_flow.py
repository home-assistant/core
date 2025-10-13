import voluptuous as vol
import logging
from bleak import BleakScanner

from homeassistant import config_entries

from ryseble.bluetoothctl import (
    pair_with_ble_device,
    filter_ryse_devices_pairing,
)
from ryseble.constants import HARDCODED_UUIDS

_LOGGER = logging.getLogger(__name__)

DOMAIN = "ryse"


class RyseBLEDeviceConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for RYSE BLE Device."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is not None:
            return await self.async_step_scan()

        # Show confirmation popup
        return self.async_show_form(
            step_id="user",
            description_placeholders={
                "info": "Press OK to start scanning for RYSE BLE devices."
            },
            data_schema=vol.Schema({}),  # Empty schema means no input field
            last_step=False,
        )

    async def async_step_scan(self, user_input=None):
        """Handle the BLE device scanning step."""
        if user_input is not None:
            # Extract device name and address from the selected option
            selected_device = next(
                (
                    name
                    for addr, name in self.device_options.items()
                    if addr == user_input["device_address"]
                ),
                None,
            )
            if not selected_device:
                return self.async_abort(reason="Invalid selected device!")

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
                    return self.async_abort(reason="Pairing failed!")

                _LOGGER.debug(
                    "Successfully Connected and Bonded with BLE device: %s (%s)",
                    device_name,
                    device_address,
                )
                # Create entry after successful pairing
                return self.async_create_entry(
                    title=f"RYSE gear {device_name}",
                    data={
                        "address": device_address,
                        **HARDCODED_UUIDS,
                    },
                )

            except Exception as e:
                _LOGGER.error(
                    "Error during pairing process for BLE device: %s (%s): %s",
                    device_name,
                    device_address,
                    e,
                )
                return self.async_abort(reason="Pairing failed!")

        # Scan for BLE devices
        devices = await BleakScanner.discover()

        # Debug: Log all discovered devices
        for device in devices:
            _LOGGER.debug(
                "Device Name: %s - Device Address: %s",
                device.name,
                device.address,
            )

        # Get existing entries to exclude already configured devices
        existing_entries = self._async_current_entries()
        existing_addresses = {entry.data["address"] for entry in existing_entries}

        self.device_options = await filter_ryse_devices_pairing(
            devices,
            existing_addresses,
        )

        if not self.device_options:
            _LOGGER.warning("No BLE devices found in pairing mode.")
            return self.async_abort(reason="No RYSE devices found in pairing mode!")

        # Show device selection form
        return self.async_show_form(
            step_id="scan",
            data_schema=vol.Schema(
                {
                    vol.Required("device_address"): vol.In(self.device_options),
                }
            ),
            description_placeholders={"info": "Select a RYSE BLE device to pair."},
        )

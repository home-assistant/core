"""Config flow for RYSE BLE integration."""

import asyncio
import logging
from typing import Any

from bleak import BleakError
from ryseble.bluetoothctl import is_pairing_ryse_device, pair_with_ble_device
import voluptuous as vol

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS

from .const import DOMAIN, MANUFACTURER_ID, MANUFACTURER_NAME, SERVICE_UUID

_LOGGER = logging.getLogger(__name__)


async def _async_check_pairing(
    device_info: BluetoothServiceInfoBleak,
) -> BluetoothServiceInfoBleak | None:
    """Check if device is pairing."""
    try:
        async with asyncio.timeout(5.0):
            if await is_pairing_ryse_device(device_info.address):
                return device_info
    except TimeoutError as ex:
        _LOGGER.debug(
            "Timeout checking pairing status for %s: %s",
            device_info.address,
            ex,
        )
        return None
    except Exception:
        _LOGGER.exception(
            "Unexpected error checking pairing status for %s",
            device_info.address,
        )
        return None
    return None


class RyseBLEDeviceConfigFlow(ConfigFlow, domain=DOMAIN):
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
            success = False
            try:
                success = await pair_with_ble_device(name, discovery_info.address)
            except TimeoutError, OSError, BleakError:
                _LOGGER.error("Connection error during bluetooth confirm")
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during bluetooth confirm")
                errors["base"] = "unexpected_error"

            if success:
                return self.async_create_entry(
                    title=name,
                    data={},
                )
            if not errors:
                errors["base"] = "cannot_connect"

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

            success = False
            try:
                success = await pair_with_ble_device(name, address)
            except TimeoutError, OSError, BleakError:
                _LOGGER.error("Connection error during pairing")
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unexpected_error"

            if success:
                return self.async_create_entry(title=name, data={})
            if not errors:
                errors["base"] = "cannot_connect"

        current_ids = self._async_current_ids(include_ignore=False)

        self._discovered_devices.clear()

        candidates: list[BluetoothServiceInfoBleak] = []
        for info in async_discovered_service_info(self.hass, connectable=True):
            if info.address in current_ids:
                continue
            if not info.name:  # Skip no-name devices
                continue

            # Pre-filter candidates by name, manufacturer id, or known service UUIDs
            has_ryse_uuid = SERVICE_UUID in info.service_uuids
            has_ryse_mfg = MANUFACTURER_ID in info.manufacturer_data
            has_ryse_name = MANUFACTURER_NAME in info.name.upper()

            if not (has_ryse_uuid or has_ryse_mfg or has_ryse_name):
                continue

            candidates.append(info)

        if candidates:
            results = await asyncio.gather(
                *(_async_check_pairing(info) for info in candidates)
            )
            for device in results:
                if device is not None:
                    # Add device to selection list
                    self._discovered_devices[device.address] = device.name

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

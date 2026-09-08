"""Config flow for RYSE BLE integration."""

import logging
from typing import Any, override

from bleak import BleakError
from ryseble.device import RyseBLEDevice
import voluptuous as vol

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
    async_last_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS

from .const import DOMAIN, is_pairing_mode

_LOGGER = logging.getLogger(__name__)


class RyseBLEDeviceConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle config flow for RYSE BLE Device."""

    def __init__(self) -> None:
        """Initialize flow attributes."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, BluetoothServiceInfoBleak] = {}

    def _latest_service_info(
        self, service_info: BluetoothServiceInfoBleak
    ) -> BluetoothServiceInfoBleak:
        """Return the freshest advertisement for this address, if any."""
        return (
            async_last_service_info(self.hass, service_info.address, connectable=True)
            or service_info
        )

    async def _async_pair(self, service_info: BluetoothServiceInfoBleak) -> str | None:
        """Bond with the device via Bleak, then release the connection.

        Returns an error key, or None on success. Pairing is refused unless the
        latest advertisement still has the PAIR flag set.
        """
        latest = self._latest_service_info(service_info)
        if not is_pairing_mode(latest.manufacturer_data):
            return "not_in_pairing_mode"

        device = RyseBLEDevice(latest.device)
        try:
            if await device.pair():
                return None
        except TimeoutError, OSError, EOFError, BleakError:
            _LOGGER.error("Connection error during pairing")
            return "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected error during pairing")
            return "unexpected_error"
        finally:
            await device.unpair()
        return "cannot_connect"

    @override
    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle bluetooth discovery step."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()

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
            if error := await self._async_pair(discovery_info):
                errors["base"] = error
            else:
                return self.async_create_entry(
                    title=name,
                    data={},
                )

        self._set_confirm_only()
        self.context["title_placeholders"] = {"name": name}
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={"name": name},
            errors=errors,
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual 'Add Integration'."""

        errors: dict[str, str] = {}

        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            service_info = self._discovered_devices[address]

            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()

            if error := await self._async_pair(service_info):
                errors["base"] = error
            else:
                return self.async_create_entry(title=service_info.name, data={})

        current_ids = self._async_current_ids(include_ignore=False)

        # A device only sets the pairing flag in its manufacturer data while the
        # user holds its PAIR button.
        self._discovered_devices = {
            info.address: info
            for info in async_discovered_service_info(self.hass, connectable=True)
            if info.name
            and info.address not in current_ids
            and is_pairing_mode(info.manufacturer_data)
        }

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): vol.In(
                        {
                            address: info.name
                            for address, info in self._discovered_devices.items()
                        }
                    ),
                }
            ),
            errors=errors,
        )

"""Config flow for RYSE BLE integration."""

import logging
from typing import Any, override

from bleak import BleakError
from ryseble import is_pairing_mode
from ryseble.device import RyseBLEDevice
import voluptuous as vol

from homeassistant.components.bluetooth import (
    BaseHaRemoteScanner,
    BluetoothServiceInfoBleak,
    async_clear_address_from_match_history,
    async_discovered_service_info,
    async_last_service_info,
    async_scanner_by_source,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS

from .const import DOMAIN

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

    def _local_service_info(
        self,
        service_info: BluetoothServiceInfoBleak,
        *,
        prefer_pairing: bool = False,
    ) -> BluetoothServiceInfoBleak | None:
        """Return a local-adapter advertisement, ignoring Bluetooth proxies.

        ``async_last_service_info`` can still be an older idle advertisement
        (higher RSSI or a race with the PAIR-flag update). When discovering,
        prefer any local candidate that is in pairing mode so a PAIR press is
        not discarded.
        """
        latest = self._latest_service_info(service_info)
        local: list[BluetoothServiceInfoBleak] = []
        for info in (latest, service_info):
            if info not in local:
                scanner = async_scanner_by_source(self.hass, info.source)
                if not isinstance(scanner, BaseHaRemoteScanner):
                    local.append(info)
        if not local:
            return None
        if prefer_pairing:
            for info in local:
                if is_pairing_mode(info.manufacturer_data):
                    return info
        return local[0]

    async def _async_pair(self, service_info: BluetoothServiceInfoBleak) -> str | None:
        """Bond with the device via Bleak, then release the connection.

        Returns an error key, or None on success. Pairing is refused unless the
        latest advertisement still has the PAIR flag set and came from a local
        adapter; ryseble's BlueZ agent cannot pair through a Bluetooth proxy.
        """
        latest = self._local_service_info(service_info)
        if latest is None:
            return "not_local_source"
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

        latest = self._local_service_info(discovery_info, prefer_pairing=True)
        if latest is None:
            # Release the unique id so a later PAIR advertisement can start a
            # new flow instead of aborting as already_in_progress.
            await self.async_set_unique_id(None)
            async_clear_address_from_match_history(self.hass, discovery_info.address)
            return self.async_abort(reason="not_local_source")
        if not is_pairing_mode(latest.manufacturer_data):
            # Idle shades still match the manifest; drop them here so they are
            # not shown as unusable discoveries. Clear matcher history so a
            # later PAIR-flag advertisement can start a new flow.
            await self.async_set_unique_id(None)
            async_clear_address_from_match_history(self.hass, discovery_info.address)
            return self.async_abort(reason="not_in_pairing_mode")

        self._discovery_info = latest

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

        if user_input is None:
            current_ids = self._async_current_ids(include_ignore=False)

            # A device only sets the pairing flag in its manufacturer data while
            # the user holds its PAIR button.
            self._discovered_devices = {
                info.address: info
                for info in async_discovered_service_info(self.hass, connectable=True)
                if info.name
                and info.address not in current_ids
                and not isinstance(
                    async_scanner_by_source(self.hass, info.source), BaseHaRemoteScanner
                )
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

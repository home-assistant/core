"""Config flow for Meross Bluetooth."""

from typing import Any, override

from meross_ble import (
    MerossAdvertisement,
    MerossBLEError,
    create_device,
    parse_advertisement_data,
)
import probatio

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS, CONF_MODEL
from homeassistant.core import HomeAssistant

from .const import DOMAIN, LOGGER, MANUAL_SCAN_DURATION


def _format_ble_unique_id(address: str) -> str:
    """Format a Bluetooth address as a config entry unique id."""
    return address.replace(":", "").replace("-", "").lower()


def _name_from_discovery(discovery: MerossAdvertisement) -> str:
    """Config entry title (no MAC suffix)."""
    return discovery.friendly_name


def _label_from_discovery(discovery: MerossAdvertisement) -> str:
    """Picker / confirm label: model name plus full MAC."""
    return f"{discovery.friendly_name} ({discovery.address})"


def _discovery_title_placeholders(discovery: MerossAdvertisement) -> dict[str, str]:
    """Return title placeholders for discovery flows."""
    return {
        "name": discovery.friendly_name,
        "address": discovery.address,
    }


def _collect_discovered_service_info(
    hass: HomeAssistant,
) -> list[BluetoothServiceInfoBleak]:
    """Collect unique discovered Bluetooth service infos."""
    seen: set[str] = set()
    results: list[BluetoothServiceInfoBleak] = []
    for connectable in (True, False):
        for info in async_discovered_service_info(hass, connectable):
            if info.address in seen:
                continue
            seen.add(info.address)
            results.append(info)
    return results


class MerossConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Meross Bluetooth."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow state used by Bluetooth setup."""
        self._discovered: MerossAdvertisement | None = None
        self._discovered_devices: dict[str, MerossAdvertisement] = {}

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user: pick a discovered device."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            discovery = self._discovered_devices[address]
            await self.async_set_unique_id(
                _format_ble_unique_id(address), raise_on_progress=False
            )
            self._abort_if_unique_id_configured()
            self._discovered = discovery
            self.context["title_placeholders"] = _discovery_title_placeholders(
                discovery
            )
            return await self.async_step_bluetooth_confirm()

        await bluetooth.async_request_active_scan(self.hass, MANUAL_SCAN_DURATION)

        if bluetooth.async_scanner_count(self.hass, connectable=False) == 0:
            return self.async_abort(reason="no_bluetooth_adapter")

        current = self._async_current_ids(include_ignore=False)
        for info in _collect_discovered_service_info(self.hass):
            address = info.address
            uid = _format_ble_unique_id(address)
            if uid in current or address in self._discovered_devices:
                continue
            parsed = parse_advertisement_data(info.device, info.advertisement)
            if not parsed:
                continue
            self._discovered_devices[address] = parsed

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        if len(self._discovered_devices) == 1:
            discovery = next(iter(self._discovered_devices.values()))
            await self.async_set_unique_id(
                _format_ble_unique_id(discovery.address), raise_on_progress=False
            )
            self._abort_if_unique_id_configured()
            self._discovered = discovery
            self.context["title_placeholders"] = _discovery_title_placeholders(
                discovery
            )
            return await self.async_step_bluetooth_confirm()

        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_ADDRESS): probatio.In(
                        {
                            address: _label_from_discovery(parsed)
                            for address, parsed in self._discovered_devices.items()
                        }
                    ),
                }
            ),
        )

    @override
    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """HA bluetooth matched manifest rules."""
        await self.async_set_unique_id(_format_ble_unique_id(discovery_info.address))
        self._abort_if_unique_id_configured()

        parsed = parse_advertisement_data(
            discovery_info.device, discovery_info.advertisement
        )
        if not parsed:
            return self.async_abort(reason="not_supported")

        self._discovered = parsed
        self.context["title_placeholders"] = _discovery_title_placeholders(parsed)
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm Bluetooth setup; Identify only after the user accepts."""
        assert self._discovered is not None
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await self._async_bind_identify(self._discovered)
            except MerossBLEError as err:
                LOGGER.warning(
                    "%s: Identify on bind failed: %s",
                    self._discovered.address,
                    err,
                )
                errors["base"] = "identify_failed"
            else:
                return self._async_create_ble_entry(self._discovered)

        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders=_discovery_title_placeholders(self._discovered),
            errors=errors,
        )

    async def _async_bind_identify(self, discovery: MerossAdvertisement) -> None:
        """GATT Identify once when the user confirms adding the device."""
        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, discovery.address.upper(), connectable=True
        )
        if not ble_device:
            raise MerossBLEError(
                f"Could not find Meross BLE device with address {discovery.address}"
            )
        device = create_device(ble_device, discovery.model)
        await device.identify()
        LOGGER.info("%s: Identify sent on HA bind (user confirmed)", discovery.address)

    def _async_create_ble_entry(
        self, discovery: MerossAdvertisement
    ) -> ConfigFlowResult:
        return self.async_create_entry(
            title=_name_from_discovery(discovery),
            data={
                CONF_ADDRESS: discovery.address,
                CONF_MODEL: discovery.model.value,
            },
        )

"""Config flow for Rainforest RAVEn devices."""

import asyncio
from typing import Any, override
from urllib.parse import urlsplit

from aioraven.data import MeterType
from aioraven.device import RAVEnConnectionError
from aioraven.serial import RAVEnSerialDevice
import probatio

from homeassistant.components import usb
from homeassistant.config_entries import (
    SOURCE_IGNORE,
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_DEVICE, CONF_MAC, CONF_NAME
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.helpers.service_info.usb import UsbServiceInfo

from .const import CONF_NETWORK_ENDPOINT, DEFAULT_NAME, DOMAIN, NETWORK_SOCKET_OPTION


def _format_id(value: str | int | None) -> str:
    if isinstance(value, str):
        return value
    return f"{value or 0:04X}"


def _generate_unique_id(info: usb.USBDevice | usb.SerialDevice | UsbServiceInfo) -> str:
    """Generate unique id from usb attributes."""
    vid = info.vid if isinstance(info, (usb.USBDevice, UsbServiceInfo)) else None
    pid = info.pid if isinstance(info, (usb.USBDevice, UsbServiceInfo)) else None

    return (
        f"{_format_id(vid)}:{_format_id(pid)}_{info.serial_number}"
        f"_{info.manufacturer}_{info.description}"
    )


def _is_valid_socket_endpoint(endpoint: str) -> bool:
    """Return whether the endpoint is a valid socket URL."""
    try:
        parsed = urlsplit(endpoint)
        port = parsed.port
    except ValueError:
        return False

    return (
        parsed.scheme == "socket"
        and parsed.hostname is not None
        and port is not None
        and port > 0
        and not parsed.username
        and not parsed.password
        and not parsed.path
        and not parsed.query
        and not parsed.fragment
    )


def _generate_socket_unique_id(device_mac: bytes) -> str:
    """Generate a unique ID from the RAVEn device MAC."""
    return f"socket_{device_mac.hex()}"


class RainforestRavenConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Rainforest RAVEn devices."""

    def __init__(self) -> None:
        """Set up flow instance."""
        self._dev_path: str | None = None
        self._meter_macs: set[str] = set()
        self._reconfigure_entry: ConfigEntry | None = None
        self._reconfigure_unique_id: str | None = None

    async def _validate_device(
        self, dev_path: str, *, reconfigure: bool = False
    ) -> bytes | None:
        self._meter_macs.clear()
        if not reconfigure:
            self._abort_if_unique_id_configured(updates={CONF_DEVICE: dev_path})
        device_mac = None
        async with (
            asyncio.timeout(5),
            RAVEnSerialDevice(dev_path) as raven_device,
        ):
            await raven_device.synchronize()
            device_info = await raven_device.get_device_info()
            if device_info is not None:
                device_mac = device_info.device_mac_id
            meters = await raven_device.get_meter_list()
            if meters:
                for meter in meters.meter_mac_ids or ():
                    meter_info = await raven_device.get_meter_info(meter=meter)
                    if meter_info and (
                        meter_info.meter_type is None
                        or meter_info.meter_type == MeterType.ELECTRIC
                    ):
                        self._meter_macs.add(meter.hex())
        self._dev_path = dev_path
        return device_mac

    async def _validate_reconfigure_device(self, dev_path: str) -> bytes | None:
        """Validate a reconfigure target without competing with coordinator polling."""
        entry = self._reconfigure_entry
        if entry is not None and entry.state is ConfigEntryState.LOADED:
            async with entry.runtime_data.async_pause_updates():
                return await self._validate_device(dev_path, reconfigure=True)
        return await self._validate_device(dev_path, reconfigure=True)

    async def _validate_socket_device(
        self, endpoint: str, *, reconfigure: bool = False
    ) -> bytes:
        """Validate a socket endpoint and return its RAVEn device MAC."""
        if reconfigure:
            device_mac = await self._validate_reconfigure_device(endpoint)
        else:
            device_mac = await self._validate_device(endpoint)
        if device_mac is None:
            raise RAVEnConnectionError
        return device_mac

    async def _async_remove_ignored_entry(self, unique_id: str) -> None:
        """Remove an ignored entry matching a device being reconfigured."""
        for entry in self._async_current_entries(include_ignore=True):
            if entry.source == SOURCE_IGNORE and entry.unique_id == unique_id:
                await self.hass.config_entries.async_remove(entry.entry_id)

    def _device_is_configured(self, device_mac: bytes) -> bool:
        """Return whether another config entry is linked to the device."""
        reconfigure_entry_id = (
            self._reconfigure_entry.entry_id
            if self._reconfigure_entry is not None
            else None
        )
        return any(
            entry.entry_id != reconfigure_entry_id
            and entry.unique_id == _generate_socket_unique_id(device_mac)
            for entry in self._async_current_entries(include_ignore=False)
        ) or any(
            entry_id != reconfigure_entry_id
            for device in dr.async_get(self.hass).async_get_devices(
                identifiers={(DOMAIN, device_mac.hex())}
            )
            for entry_id in (device.config_entry_id,)
        )

    def _configured_device_mac(self, entry: ConfigEntry) -> bytes | None:
        """Return the MAC registered for a config entry, if available."""
        for device in dr.async_entries_for_config_entry(
            dr.async_get(self.hass), entry.entry_id
        ):
            for domain, identifier in device.identifiers:
                if domain == DOMAIN:
                    return bytes.fromhex(identifier)
        if entry.unique_id is not None and entry.unique_id.startswith("socket_"):
            return bytes.fromhex(entry.unique_id.removeprefix("socket_"))
        return None

    async def async_step_meters(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Connect to device and discover meters."""
        errors: dict[str, str] = {}
        if user_input is not None:
            meter_macs = []
            for raw_mac in user_input.get(CONF_MAC, ()):
                mac = bytes.fromhex(raw_mac).hex()
                if mac not in meter_macs:
                    meter_macs.append(mac)
            if meter_macs and not errors:
                if self._reconfigure_entry is not None:
                    if self._reconfigure_unique_id is not None:
                        await self._async_remove_ignored_entry(
                            self._reconfigure_unique_id
                        )
                    return self.async_update_reload_and_abort(
                        self._reconfigure_entry,
                        unique_id=self._reconfigure_unique_id,
                        data={CONF_DEVICE: self._dev_path, CONF_MAC: meter_macs},
                    )
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME, DEFAULT_NAME),
                    data={
                        CONF_DEVICE: self._dev_path,
                        CONF_MAC: meter_macs,
                    },
                )

        schema = probatio.Schema(
            {
                probatio.Required(CONF_MAC): SelectSelector(
                    SelectSelectorConfig(
                        options=sorted(self._meter_macs),
                        mode=SelectSelectorMode.DROPDOWN,
                        multiple=True,
                        translation_key=CONF_MAC,
                    )
                ),
            }
        )
        return self.async_show_form(step_id="meters", data_schema=schema, errors=errors)

    def _connection_schema(
        self,
        port_map: dict[str, usb.USBDevice | usb.SerialDevice],
        default_device: str | None = None,
    ) -> probatio.Schema:
        """Build the serial device selection form schema."""
        device_key = probatio.Required(CONF_DEVICE)
        if default_device is not None:
            device_key = probatio.Required(CONF_DEVICE, default=default_device)
        return probatio.Schema(
            {device_key: probatio.In([*port_map, NETWORK_SOCKET_OPTION])}
        )

    async def async_step_network(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure a network socket endpoint."""
        errors: dict[str, str] = {}
        if user_input is not None:
            endpoint = user_input[CONF_NETWORK_ENDPOINT].strip()
            if not _is_valid_socket_endpoint(endpoint):
                errors[CONF_NETWORK_ENDPOINT] = "invalid_network_endpoint"
            else:
                endpoint = urlsplit(endpoint).geturl()
                try:
                    device_mac = await self._validate_socket_device(
                        endpoint, reconfigure=self._reconfigure_entry is not None
                    )
                except TimeoutError:
                    errors[CONF_NETWORK_ENDPOINT] = "timeout_connect"
                except OSError, RAVEnConnectionError:
                    errors[CONF_NETWORK_ENDPOINT] = "cannot_connect"
                else:
                    if self._reconfigure_entry is not None:
                        configured_mac = self._configured_device_mac(
                            self._reconfigure_entry
                        )
                        if (
                            configured_mac is None
                            and not self._reconfigure_entry.data[
                                CONF_DEVICE
                            ].startswith("socket://")
                        ) or (
                            configured_mac is not None and configured_mac != device_mac
                        ):
                            return self.async_abort(reason="unique_id_mismatch")
                    if self._device_is_configured(device_mac):
                        return self.async_abort(reason="device_already_configured")
                    unique_id = _generate_socket_unique_id(device_mac)
                    await self.async_set_unique_id(unique_id)
                    if (
                        self._reconfigure_entry is not None
                        and self._reconfigure_entry.data[CONF_DEVICE].startswith(
                            "socket://"
                        )
                    ):
                        self._abort_if_unique_id_mismatch()
                    if self._reconfigure_entry is not None:
                        self._reconfigure_unique_id = unique_id
                    return await self.async_step_meters()

        default_endpoint = ""
        if self._reconfigure_entry is not None:
            configured_device = self._reconfigure_entry.data[CONF_DEVICE]
            if configured_device.startswith("socket://"):
                default_endpoint = configured_device
        return self.async_show_form(
            step_id="network",
            data_schema=probatio.Schema(
                {
                    probatio.Required(
                        CONF_NETWORK_ENDPOINT, default=default_endpoint
                    ): str
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reconfigure the serial device and selected meters."""
        entry = self._get_reconfigure_entry()
        other_devices = {
            other.data[CONF_DEVICE]
            for other in self._async_current_entries(include_ignore=False)
            if other.entry_id != entry.entry_id
        }
        ports = await usb.async_scan_serial_ports(self.hass)
        port_map = {
            usb.human_readable_device_name(
                port.device,
                port.serial_number,
                port.manufacturer,
                port.description,
                port.vid if isinstance(port, usb.USBDevice) else None,
                port.pid if isinstance(port, usb.USBDevice) else None,
            ): port
            for port in ports
            if port.device not in other_devices
        }

        errors: dict[str, str] = {}
        if user_input is not None:
            selected_device = user_input[CONF_DEVICE]
            if selected_device == NETWORK_SOCKET_OPTION:
                self._reconfigure_entry = entry
                return await self.async_step_network()

            if (port := port_map.get(selected_device)) is None:
                errors[CONF_DEVICE] = "cannot_connect"
                return self.async_show_form(
                    step_id="reconfigure",
                    data_schema=self._connection_schema(
                        port_map,
                        NETWORK_SOCKET_OPTION
                        if entry.data[CONF_DEVICE].startswith("socket://")
                        else None,
                    ),
                    errors=errors,
                )
            unique_id = _generate_unique_id(port)
            await self.async_set_unique_id(unique_id)
            if any(
                other.unique_id == unique_id and other.entry_id != entry.entry_id
                for other in self._async_current_entries(include_ignore=False)
            ):
                return self.async_abort(reason="already_configured")
            self._reconfigure_entry = entry
            self._reconfigure_unique_id = unique_id
            try:
                device_mac = await self._validate_reconfigure_device(port.device)
            except TimeoutError:
                errors[CONF_DEVICE] = "timeout_connect"
            except OSError, RAVEnConnectionError:
                errors[CONF_DEVICE] = "cannot_connect"
            else:
                configured_mac = self._configured_device_mac(entry)
                if configured_mac is None and not entry.data[CONF_DEVICE].startswith(
                    "socket://"
                ):
                    self._abort_if_unique_id_mismatch()
                    if device_mac is not None and self._device_is_configured(
                        device_mac
                    ):
                        return self.async_abort(reason="device_already_configured")
                    return await self.async_step_meters()
                if device_mac is None:
                    errors[CONF_DEVICE] = "cannot_connect"
                elif configured_mac is not None and configured_mac != device_mac:
                    return self.async_abort(reason="unique_id_mismatch")
                elif self._device_is_configured(device_mac):
                    return self.async_abort(reason="device_already_configured")
                else:
                    return await self.async_step_meters()

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self._connection_schema(
                port_map,
                NETWORK_SOCKET_OPTION
                if entry.data[CONF_DEVICE].startswith("socket://")
                else None,
            ),
            errors=errors,
        )

    @override
    async def async_step_usb(self, discovery_info: UsbServiceInfo) -> ConfigFlowResult:
        """Handle USB Discovery."""
        dev_path = discovery_info.device
        unique_id = _generate_unique_id(discovery_info)
        await self.async_set_unique_id(unique_id)
        try:
            device_mac = await self._validate_device(dev_path)
        except TimeoutError:
            return self.async_abort(reason="timeout_connect")
        except RAVEnConnectionError:
            return self.async_abort(reason="cannot_connect")
        if device_mac is not None and self._device_is_configured(device_mac):
            return self.async_abort(reason="device_already_configured")
        return await self.async_step_meters()

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        if self._async_in_progress():
            return self.async_abort(reason="already_in_progress")
        ports = await usb.async_scan_serial_ports(self.hass)
        existing_devices = [
            entry.data[CONF_DEVICE] for entry in self._async_current_entries()
        ]
        port_map = {
            usb.human_readable_device_name(
                port.device,
                port.serial_number,
                port.manufacturer,
                port.description,
                port.vid if isinstance(port, usb.USBDevice) else None,
                port.pid if isinstance(port, usb.USBDevice) else None,
            ): port
            for port in ports
            if port.device not in existing_devices
        }

        errors = {}
        if user_input is not None:
            selected_device = user_input[CONF_DEVICE]
            if selected_device == NETWORK_SOCKET_OPTION:
                return await self.async_step_network()

            port = port_map[selected_device]
            unique_id = _generate_unique_id(port)
            await self.async_set_unique_id(unique_id)
            try:
                device_mac = await self._validate_device(port.device)
            except TimeoutError:
                errors[CONF_DEVICE] = "timeout_connect"
            except RAVEnConnectionError:
                errors[CONF_DEVICE] = "cannot_connect"
            else:
                if device_mac is not None and self._device_is_configured(device_mac):
                    return self.async_abort(reason="device_already_configured")
                return await self.async_step_meters()

        return self.async_show_form(
            step_id="user",
            data_schema=self._connection_schema(port_map),
            errors=errors,
        )

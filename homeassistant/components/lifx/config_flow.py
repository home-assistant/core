"""Config flow flow LIFX."""
from __future__ import annotations

import socket
from typing import Any

from aiolifx.aiolifx import Light
from aiolifx.connection import LIFXConnection
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.components.dhcp import DhcpServiceInfo
from homeassistant.const import CONF_DEVICE, CONF_HOST
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.typing import DiscoveryInfoType

from .const import (
    _LOGGER,
    CONF_SERIAL,
    DEFAULT_ATTEMPTS,
    DOMAIN,
    OVERALL_TIMEOUT,
    TARGET_ANY,
)
from .discovery import async_discover_devices
from .util import (
    async_entry_is_legacy,
    async_get_legacy_entry,
    async_multi_execute_lifx_with_retries,
    formatted_serial,
    lifx_features,
    mac_matches_serial_number,
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for LIFX."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_devices: dict[str, Light] = {}
        self._discovered_device: Light | None = None

    async def async_step_dhcp(self, discovery_info: DhcpServiceInfo) -> FlowResult:
        """Handle discovery via DHCP."""
        mac = discovery_info.macaddress
        host = discovery_info.ip
        hass = self.hass
        for entry in self._async_current_entries():
            if (
                entry.unique_id
                and not async_entry_is_legacy(entry)
                and mac_matches_serial_number(mac, entry.unique_id)
            ):
                if entry.data[CONF_HOST] != host:
                    hass.config_entries.async_update_entry(
                        entry, data={**entry.data, CONF_HOST: host}
                    )
                    hass.async_create_task(
                        hass.config_entries.async_reload(entry.entry_id)
                    )
                return self.async_abort(reason="already_configured")
        return await self._async_handle_discovery(host)

    async def async_step_homekit(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle HomeKit discovery."""
        return await self._async_handle_discovery(host=discovery_info.host)

    async def async_step_integration_discovery(
        self, discovery_info: DiscoveryInfoType
    ) -> FlowResult:
        """Handle LIFX UDP broadcast discovery."""
        serial = discovery_info[CONF_SERIAL]
        host = discovery_info[CONF_HOST]
        await self.async_set_unique_id(formatted_serial(serial))
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})
        return await self._async_handle_discovery(host, serial)

    async def _async_handle_discovery(
        self, host: str, serial: str | None = None
    ) -> FlowResult:
        """Handle any discovery."""
        self._async_abort_entries_match({CONF_HOST: host})
        self.context[CONF_HOST] = host
        if any(
            progress.get("context", {}).get(CONF_HOST) == host
            for progress in self._async_in_progress()
        ):
            return self.async_abort(reason="already_in_progress")
        if not (
            device := await self._async_try_connect(
                host, serial=serial, raise_on_progress=True
            )
        ):
            return self.async_abort(reason="cannot_connect")
        self._discovered_device = device
        return await self.async_step_discovery_confirm()

    @callback
    def _async_discovered_pending_migration(self) -> bool:
        """Check if a discovered device is pending migration."""
        assert self.unique_id is not None
        if not (legacy_entry := async_get_legacy_entry(self.hass)):
            return False
        device_registry = dr.async_get(self.hass)
        existing_device = device_registry.async_get_device(
            identifiers={(DOMAIN, self.unique_id)}
        )
        return bool(
            existing_device is not None
            and legacy_entry.entry_id in existing_device.config_entries
        )

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm discovery."""
        assert self._discovered_device is not None
        discovered = self._discovered_device
        _LOGGER.debug(
            "Confirming discovery of %s (%s) [%s]",
            discovered.label,
            discovered.group,
            discovered.mac_addr,
        )
        if user_input is not None or self._async_discovered_pending_migration():
            return self._async_create_entry_from_device(discovered)

        self._abort_if_unique_id_configured(updates={CONF_HOST: discovered.ip_addr})
        self._set_confirm_only()
        placeholders = {
            "label": discovered.label,
            "group": discovered.group,
        }
        self.context["title_placeholders"] = placeholders
        return self.async_show_form(
            step_id="discovery_confirm", description_placeholders=placeholders
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            if not host:
                return await self.async_step_pick_device()
            if (
                device := await self._async_try_connect(host, raise_on_progress=False)
            ) is None:
                errors["base"] = "cannot_connect"
            else:
                return self._async_create_entry_from_device(device)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Optional(CONF_HOST, default=""): str}),
            errors=errors,
        )

    async def async_step_pick_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the step to pick discovered device."""
        if user_input is not None:
            serial = user_input[CONF_DEVICE]
            await self.async_set_unique_id(serial, raise_on_progress=False)
            device_without_label = self._discovered_devices[serial]
            device = await self._async_try_connect(
                device_without_label.ip_addr, raise_on_progress=False
            )
            if not device:
                return self.async_abort(reason="cannot_connect")
            return self._async_create_entry_from_device(device)

        configured_serials: set[str] = set()
        configured_hosts: set[str] = set()
        for entry in self._async_current_entries():
            if entry.unique_id and not async_entry_is_legacy(entry):
                configured_serials.add(entry.unique_id)
                configured_hosts.add(entry.data[CONF_HOST])
        self._discovered_devices = {
            # device.mac_addr is not the mac_address, its the serial number
            device.mac_addr: device
            for device in await async_discover_devices(self.hass)
        }
        devices_name = {
            serial: f"{serial} ({device.ip_addr})"
            for serial, device in self._discovered_devices.items()
            if serial not in configured_serials
            and device.ip_addr not in configured_hosts
        }
        # Check if there is at least one device
        if not devices_name:
            return self.async_abort(reason="no_devices_found")
        return self.async_show_form(
            step_id="pick_device",
            data_schema=vol.Schema({vol.Required(CONF_DEVICE): vol.In(devices_name)}),
        )

    @callback
    def _async_create_entry_from_device(self, device: Light) -> FlowResult:
        """Create a config entry from a smart device."""
        self._abort_if_unique_id_configured(updates={CONF_HOST: device.ip_addr})
        return self.async_create_entry(
            title=device.label,
            data={CONF_HOST: device.ip_addr},
        )

    async def _async_try_connect(
        self, host: str, serial: str | None = None, raise_on_progress: bool = True
    ) -> Light | None:
        """Try to connect."""
        self._async_abort_entries_match({CONF_HOST: host})
        connection = LIFXConnection(host, TARGET_ANY)
        try:
            await connection.async_setup()
        except socket.gaierror:
            return None
        device: Light = connection.device
        try:
            # get_hostfirmware required for MAC address offset
            # get_version required for lifx_features()
            # get_label required to log the name of the device
            # get_group required to populate suggested areas
            messages = await async_multi_execute_lifx_with_retries(
                [
                    device.get_hostfirmware,
                    device.get_version,
                    device.get_label,
                    device.get_group,
                ],
                DEFAULT_ATTEMPTS,
                OVERALL_TIMEOUT,
            )
        except TimeoutError:
            return None
        finally:
            connection.async_stop()
        if (
            messages is None
            or len(messages) != 4
            or lifx_features(device)["relays"] is True
            or device.host_firmware_version is None
        ):
            return None  # relays not supported
        # device.mac_addr is not the mac_address, its the serial number
        device.mac_addr = serial or messages[0].target_addr
        await self.async_set_unique_id(
            formatted_serial(device.mac_addr), raise_on_progress=raise_on_progress
        )
        return device

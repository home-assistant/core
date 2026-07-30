"""Config flow for LIFX."""

from dataclasses import dataclass
from typing import Any, Self, override

from lifx import (
    Device,
    DiscoveredDevice,
    LifxError,
    find_by_ip,
    find_by_serial,
    mac_candidates_for_serial,
)
import voluptuous as vol

from homeassistant.components import onboarding
from homeassistant.config_entries import ConfigEntryState, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_DEVICE, CONF_HOST
from homeassistant.core import callback
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.service_info.zeroconf import (
    ATTR_PROPERTIES_ID,
    ZeroconfServiceInfo,
)
from homeassistant.helpers.typing import DiscoveryInfoType

from .const import CONF_SERIAL, DOMAIN, LOGGER
from .coordinator import LIFXConfigEntry
from .discovery import async_discover_devices
from .util import async_entry_serial, normalize_serial


@dataclass(slots=True)
class FlowDevice:
    """Closed LIFX device data retained by a config flow."""

    ip: str
    serial: str
    label: str
    group: str


class LIFXConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for LIFX."""

    VERSION = 2

    host: str | None = None

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_devices: dict[str, DiscoveredDevice] = {}
        self._discovered_device: FlowDevice | None = None

    async def _async_set_serial_and_repair(
        self, raw_serial: str, host: str, raise_on_progress: bool = True
    ) -> None:
        """Set the device identity and repair a configured host."""
        raw_serial = normalize_serial(raw_serial)
        await self.async_set_unique_id(raw_serial, raise_on_progress=raise_on_progress)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

    @override
    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle discovery via LIFX mDNS."""
        raw_serial = discovery_info.properties.get(ATTR_PROPERTIES_ID)
        if not isinstance(raw_serial, str):
            serial = None
        else:
            try:
                serial = normalize_serial(raw_serial)
            except ValueError:
                serial = None
        return await self._async_handle_discovery(discovery_info.host, serial)

    @override
    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle discovery via DHCP."""
        host = discovery_info.ip
        dhcp_mac = normalize_serial(discovery_info.macaddress)
        for entry in self._async_current_entries():
            if (entry_serial := async_entry_serial(entry)) is None:
                continue
            if any(
                dhcp_mac == normalize_serial(candidate)
                for candidate in mac_candidates_for_serial(entry_serial)
            ):
                # The entry is matched on its serial rather than its unique ID,
                # which is still colon separated until the entry is set up
                await self.async_set_unique_id(entry_serial)
                return self._async_abort_configured_entry(entry, host)
        return await self._async_handle_discovery(host)

    @callback
    def _async_abort_configured_entry(
        self, entry: LIFXConfigEntry, host: str
    ) -> ConfigFlowResult:
        """Repair the host of an already configured entry and abort."""
        if self.hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_HOST: host}
        ) and entry.state in (ConfigEntryState.LOADED, ConfigEntryState.SETUP_RETRY):
            self.hass.config_entries.async_schedule_reload(entry.entry_id)
        return self.async_abort(reason="already_configured")

    @override
    async def async_step_homekit(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle HomeKit discovery."""
        return await self._async_handle_discovery(discovery_info.host)

    @override
    async def async_step_integration_discovery(
        self, discovery_info: DiscoveryInfoType
    ) -> ConfigFlowResult:
        """Handle LIFX UDP broadcast discovery."""
        return await self._async_handle_discovery(
            discovery_info[CONF_HOST], discovery_info[CONF_SERIAL]
        )

    async def _async_handle_discovery(
        self, host: str, serial: str | None = None
    ) -> ConfigFlowResult:
        """Handle discovery with serial or IP-only identification."""
        self.host = host
        if serial is not None:
            await self._async_set_serial_and_repair(serial, host)
        elif self.hass.config_entries.flow.async_has_matching_flow(self):
            return self.async_abort(reason="already_in_progress")

        if not (device := await self._async_try_connect(host, serial)):
            return self.async_abort(reason="cannot_connect")
        if serial is None:
            await self._async_set_serial_and_repair(device.serial, device.ip)
        self._discovered_device = device
        return await self.async_step_discovery_confirm()

    @override
    def is_matching(self, other_flow: Self) -> bool:
        """Return True if another unidentified flow targets the same host."""
        return other_flow.host == self.host

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        assert self._discovered_device is not None
        discovered = self._discovered_device
        LOGGER.debug(
            "Confirming discovery of %s (%s) [%s]",
            discovered.label,
            discovered.group,
            discovered.serial,
        )
        if user_input is not None or not onboarding.async_is_onboarded(self.hass):
            return self._async_create_entry_from_device(discovered)

        self._abort_if_unique_id_configured(updates={CONF_HOST: discovered.ip})
        self._set_confirm_only()
        placeholders = {"label": discovered.label, "group": discovered.group}
        self.context["title_placeholders"] = placeholders
        return self.async_show_form(
            step_id="discovery_confirm", description_placeholders=placeholders
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a change of host for an already configured device.

        Whatever answers at the new address identifies itself, so an address
        that now belongs to a different LIFX device is rejected rather than
        silently rebinding the entry to it.
        """
        entry = self._get_reconfigure_entry()
        errors = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            if device := await self._async_try_connect(host):
                await self.async_set_unique_id(device.serial)
                self._abort_if_unique_id_mismatch(reason="wrong_device")
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_HOST: device.ip}
                )
            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {vol.Required(CONF_HOST, default=entry.data[CONF_HOST]): str}
            ),
            errors=errors,
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            serial = user_input[CONF_SERIAL]
            if not host and not serial:
                return await self.async_step_pick_device()
            try:
                raw_serial = normalize_serial(serial) if serial else None
            except ValueError:
                errors[CONF_SERIAL] = "invalid_serial"
            else:
                if device := await self._async_try_connect(host or None, raw_serial):
                    await self._async_set_serial_and_repair(
                        device.serial, device.ip, raise_on_progress=False
                    )
                    return self._async_create_entry_from_device(device)
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_HOST, default=""): str,
                    vol.Optional(CONF_SERIAL, default=""): str,
                }
            ),
            errors=errors,
        )

    async def async_step_pick_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the step to pick a broadcast-discovered device."""
        if user_input is not None:
            selected = self._discovered_devices[user_input[CONF_DEVICE]]
            if not (
                device := await self._async_try_connect(selected.ip, selected.serial)
            ):
                return self.async_abort(reason="cannot_connect")
            await self._async_set_serial_and_repair(
                device.serial, device.ip, raise_on_progress=False
            )
            return self._async_create_entry_from_device(device)

        configured_serials = {
            serial
            for entry in self._async_current_entries()
            if (serial := async_entry_serial(entry)) is not None
        }
        self._discovered_devices = {
            serial: device
            for device in await async_discover_devices(self.hass)
            if (serial := normalize_serial(device.serial)) not in configured_serials
        }
        device_names = {
            serial: f"{serial} ({device.ip})"
            for serial, device in self._discovered_devices.items()
        }
        if not device_names:
            return self.async_abort(reason="no_devices_found")
        return self.async_show_form(
            step_id="pick_device",
            data_schema=vol.Schema({vol.Required(CONF_DEVICE): vol.In(device_names)}),
        )

    @callback
    def _async_create_entry_from_device(self, device: FlowDevice) -> ConfigFlowResult:
        """Create a config entry from closed device data."""
        self._abort_if_unique_id_configured(updates={CONF_HOST: device.ip})
        return self.async_create_entry(
            title=device.label,
            data={CONF_HOST: device.ip, CONF_SERIAL: normalize_serial(device.serial)},
        )

    async def _async_try_connect(
        self, host: str | None, serial: str | None = None
    ) -> FlowDevice | None:
        """Identify and validate a supported LIFX device."""
        try:
            if host is None:
                assert serial is not None
                device = await find_by_serial(serial)
            elif serial is None:
                device = await find_by_ip(host)
            else:
                device = await Device.connect(ip=host, serial=normalize_serial(serial))
            if device is None:
                return None
        except LifxError, OSError, ValueError:
            return None

        try:
            await device.refresh_state()
            if (state := device.state) is None:
                return None
            return FlowDevice(
                ip=device.ip,
                serial=normalize_serial(device.serial),
                label=state.label,
                group=state.group.label,
            )
        except LifxError, OSError, ValueError:
            return None
        finally:
            await device.close()

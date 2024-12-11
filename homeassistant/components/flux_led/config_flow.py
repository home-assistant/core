"""Config flow for Flux LED/MagicLight."""

from __future__ import annotations

import contextlib
from typing import Any, Self, cast

from flux_led.const import (
    ATTR_ID,
    ATTR_IPADDR,
    ATTR_MODEL,
    ATTR_MODEL_DESCRIPTION,
    ATTR_MODEL_INFO,
    ATTR_VERSION_NUM,
)
from flux_led.scanner import FluxLEDDiscovery
import voluptuous as vol

from homeassistant.components import dhcp
from homeassistant.config_entries import (
    SOURCE_IGNORE,
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_DEVICE, CONF_HOST
from homeassistant.core import callback
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.typing import DiscoveryInfoType

from . import async_wifi_bulb_for_host
from .const import (
    CONF_CUSTOM_EFFECT_COLORS,
    CONF_CUSTOM_EFFECT_SPEED_PCT,
    CONF_CUSTOM_EFFECT_TRANSITION,
    DEFAULT_EFFECT_SPEED,
    DISCOVER_SCAN_TIMEOUT,
    DOMAIN,
    FLUX_LED_DISCOVERY_SIGNAL,
    FLUX_LED_EXCEPTIONS,
    TRANSITION_GRADUAL,
    TRANSITION_JUMP,
    TRANSITION_STROBE,
)
from .discovery import (
    async_discover_device,
    async_discover_devices,
    async_name_from_discovery,
    async_populate_data_from_discovery,
    async_update_entry_from_discovery,
)
from .util import format_as_flux_mac, mac_matches_by_one


class FluxLedConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Magic Home Integration."""

    VERSION = 1

    host: str | None = None

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_devices: dict[str, FluxLEDDiscovery] = {}
        self._discovered_device: FluxLEDDiscovery | None = None
        self._allow_update_mac = False

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> FluxLedOptionsFlow:
        """Get the options flow for the Flux LED component."""
        return FluxLedOptionsFlow()

    async def async_step_dhcp(
        self, discovery_info: dhcp.DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle discovery via dhcp."""
        self._discovered_device = FluxLEDDiscovery(
            ipaddr=discovery_info.ip,
            model=None,
            id=format_as_flux_mac(discovery_info.macaddress),
            model_num=None,
            version_num=None,
            firmware_date=None,
            model_info=None,
            model_description=None,
            remote_access_enabled=None,
            remote_access_host=None,
            remote_access_port=None,
        )
        return await self._async_handle_discovery()

    async def async_step_integration_discovery(
        self, discovery_info: DiscoveryInfoType
    ) -> ConfigFlowResult:
        """Handle integration discovery."""
        self._allow_update_mac = True
        self._discovered_device = cast(FluxLEDDiscovery, discovery_info)
        return await self._async_handle_discovery()

    async def _async_set_discovered_mac(
        self, device: FluxLEDDiscovery, allow_update_mac: bool
    ) -> None:
        """Set the discovered mac.

        We only allow it to be updated if it comes from udp
        discovery since the dhcp mac can be one digit off from
        the udp discovery mac for devices with multiple network interfaces
        """
        mac_address = device[ATTR_ID]
        assert mac_address is not None
        mac = dr.format_mac(mac_address)
        await self.async_set_unique_id(mac)
        for entry in self._async_current_entries(include_ignore=True):
            if not (
                entry.data.get(CONF_HOST) == device[ATTR_IPADDR]
                or (
                    entry.unique_id
                    and ":" in entry.unique_id
                    and mac_matches_by_one(entry.unique_id, mac)
                )
            ):
                continue
            if entry.source == SOURCE_IGNORE:
                raise AbortFlow("already_configured")
            if (
                async_update_entry_from_discovery(
                    self.hass, entry, device, None, allow_update_mac
                )
                and entry.state
                not in (
                    ConfigEntryState.SETUP_IN_PROGRESS,
                    ConfigEntryState.NOT_LOADED,
                )
            ) or entry.state == ConfigEntryState.SETUP_RETRY:
                self.hass.config_entries.async_schedule_reload(entry.entry_id)
            else:
                async_dispatcher_send(
                    self.hass,
                    FLUX_LED_DISCOVERY_SIGNAL.format(entry_id=entry.entry_id),
                )
            raise AbortFlow("already_configured")

    async def _async_handle_discovery(self) -> ConfigFlowResult:
        """Handle any discovery."""
        device = self._discovered_device
        assert device is not None
        await self._async_set_discovered_mac(device, self._allow_update_mac)
        host = device[ATTR_IPADDR]
        self.host = host
        if self.hass.config_entries.flow.async_has_matching_flow(self):
            return self.async_abort(reason="already_in_progress")
        if not device[ATTR_MODEL_DESCRIPTION]:
            mac_address = device[ATTR_ID]
            assert mac_address is not None
            mac = dr.format_mac(mac_address)
            try:
                device = await self._async_try_connect(host, device)
            except FLUX_LED_EXCEPTIONS:
                return self.async_abort(reason="cannot_connect")

            discovered_mac = device[ATTR_ID]
            if device[ATTR_MODEL_DESCRIPTION] or (
                discovered_mac is not None
                and (formatted_discovered_mac := dr.format_mac(discovered_mac))
                and formatted_discovered_mac != mac
                and mac_matches_by_one(discovered_mac, mac)
            ):
                self._discovered_device = device
                await self._async_set_discovered_mac(device, True)
        return await self.async_step_discovery_confirm()

    def is_matching(self, other_flow: Self) -> bool:
        """Return True if other_flow is matching this flow."""
        return other_flow.host == self.host

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        assert self._discovered_device is not None
        device = self._discovered_device
        mac_address = device[ATTR_ID]
        assert mac_address is not None
        if user_input is not None:
            return self._async_create_entry_from_device(self._discovered_device)

        self._set_confirm_only()
        placeholders = {
            "model": device[ATTR_MODEL_DESCRIPTION]
            or device[ATTR_MODEL]
            or "Magic Home",
            "id": mac_address[-6:],
            "ipaddr": device[ATTR_IPADDR],
        }
        self.context["title_placeholders"] = placeholders
        return self.async_show_form(
            step_id="discovery_confirm", description_placeholders=placeholders
        )

    @callback
    def _async_create_entry_from_device(
        self, device: FluxLEDDiscovery
    ) -> ConfigFlowResult:
        """Create a config entry from a device."""
        self._async_abort_entries_match({CONF_HOST: device[ATTR_IPADDR]})
        name = async_name_from_discovery(device)
        data: dict[str, Any] = {CONF_HOST: device[ATTR_IPADDR]}
        async_populate_data_from_discovery(data, data, device)
        return self.async_create_entry(
            title=name,
            data=data,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            if not (host := user_input[CONF_HOST]):
                return await self.async_step_pick_device()
            try:
                device = await self._async_try_connect(host, None)
            except FLUX_LED_EXCEPTIONS:
                errors["base"] = "cannot_connect"
            else:
                if (mac_address := device[ATTR_ID]) is not None:
                    await self.async_set_unique_id(
                        dr.format_mac(mac_address), raise_on_progress=False
                    )
                    self._abort_if_unique_id_configured(updates={CONF_HOST: host})
                return self._async_create_entry_from_device(device)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Optional(CONF_HOST, default=""): str}),
            errors=errors,
        )

    async def async_step_pick_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the step to pick discovered device."""
        if user_input is not None:
            mac = user_input[CONF_DEVICE]
            await self.async_set_unique_id(mac, raise_on_progress=False)
            device = self._discovered_devices[mac]
            if not device.get(ATTR_MODEL_DESCRIPTION):
                with contextlib.suppress(*FLUX_LED_EXCEPTIONS):
                    device = await self._async_try_connect(device[ATTR_IPADDR], device)
            return self._async_create_entry_from_device(device)

        current_unique_ids = self._async_current_ids()
        current_hosts = {
            entry.data[CONF_HOST]
            for entry in self._async_current_entries(include_ignore=False)
        }
        discovered_devices = await async_discover_devices(
            self.hass, DISCOVER_SCAN_TIMEOUT
        )
        self._discovered_devices = {}
        for device in discovered_devices:
            mac_address = device[ATTR_ID]
            assert mac_address is not None
            self._discovered_devices[dr.format_mac(mac_address)] = device
        devices_name = {
            mac: f"{async_name_from_discovery(device)} ({device[ATTR_IPADDR]})"
            for mac, device in self._discovered_devices.items()
            if mac not in current_unique_ids
            and device[ATTR_IPADDR] not in current_hosts
        }
        # Check if there is at least one device
        if not devices_name:
            return self.async_abort(reason="no_devices_found")
        return self.async_show_form(
            step_id="pick_device",
            data_schema=vol.Schema({vol.Required(CONF_DEVICE): vol.In(devices_name)}),
        )

    async def _async_try_connect(
        self, host: str, discovery: FluxLEDDiscovery | None
    ) -> FluxLEDDiscovery:
        """Try to connect."""
        self._async_abort_entries_match({CONF_HOST: host})
        if (device := await async_discover_device(self.hass, host)) and device[
            ATTR_MODEL_DESCRIPTION
        ]:
            # Older models do not return enough information
            # to build the model description via UDP so we have
            # to fallback to making a tcp connection to avoid
            # identifying the device as the chip model number
            # AKA `HF-LPB100-ZJ200`
            return device
        bulb = async_wifi_bulb_for_host(host, discovery=device)
        bulb.discovery = discovery
        try:
            await bulb.async_setup(lambda: None)
        finally:
            await bulb.async_stop()
        return FluxLEDDiscovery(
            ipaddr=host,
            model=discovery[ATTR_MODEL] if discovery else None,
            id=discovery[ATTR_ID] if discovery else None,
            model_num=bulb.model_num,
            version_num=discovery[ATTR_VERSION_NUM] if discovery else None,
            firmware_date=None,
            model_info=discovery[ATTR_MODEL_INFO] if discovery else None,
            model_description=bulb.model_data.description,
            remote_access_enabled=None,
            remote_access_host=None,
            remote_access_port=None,
        )


class FluxLedOptionsFlow(OptionsFlow):
    """Handle flux_led options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure the options."""
        errors: dict[str, str] = {}
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = self.config_entry.options
        options_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_CUSTOM_EFFECT_COLORS,
                    default=options.get(CONF_CUSTOM_EFFECT_COLORS, ""),
                ): str,
                vol.Optional(
                    CONF_CUSTOM_EFFECT_SPEED_PCT,
                    default=options.get(
                        CONF_CUSTOM_EFFECT_SPEED_PCT, DEFAULT_EFFECT_SPEED
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=100)),
                vol.Optional(
                    CONF_CUSTOM_EFFECT_TRANSITION,
                    default=options.get(
                        CONF_CUSTOM_EFFECT_TRANSITION, TRANSITION_GRADUAL
                    ),
                ): vol.In([TRANSITION_GRADUAL, TRANSITION_JUMP, TRANSITION_STROBE]),
            }
        )

        return self.async_show_form(
            step_id="init", data_schema=options_schema, errors=errors
        )

"""Config flow for Flux LED/MagicLight."""
from __future__ import annotations

import logging
from typing import Any, Final, cast

from flux_led.scanner import FluxLEDDiscovery
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import dhcp
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_MODE, CONF_NAME, CONF_PROTOCOL
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.typing import DiscoveryInfoType

from . import (
    async_discover_device,
    async_discover_devices,
    async_name_from_discovery,
    async_update_entry_from_discovery,
    async_wifi_bulb_for_host,
)
from .const import (
    CONF_CUSTOM_EFFECT_COLORS,
    CONF_CUSTOM_EFFECT_SPEED_PCT,
    CONF_CUSTOM_EFFECT_TRANSITION,
    DEFAULT_EFFECT_SPEED,
    DISCOVER_SCAN_TIMEOUT,
    DOMAIN,
    FLUX_LED_EXCEPTIONS,
    TRANSITION_GRADUAL,
    TRANSITION_JUMP,
    TRANSITION_STROBE,
)

CONF_DEVICE: Final = "device"


_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for FluxLED/MagicHome Integration."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_devices: dict[str, FluxLEDDiscovery] = {}
        self._discovered_device: FluxLEDDiscovery | None = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> OptionsFlow:
        """Get the options flow for the Flux LED component."""
        return OptionsFlow(config_entry)

    async def async_step_import(self, user_input: dict[str, Any]) -> FlowResult:
        """Handle configuration via YAML import."""
        _LOGGER.debug("Importing configuration from YAML for flux_led")
        host = user_input[CONF_HOST]
        self._async_abort_entries_match({CONF_HOST: host})
        if mac := user_input[CONF_MAC]:
            await self.async_set_unique_id(dr.format_mac(mac), raise_on_progress=False)
            self._abort_if_unique_id_configured(updates={CONF_HOST: host})
        return self.async_create_entry(
            title=user_input[CONF_NAME],
            data={
                CONF_HOST: host,
                CONF_NAME: user_input[CONF_NAME],
                CONF_PROTOCOL: user_input.get(CONF_PROTOCOL),
            },
            options={
                CONF_MODE: user_input[CONF_MODE],
                CONF_CUSTOM_EFFECT_COLORS: user_input[CONF_CUSTOM_EFFECT_COLORS],
                CONF_CUSTOM_EFFECT_SPEED_PCT: user_input[CONF_CUSTOM_EFFECT_SPEED_PCT],
                CONF_CUSTOM_EFFECT_TRANSITION: user_input[
                    CONF_CUSTOM_EFFECT_TRANSITION
                ],
            },
        )

    async def async_step_dhcp(self, discovery_info: dhcp.DhcpServiceInfo) -> FlowResult:
        """Handle discovery via dhcp."""
        self._discovered_device = FluxLEDDiscovery(
            ipaddr=discovery_info.ip,
            model=discovery_info.hostname,
            id=discovery_info.macaddress.replace(":", ""),
            model_num=None,
            version_num=None,
            firmware_date=None,
            model_info=None,
            model_description=None,
        )
        return await self._async_handle_discovery()

    async def async_step_discovery(
        self, discovery_info: DiscoveryInfoType
    ) -> FlowResult:
        """Handle discovery."""
        self._discovered_device = cast(FluxLEDDiscovery, discovery_info)
        return await self._async_handle_discovery()

    async def _async_handle_discovery(self) -> FlowResult:
        """Handle any discovery."""
        device = self._discovered_device
        assert device is not None
        assert device["id"] is not None
        mac = dr.format_mac(device["id"])
        host = device["ipaddr"]
        await self.async_set_unique_id(mac)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})
        for entry in self._async_current_entries(include_ignore=False):
            if entry.data[CONF_HOST] == host and not entry.unique_id:
                async_update_entry_from_discovery(self.hass, entry, device)
                return self.async_abort(reason="already_configured")
        self.context[CONF_HOST] = host
        for progress in self._async_in_progress():
            if progress.get("context", {}).get(CONF_HOST) == host:
                return self.async_abort(reason="already_in_progress")
        if not device["model_description"]:
            try:
                device = await self._async_try_connect(host)
            except FLUX_LED_EXCEPTIONS:
                return self.async_abort(reason="cannot_connect")
            else:
                if device["model_description"]:
                    self._discovered_device = device
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm discovery."""
        assert self._discovered_device is not None
        device = self._discovered_device
        assert device["id"] is not None
        if user_input is not None:
            return self._async_create_entry_from_device(self._discovered_device)

        self._set_confirm_only()
        placeholders = {
            "model": device["model_description"] or device["model"],
            "id": device["id"][-6:],
            "ipaddr": device["ipaddr"],
        }
        self.context["title_placeholders"] = placeholders
        return self.async_show_form(
            step_id="discovery_confirm", description_placeholders=placeholders
        )

    @callback
    def _async_create_entry_from_device(self, device: FluxLEDDiscovery) -> FlowResult:
        """Create a config entry from a device."""
        self._async_abort_entries_match({CONF_HOST: device["ipaddr"]})
        name = async_name_from_discovery(device)
        return self.async_create_entry(
            title=name,
            data={
                CONF_HOST: device["ipaddr"],
                CONF_NAME: name,
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            if not (host := user_input[CONF_HOST]):
                return await self.async_step_pick_device()
            try:
                device = await self._async_try_connect(host)
            except FLUX_LED_EXCEPTIONS:
                errors["base"] = "cannot_connect"
            else:
                if device["id"] is not None:
                    await self.async_set_unique_id(
                        dr.format_mac(device["id"]), raise_on_progress=False
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
    ) -> FlowResult:
        """Handle the step to pick discovered device."""
        if user_input is not None:
            mac = user_input[CONF_DEVICE]
            await self.async_set_unique_id(mac, raise_on_progress=False)
            return self._async_create_entry_from_device(self._discovered_devices[mac])

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
            assert device["id"] is not None
            self._discovered_devices[dr.format_mac(device["id"])] = device
        devices_name = {
            mac: f"{async_name_from_discovery(device)} ({device['ipaddr']})"
            for mac, device in self._discovered_devices.items()
            if mac not in current_unique_ids and device["ipaddr"] not in current_hosts
        }
        # Check if there is at least one device
        if not devices_name:
            return self.async_abort(reason="no_devices_found")
        return self.async_show_form(
            step_id="pick_device",
            data_schema=vol.Schema({vol.Required(CONF_DEVICE): vol.In(devices_name)}),
        )

    async def _async_try_connect(self, host: str) -> FluxLEDDiscovery:
        """Try to connect."""
        self._async_abort_entries_match({CONF_HOST: host})
        if device := await async_discover_device(self.hass, host):
            return device
        bulb = async_wifi_bulb_for_host(host)
        try:
            await bulb.async_setup(lambda: None)
        finally:
            await bulb.async_stop()
        return FluxLEDDiscovery(
            ipaddr=host,
            model=None,
            id=None,
            model_num=None,
            version_num=None,
            firmware_date=None,
            model_info=None,
            model_description=None,
        )


class OptionsFlow(config_entries.OptionsFlow):
    """Handle flux_led options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize the flux_led options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure the options."""
        errors: dict[str, str] = {}
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = self._config_entry.options
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

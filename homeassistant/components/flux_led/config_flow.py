"""Config flow for Flux LED/MagicLight."""
from __future__ import annotations

import copy
import logging
from typing import Any

from flux_led import WifiLedBulb
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.dhcp import HOSTNAME, IP_ADDRESS, MAC_ADDRESS
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_MODE, CONF_NAME, CONF_PROTOCOL
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.typing import DiscoveryInfoType

from . import async_discover_devices
from .const import (
    CONF_AUTOMATIC_ADD,
    CONF_CONFIGURE_DEVICE,
    CONF_CUSTOM_EFFECT,
    CONF_DEVICES,
    CONF_EFFECT_SPEED,
    CONF_REMOVE_DEVICE,
    DEFAULT_EFFECT_SPEED,
    DOMAIN,
    FLUX_HOST,
    FLUX_MAC,
    FLUX_MODEL,
    SIGNAL_ADD_DEVICE,
    SIGNAL_REMOVE_DEVICE,
)

CONF_DEVICE = "device"

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for FluxLED/MagicHome Integration."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_device: dict[str, Any] = {}
        self._discovered_devices: list[dict[str, Any]] = []

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Get the options flow for the Flux LED component."""
        return OptionsFlow(config_entry)

    async def async_step_import(self, user_input: dict[str, Any]) -> FlowResult:
        """Handle configuration via YAML import."""
        _LOGGER.debug("Importing configuration from YAML for flux_led")
        host = user_input[CONF_HOST]
        self._async_abort_entries_match({CONF_HOST: host})
        if mac := user_input[CONF_MAC]:
            await self.async_set_unique_id(dr.format_mac(mac))
            self._abort_if_unique_id_configured(updates={CONF_HOST: host})
        return self.async_create_entry(
            title=user_input[CONF_NAME],
            data={
                CONF_HOST: host,
                CONF_NAME: user_input[CONF_NAME],
                CONF_PROTOCOL: user_input.get(CONF_PROTOCOL),
            },
            options={
                CONF_CUSTOM_EFFECT: user_input[CONF_CUSTOM_EFFECT],
                CONF_MODE: user_input[CONF_MODE],
            },
        )

    async def async_step_dhcp(self, discovery_info: DiscoveryInfoType) -> FlowResult:
        """Handle discovery via dhcp."""
        self._discovered_device = {
            FLUX_HOST: discovery_info[IP_ADDRESS],
            FLUX_MODEL: discovery_info[HOSTNAME],
            FLUX_MAC: discovery_info[MAC_ADDRESS],
        }
        return await self._async_handle_discovery()

    async def async_step_discovery(
        self, discovery_info: DiscoveryInfoType
    ) -> FlowResult:
        """Handle discovery."""
        self._discovered_device = discovery_info
        return await self._async_handle_discovery()

    async def _async_handle_discovery(self) -> FlowResult:
        """Handle any discovery."""
        mac = self._discovered_device[FLUX_MAC]
        host = self._discovered_device[FLUX_HOST]
        await self.async_set_unique_id(dr.format_mac(mac))
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})
        self._async_abort_entries_match({CONF_HOST: host})
        self.context[CONF_HOST] = host
        for progress in self._async_in_progress():
            if progress.get("context", {}).get(CONF_HOST) == host:
                return self.async_abort(reason="already_in_progress")
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm discovery."""
        if user_input is not None:
            return self._async_create_entry_from_device(self._discovered_device)

        self._set_confirm_only()
        placeholders = self._discovered_device
        self.context["title_placeholders"] = placeholders
        return self.async_show_form(
            step_id="discovery_confirm", description_placeholders=placeholders
        )

    @callback
    def _async_create_entry_from_device(self, device: dict[str, Any]) -> FlowResult:
        """Create a config entry from a device."""
        device = self._discovered_device
        return self.async_create_entry(
            title=f"{device[FLUX_MODEL]} {device[FLUX_MAC]}",
            data={
                CONF_HOST: device[FLUX_HOST],
                CONF_NAME: f"{device[FLUX_MODEL]} {device[FLUX_MAC]}",
            },
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
            try:
                await self._async_try_connect(host)
            except BrokenPipeError:
                errors["base"] = "cannot_connect"
            else:
                return self._async_create_entry_from_device(
                    {FLUX_MAC: None, FLUX_MODEL: None, FLUX_HOST: host}
                )

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
        self._discovered_devices = await async_discover_devices(self.hass)
        devices_name = {
            dr.format_mac(
                device[FLUX_MAC]
            ): f"{device[FLUX_MODEL]} {device[FLUX_MAC]} ({device[FLUX_HOST]}"
            for device in self._discovered_devices
            if dr.format_mac(device[FLUX_MAC]) not in current_unique_ids
            and device[FLUX_HOST] not in current_hosts
        }
        # Check if there is at least one device
        if not devices_name:
            return self.async_abort(reason="no_devices_found")
        return self.async_show_form(
            step_id="pick_device",
            data_schema=vol.Schema({vol.Required(CONF_DEVICE): vol.In(devices_name)}),
        )

    async def _async_try_connect(self, host: str) -> WifiLedBulb:
        """Try to connect."""
        self._async_abort_entries_match({CONF_HOST: host})
        return await self.hass.async_add_executor_job(WifiLedBulb, host)


class OptionsFlow(config_entries.OptionsFlow):
    """Handle flux_led options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize the flux_led options flow."""

        self._config_entry = config_entry
        self._global_options = None
        self._configure_device = None

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        return await self.async_step_prompt_options()

    async def async_step_prompt_options(self, user_input=None):
        """Manage the options."""

        errors = {}

        if user_input is not None:
            self._global_options = {
                CONF_AUTOMATIC_ADD: user_input[CONF_AUTOMATIC_ADD],
                CONF_EFFECT_SPEED: user_input[CONF_EFFECT_SPEED],
            }

            if CONF_CONFIGURE_DEVICE in user_input:
                self._configure_device = user_input[CONF_CONFIGURE_DEVICE]
                return await self.async_step_configure_device()

            if CONF_REMOVE_DEVICE in user_input:
                device_id = user_input[CONF_REMOVE_DEVICE]
                config_data = copy.deepcopy(dict(self._config_entry.data))
                del config_data[CONF_DEVICES][device_id]

                self.hass.config_entries.async_update_entry(
                    self._config_entry, data=config_data
                )

                async_dispatcher_send(
                    self.hass, SIGNAL_REMOVE_DEVICE, {"device_id": device_id}
                )

                options_data = self._config_entry.options.copy()
                if device_id in options_data:
                    del options_data[device_id]
                options_data["global"] = self._global_options

                return self.async_create_entry(title="", data=options_data)

            if CONF_HOST in user_input:
                device_name = (
                    user_input[CONF_NAME]
                    if CONF_NAME in user_input
                    else user_input[CONF_HOST]
                )
                device_id = user_input[CONF_HOST].replace(".", "_")
                device_data = {
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_NAME: device_name,
                }
                config_data = copy.deepcopy(dict(self._config_entry.data))
                config_data[CONF_DEVICES][device_id] = device_data

                self.hass.config_entries.async_update_entry(
                    self._config_entry, data=config_data
                )

                async_dispatcher_send(
                    self.hass, SIGNAL_ADD_DEVICE, {device_id: device_data}
                )

            options_data = self._config_entry.options.copy()
            options_data["global"] = self._global_options
            return self.async_create_entry(title="", data=options_data)

        existing_devices = {}

        for device_id, device in self._config_entry.data[CONF_DEVICES].items():
            existing_devices[device_id] = device.get(CONF_NAME, device[CONF_HOST])

        options = {
            vol.Optional(
                CONF_AUTOMATIC_ADD,
                default=self._config_entry.options.get("global", {}).get(
                    CONF_AUTOMATIC_ADD, self._config_entry.data[CONF_AUTOMATIC_ADD]
                ),
            ): bool,
            vol.Optional(
                CONF_EFFECT_SPEED,
                default=self._config_entry.options.get("global", {}).get(
                    CONF_EFFECT_SPEED, DEFAULT_EFFECT_SPEED
                ),
            ): vol.All(
                vol.Coerce(int),
                vol.Range(min=1, max=100),
            ),
            vol.Optional(CONF_HOST): str,
            vol.Optional(CONF_NAME): str,
            vol.Optional(CONF_CONFIGURE_DEVICE): vol.In(existing_devices),
            vol.Optional(CONF_REMOVE_DEVICE): vol.In(existing_devices),
        }

        return self.async_show_form(
            step_id="prompt_options", data_schema=vol.Schema(options), errors=errors
        )

    async def async_step_configure_device(self, user_input=None):
        """Manage the options."""

        errors = {}

        if user_input is not None:
            options_data = self._config_entry.options.copy()
            options_data[self._configure_device] = {
                CONF_EFFECT_SPEED: user_input[CONF_EFFECT_SPEED]
            }
            options_data["global"] = self._global_options
            return self.async_create_entry(title="", data=options_data)

        options = {
            vol.Required(
                CONF_EFFECT_SPEED,
                default=self._config_entry.options.get(self._configure_device, {}).get(
                    CONF_EFFECT_SPEED, DEFAULT_EFFECT_SPEED
                ),
            ): vol.All(
                vol.Coerce(int),
                vol.Range(min=1, max=100),
            )
        }

        return self.async_show_form(
            step_id="configure_device", data_schema=vol.Schema(options), errors=errors
        )

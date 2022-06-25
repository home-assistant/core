"""Config flow for Yeelight integration."""
from __future__ import annotations

import asyncio
import logging
from urllib.parse import urlparse

import voluptuous as vol
import yeelight
from yeelight.aio import AsyncBulb
from yeelight.main import get_known_models

from homeassistant import config_entries, exceptions
from homeassistant.components import dhcp, onboarding, ssdp, zeroconf
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_ID, CONF_MODEL, CONF_NAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_DETECTED_MODEL,
    CONF_MODE_MUSIC,
    CONF_NIGHTLIGHT_SWITCH,
    CONF_NIGHTLIGHT_SWITCH_TYPE,
    CONF_SAVE_ON_CHANGE,
    CONF_TRANSITION,
    DOMAIN,
    NIGHTLIGHT_SWITCH_TYPE_LIGHT,
)
from .device import (
    _async_unique_name,
    async_format_id,
    async_format_model,
    async_format_model_id,
)
from .scanner import YeelightScanner

MODEL_UNKNOWN = "unknown"

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Yeelight."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlowHandler:
        """Return the options flow."""
        return OptionsFlowHandler(config_entry)

    def __init__(self):
        """Initialize the config flow."""
        self._discovered_devices = {}
        self._discovered_model = None
        self._discovered_ip = None

    async def async_step_homekit(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle discovery from homekit."""
        self._discovered_ip = discovery_info.host
        return await self._async_handle_discovery()

    async def async_step_dhcp(self, discovery_info: dhcp.DhcpServiceInfo) -> FlowResult:
        """Handle discovery from dhcp."""
        self._discovered_ip = discovery_info.ip
        return await self._async_handle_discovery()

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle discovery from zeroconf."""
        self._discovered_ip = discovery_info.host
        await self.async_set_unique_id(
            "{0:#0{1}x}".format(int(discovery_info.name[-26:-18]), 18)
        )
        return await self._async_handle_discovery_with_unique_id()

    async def async_step_ssdp(self, discovery_info: ssdp.SsdpServiceInfo) -> FlowResult:
        """Handle discovery from ssdp."""
        self._discovered_ip = urlparse(discovery_info.ssdp_headers["location"]).hostname
        await self.async_set_unique_id(discovery_info.ssdp_headers["id"])
        return await self._async_handle_discovery_with_unique_id()

    async def _async_handle_discovery_with_unique_id(self):
        """Handle any discovery with a unique id."""
        for entry in self._async_current_entries(include_ignore=False):
            if entry.unique_id != self.unique_id and self.unique_id != entry.data.get(
                CONF_ID
            ):
                continue
            reload = entry.state == ConfigEntryState.SETUP_RETRY
            if entry.data.get(CONF_HOST) != self._discovered_ip:
                self.hass.config_entries.async_update_entry(
                    entry, data={**entry.data, CONF_HOST: self._discovered_ip}
                )
                reload = entry.state in (
                    ConfigEntryState.SETUP_RETRY,
                    ConfigEntryState.LOADED,
                )
            if reload:
                self.hass.async_create_task(
                    self.hass.config_entries.async_reload(entry.entry_id)
                )
            return self.async_abort(reason="already_configured")
        return await self._async_handle_discovery()

    async def _async_handle_discovery(self):
        """Handle any discovery."""
        self.context[CONF_HOST] = self._discovered_ip
        for progress in self._async_in_progress():
            if progress.get("context", {}).get(CONF_HOST) == self._discovered_ip:
                return self.async_abort(reason="already_in_progress")
        self._async_abort_entries_match({CONF_HOST: self._discovered_ip})

        try:
            self._discovered_model = await self._async_try_connect(
                self._discovered_ip, raise_on_progress=True
            )
        except CannotConnect:
            return self.async_abort(reason="cannot_connect")

        if not self.unique_id:
            return self.async_abort(reason="cannot_connect")

        self._abort_if_unique_id_configured(
            updates={CONF_HOST: self._discovered_ip}, reload_on_update=False
        )
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(self, user_input=None):
        """Confirm discovery."""
        if user_input is not None or not onboarding.async_is_onboarded(self.hass):
            return self.async_create_entry(
                title=async_format_model_id(self._discovered_model, self.unique_id),
                data={
                    CONF_ID: self.unique_id,
                    CONF_HOST: self._discovered_ip,
                    CONF_MODEL: self._discovered_model,
                },
            )

        self._set_confirm_only()
        placeholders = {
            "id": async_format_id(self.unique_id),
            "model": async_format_model(self._discovered_model),
            "host": self._discovered_ip,
        }
        self.context["title_placeholders"] = placeholders
        return self.async_show_form(
            step_id="discovery_confirm", description_placeholders=placeholders
        )

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            if not user_input.get(CONF_HOST):
                return await self.async_step_pick_device()
            try:
                model = await self._async_try_connect(
                    user_input[CONF_HOST], raise_on_progress=False
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            else:
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=async_format_model_id(model, self.unique_id),
                    data={
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_ID: self.unique_id,
                        CONF_MODEL: model,
                    },
                )

        user_input = user_input or {}
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Optional(CONF_HOST, default=user_input.get(CONF_HOST, "")): str}
            ),
            errors=errors,
        )

    async def async_step_pick_device(self, user_input=None):
        """Handle the step to pick discovered device."""
        if user_input is not None:
            unique_id = user_input[CONF_DEVICE]
            capabilities = self._discovered_devices[unique_id]
            await self.async_set_unique_id(unique_id, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            host = urlparse(capabilities["location"]).hostname
            return self.async_create_entry(
                title=_async_unique_name(capabilities),
                data={
                    CONF_ID: unique_id,
                    CONF_HOST: host,
                    CONF_MODEL: capabilities["model"],
                },
            )

        configured_devices = {
            entry.data[CONF_ID]
            for entry in self._async_current_entries()
            if entry.data[CONF_ID]
        }
        devices_name = {}
        scanner = YeelightScanner.async_get(self.hass)
        devices = await scanner.async_discover()
        # Run 3 times as packets can get lost
        for capabilities in devices:
            unique_id = capabilities["id"]
            if unique_id in configured_devices:
                continue  # ignore configured devices
            model = capabilities["model"]
            host = urlparse(capabilities["location"]).hostname
            model_id = async_format_model_id(model, unique_id)
            name = f"{model_id} ({host})"
            self._discovered_devices[unique_id] = capabilities
            devices_name[unique_id] = name

        # Check if there is at least one device
        if not devices_name:
            return self.async_abort(reason="no_devices_found")
        return self.async_show_form(
            step_id="pick_device",
            data_schema=vol.Schema({vol.Required(CONF_DEVICE): vol.In(devices_name)}),
        )

    async def async_step_import(self, user_input=None):
        """Handle import step."""
        host = user_input[CONF_HOST]
        try:
            await self._async_try_connect(host, raise_on_progress=False)
        except CannotConnect:
            _LOGGER.error("Failed to import %s: cannot connect", host)
            return self.async_abort(reason="cannot_connect")
        if CONF_NIGHTLIGHT_SWITCH_TYPE in user_input:
            user_input[CONF_NIGHTLIGHT_SWITCH] = (
                user_input.pop(CONF_NIGHTLIGHT_SWITCH_TYPE)
                == NIGHTLIGHT_SWITCH_TYPE_LIGHT
            )
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

    async def _async_try_connect(self, host, raise_on_progress=True):
        """Set up with options."""
        self._async_abort_entries_match({CONF_HOST: host})

        scanner = YeelightScanner.async_get(self.hass)
        capabilities = await scanner.async_get_capabilities(host)
        if capabilities is None:  # timeout
            _LOGGER.debug("Failed to get capabilities from %s: timeout", host)
        else:
            _LOGGER.debug("Get capabilities: %s", capabilities)
            await self.async_set_unique_id(
                capabilities["id"], raise_on_progress=raise_on_progress
            )
            return capabilities["model"]
        # Fallback to get properties
        bulb = AsyncBulb(host)
        try:
            await bulb.async_listen(lambda _: True)
            await bulb.async_get_properties()
            await bulb.async_stop_listening()
        except (asyncio.TimeoutError, yeelight.BulbException) as err:
            _LOGGER.error("Failed to get properties from %s: %s", host, err)
            raise CannotConnect from err
        _LOGGER.debug("Get properties: %s", bulb.last_properties)
        return MODEL_UNKNOWN


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option flow for Yeelight."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize the option flow."""
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Handle the initial step."""
        data = self._config_entry.data
        options = self._config_entry.options
        detected_model = data.get(CONF_DETECTED_MODEL)
        model = options[CONF_MODEL] or detected_model

        if user_input is not None:
            return self.async_create_entry(
                title="", data={CONF_MODEL: model, **options, **user_input}
            )

        schema_dict = {}
        known_models = get_known_models()
        if is_unknown_model := model not in known_models:
            known_models.insert(0, model)

        if is_unknown_model or model != detected_model:
            schema_dict.update(
                {
                    vol.Optional(CONF_MODEL, default=model): vol.In(known_models),
                }
            )
        schema_dict.update(
            {
                vol.Required(
                    CONF_TRANSITION, default=options[CONF_TRANSITION]
                ): cv.positive_int,
                vol.Required(CONF_MODE_MUSIC, default=options[CONF_MODE_MUSIC]): bool,
                vol.Required(
                    CONF_SAVE_ON_CHANGE, default=options[CONF_SAVE_ON_CHANGE]
                ): bool,
                vol.Required(
                    CONF_NIGHTLIGHT_SWITCH, default=options[CONF_NIGHTLIGHT_SWITCH]
                ): bool,
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema_dict),
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""

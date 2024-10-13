"""Test config flow for Insteon."""

from __future__ import annotations

import logging
from typing import Any

from pyinsteon import async_connect

from homeassistant.components import dhcp, usb
from homeassistant.config_entries import (
    DEFAULT_DISCOVERY_UNIQUE_ID,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_NAME
from homeassistant.helpers.device_registry import format_mac

from .const import CONF_HUB_VERSION, DOMAIN
from .schemas import build_hub_schema, build_plm_manual_schema, build_plm_schema
from .utils import async_get_usb_ports

STEP_PLM = "plm"
STEP_PLM_MANUALLY = "plm_manually"
STEP_HUB_V1 = "hubv1"
STEP_HUB_V2 = "hubv2"
STEP_CHANGE_HUB_CONFIG = "change_hub_config"
STEP_CHANGE_PLM_CONFIG = "change_plm_config"
STEP_ADD_X10 = "add_x10"
STEP_ADD_OVERRIDE = "add_override"
STEP_REMOVE_OVERRIDE = "remove_override"
STEP_REMOVE_X10 = "remove_x10"
MODEM_TYPE = "modem_type"
PLM_MANUAL = "manual"

_LOGGER = logging.getLogger(__name__)


async def _async_connect(**kwargs):
    """Connect to the Insteon modem."""
    try:
        await async_connect(**kwargs)
    except ConnectionError:
        _LOGGER.error("Could not connect to Insteon modem")
        return False

    _LOGGER.debug("Connected to Insteon modem")
    return True


class InsteonFlowHandler(ConfigFlow, domain=DOMAIN):
    """Insteon config flow handler."""

    _device_path: str
    _device_name: str
    discovered_conf: dict[str, str] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Init the config flow."""
        modem_types = [STEP_PLM, STEP_HUB_V1, STEP_HUB_V2]
        return self.async_show_menu(step_id="user", menu_options=modem_types)

    async def async_step_plm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set up the PLM modem type."""
        errors = {}
        if user_input is not None:
            if user_input[CONF_DEVICE] == PLM_MANUAL:
                return await self.async_step_plm_manually()
            if await _async_connect(**user_input):
                return self.async_create_entry(title="", data=user_input)
            errors["base"] = "cannot_connect"
        schema_defaults = user_input if user_input is not None else {}
        ports = await async_get_usb_ports(self.hass)
        if not ports:
            return await self.async_step_plm_manually()
        ports[PLM_MANUAL] = "Enter manually"
        data_schema = build_plm_schema(ports, **schema_defaults)
        return self.async_show_form(
            step_id=STEP_PLM, data_schema=data_schema, errors=errors
        )

    async def async_step_plm_manually(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set up the PLM modem type manually."""
        errors = {}
        schema_defaults = {}
        if user_input is not None:
            if await _async_connect(**user_input):
                return self.async_create_entry(title="", data=user_input)
            errors["base"] = "cannot_connect"
            schema_defaults = user_input
        data_schema = build_plm_manual_schema(**schema_defaults)
        return self.async_show_form(
            step_id=STEP_PLM_MANUALLY, data_schema=data_schema, errors=errors
        )

    async def async_step_hubv1(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set up the Hub v1 modem type."""
        return await self._async_setup_hub(hub_version=1, user_input=user_input)

    async def async_step_hubv2(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set up the Hub v2 modem type."""
        return await self._async_setup_hub(hub_version=2, user_input=user_input)

    async def _async_setup_hub(
        self, hub_version: int, user_input: dict[str, Any] | None
    ) -> ConfigFlowResult:
        """Set up the Hub versions 1 and 2."""
        errors = {}
        if user_input is not None:
            user_input[CONF_HUB_VERSION] = hub_version
            if await _async_connect(**user_input):
                return self.async_create_entry(title="", data=user_input)
            user_input.pop(CONF_HUB_VERSION)
            errors["base"] = "cannot_connect"
        schema_defaults = user_input if user_input is not None else self.discovered_conf
        data_schema = build_hub_schema(hub_version=hub_version, **schema_defaults)
        step_id = STEP_HUB_V2 if hub_version == 2 else STEP_HUB_V1
        return self.async_show_form(
            step_id=step_id, data_schema=data_schema, errors=errors
        )

    async def async_step_usb(
        self, discovery_info: usb.UsbServiceInfo
    ) -> ConfigFlowResult:
        """Handle USB discovery."""
        self._device_path = discovery_info.device
        self._device_name = usb.human_readable_device_name(
            discovery_info.device,
            discovery_info.serial_number,
            discovery_info.manufacturer,
            discovery_info.description,
            discovery_info.vid,
            discovery_info.pid,
        )
        self._set_confirm_only()
        self.context["title_placeholders"] = {
            CONF_NAME: f"Insteon PLM {self._device_name}"
        }
        await self.async_set_unique_id(DEFAULT_DISCOVERY_UNIQUE_ID)
        return await self.async_step_confirm_usb()

    async def async_step_confirm_usb(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm a USB discovery."""
        if user_input is not None:
            return await self.async_step_plm({CONF_DEVICE: self._device_path})

        return self.async_show_form(
            step_id="confirm_usb",
            description_placeholders={CONF_NAME: self._device_name},
        )

    async def async_step_dhcp(
        self, discovery_info: dhcp.DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle a DHCP discovery."""
        self.discovered_conf = {CONF_HOST: discovery_info.ip}
        self.context["title_placeholders"] = {
            CONF_NAME: f"Insteon Hub {discovery_info.ip}"
        }
        await self.async_set_unique_id(format_mac(discovery_info.macaddress))
        return await self.async_step_user()

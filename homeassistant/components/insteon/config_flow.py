"""Test config flow for Insteon."""
from __future__ import annotations

import logging

from pyinsteon import async_close, async_connect, devices

from homeassistant import config_entries
from homeassistant.components import dhcp, usb
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_DEVICE,
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    CONF_HOUSECODE,
    CONF_HUB_VERSION,
    CONF_OVERRIDE,
    CONF_UNITCODE,
    CONF_X10,
    DOMAIN,
    SIGNAL_ADD_DEVICE_OVERRIDE,
    SIGNAL_ADD_X10_DEVICE,
    SIGNAL_REMOVE_DEVICE_OVERRIDE,
    SIGNAL_REMOVE_X10_DEVICE,
)
from .schemas import (
    add_device_override,
    add_x10_device,
    build_device_override_schema,
    build_hub_schema,
    build_plm_schema,
    build_remove_override_schema,
    build_remove_x10_schema,
    build_x10_schema,
)
from .utils import async_get_usb_ports

STEP_PLM = "plm"
STEP_HUB_V1 = "hubv1"
STEP_HUB_V2 = "hubv2"
STEP_CHANGE_HUB_CONFIG = "change_hub_config"
STEP_CHANGE_PLM_CONFIG = "change_plm_config"
STEP_ADD_X10 = "add_x10"
STEP_ADD_OVERRIDE = "add_override"
STEP_REMOVE_OVERRIDE = "remove_override"
STEP_REMOVE_X10 = "remove_x10"
MODEM_TYPE = "modem_type"

_LOGGER = logging.getLogger(__name__)


async def _async_connect(**kwargs):
    """Connect to the Insteon modem."""
    try:
        await async_connect(**kwargs)
        _LOGGER.info("Connected to Insteon modem")
        return True
    except ConnectionError:
        _LOGGER.error("Could not connect to Insteon modem")
        return False


def _remove_override(address, options):
    """Remove a device override from config."""
    new_options = {}
    if options.get(CONF_X10):
        new_options[CONF_X10] = options.get(CONF_X10)
    new_overrides = []
    for override in options[CONF_OVERRIDE]:
        if override[CONF_ADDRESS] != address:
            new_overrides.append(override)
    if new_overrides:
        new_options[CONF_OVERRIDE] = new_overrides
    return new_options


def _remove_x10(device, options):
    """Remove an X10 device from the config."""
    housecode = device[11].lower()
    unitcode = int(device[24:])
    new_options = {}
    if options.get(CONF_OVERRIDE):
        new_options[CONF_OVERRIDE] = options.get(CONF_OVERRIDE)
    new_x10 = []
    for existing_device in options[CONF_X10]:
        if (
            existing_device[CONF_HOUSECODE].lower() != housecode
            or existing_device[CONF_UNITCODE] != unitcode
        ):
            new_x10.append(existing_device)
    if new_x10:
        new_options[CONF_X10] = new_x10
    return new_options, housecode, unitcode


class InsteonFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Insteon config flow handler."""

    _device_path: str | None = None
    _device_name: str | None = None
    discovered_conf: dict[str, str] = {}

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> InsteonOptionsFlowHandler:
        """Define the config flow to handle options."""
        return InsteonOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """Init the config flow."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        modem_types = [STEP_PLM, STEP_HUB_V1, STEP_HUB_V2]
        return self.async_show_menu(step_id="user", menu_options=modem_types)

    async def async_step_plm(self, user_input=None):
        """Set up the PLM modem type."""
        errors = {}
        if user_input is not None:
            if await _async_connect(**user_input):
                return self.async_create_entry(title="", data=user_input)
            errors["base"] = "cannot_connect"
        schema_defaults = user_input if user_input is not None else {}
        ports = await async_get_usb_ports(self.hass)
        data_schema = build_plm_schema(ports, **schema_defaults)
        return self.async_show_form(
            step_id=STEP_PLM, data_schema=data_schema, errors=errors
        )

    async def async_step_hubv1(self, user_input=None):
        """Set up the Hub v1 modem type."""
        return await self._async_setup_hub(hub_version=1, user_input=user_input)

    async def async_step_hubv2(self, user_input=None):
        """Set up the Hub v2 modem type."""
        return await self._async_setup_hub(hub_version=2, user_input=user_input)

    async def _async_setup_hub(self, hub_version, user_input):
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

    async def async_step_usb(self, discovery_info: usb.UsbServiceInfo) -> FlowResult:
        """Handle USB discovery."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

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
        await self.async_set_unique_id(config_entries.DEFAULT_DISCOVERY_UNIQUE_ID)
        return await self.async_step_confirm_usb()

    async def async_step_confirm_usb(self, user_input=None) -> FlowResult:
        """Confirm a USB discovery."""
        if user_input is not None:
            return await self.async_step_plm({CONF_DEVICE: self._device_path})

        return self.async_show_form(
            step_id="confirm_usb",
            description_placeholders={CONF_NAME: self._device_name},
        )

    async def async_step_dhcp(self, discovery_info: dhcp.DhcpServiceInfo) -> FlowResult:
        """Handle a DHCP discovery."""
        self.discovered_conf = {CONF_HOST: discovery_info.ip}
        self.context["title_placeholders"] = {
            CONF_NAME: f"Insteon Hub {discovery_info.ip}"
        }
        await self.async_set_unique_id(format_mac(discovery_info.macaddress))
        return await self.async_step_user()


class InsteonOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle an Insteon options flow."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Init the InsteonOptionsFlowHandler class."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None) -> FlowResult:
        """Init the options config flow."""
        menu_options = [STEP_ADD_OVERRIDE, STEP_ADD_X10]

        if self.config_entry.data.get(CONF_HOST):
            menu_options.append(STEP_CHANGE_HUB_CONFIG)
        else:
            menu_options.append(STEP_CHANGE_PLM_CONFIG)

        options = {**self.config_entry.options}
        if options.get(CONF_OVERRIDE):
            menu_options.append(STEP_REMOVE_OVERRIDE)
        if options.get(CONF_X10):
            menu_options.append(STEP_REMOVE_X10)

        return self.async_show_menu(step_id="init", menu_options=menu_options)

    async def async_step_change_hub_config(self, user_input=None) -> FlowResult:
        """Change the Hub configuration."""
        errors = {}
        if user_input is not None:
            data = {
                **self.config_entry.data,
                CONF_HOST: user_input[CONF_HOST],
                CONF_PORT: user_input[CONF_PORT],
            }
            if self.config_entry.data[CONF_HUB_VERSION] == 2:
                data[CONF_USERNAME] = user_input[CONF_USERNAME]
                data[CONF_PASSWORD] = user_input[CONF_PASSWORD]
            if devices.modem:
                await async_close()

            if await _async_connect(**data):
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=data
                )
                return self.async_create_entry(data={**self.config_entry.options})
            errors["base"] = "cannot_connect"
        data_schema = build_hub_schema(**self.config_entry.data)
        return self.async_show_form(
            step_id=STEP_CHANGE_HUB_CONFIG, data_schema=data_schema, errors=errors
        )

    async def async_step_change_plm_config(self, user_input=None) -> FlowResult:
        """Change the PLM configuration."""
        errors = {}
        if user_input is not None:
            data = {
                **self.config_entry.data,
                CONF_DEVICE: user_input[CONF_DEVICE],
            }
            if devices.modem:
                await async_close()
            if await _async_connect(**data):
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=data
                )
                return self.async_create_entry(data={**self.config_entry.options})
            errors["base"] = "cannot_connect"

        ports = await async_get_usb_ports(self.hass)
        data_schema = build_plm_schema(ports, **self.config_entry.data)
        return self.async_show_form(
            step_id=STEP_CHANGE_PLM_CONFIG, data_schema=data_schema, errors=errors
        )

    async def async_step_add_override(self, user_input=None) -> FlowResult:
        """Add a device override."""
        errors = {}
        if user_input is not None:
            try:
                data = add_device_override({**self.config_entry.options}, user_input)
                async_dispatcher_send(self.hass, SIGNAL_ADD_DEVICE_OVERRIDE, user_input)
                return self.async_create_entry(data=data)
            except ValueError:
                errors["base"] = "input_error"
        schema_defaults = user_input if user_input is not None else {}
        data_schema = build_device_override_schema(**schema_defaults)
        return self.async_show_form(
            step_id=STEP_ADD_OVERRIDE, data_schema=data_schema, errors=errors
        )

    async def async_step_add_x10(self, user_input=None) -> FlowResult:
        """Add an X10 device."""
        errors: dict[str, str] = {}
        if user_input is not None:
            options = add_x10_device({**self.config_entry.options}, user_input)
            async_dispatcher_send(self.hass, SIGNAL_ADD_X10_DEVICE, user_input)
            return self.async_create_entry(data=options)
        schema_defaults: dict[str, str] = user_input if user_input is not None else {}
        data_schema = build_x10_schema(**schema_defaults)
        return self.async_show_form(
            step_id=STEP_ADD_X10, data_schema=data_schema, errors=errors
        )

    async def async_step_remove_override(self, user_input=None) -> FlowResult:
        """Remove a device override."""
        errors: dict[str, str] = {}
        options = self.config_entry.options
        if user_input is not None:
            options = _remove_override(user_input[CONF_ADDRESS], options)
            async_dispatcher_send(
                self.hass,
                SIGNAL_REMOVE_DEVICE_OVERRIDE,
                user_input[CONF_ADDRESS],
            )
            return self.async_create_entry(data=options)

        data_schema = build_remove_override_schema(options[CONF_OVERRIDE])
        return self.async_show_form(
            step_id=STEP_REMOVE_OVERRIDE, data_schema=data_schema, errors=errors
        )

    async def async_step_remove_x10(self, user_input=None) -> FlowResult:
        """Remove an X10 device."""
        errors: dict[str, str] = {}
        options = self.config_entry.options
        if user_input is not None:
            options, housecode, unitcode = _remove_x10(user_input[CONF_DEVICE], options)
            async_dispatcher_send(
                self.hass, SIGNAL_REMOVE_X10_DEVICE, housecode, unitcode
            )
            return self.async_create_entry(data=options)

        data_schema = build_remove_x10_schema(options[CONF_X10])
        return self.async_show_form(
            step_id=STEP_REMOVE_X10, data_schema=data_schema, errors=errors
        )

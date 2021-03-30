"""Test config flow for Insteon."""
import logging

from pyinsteon import async_connect
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_DEVICE,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import callback
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

STEP_PLM = "plm"
STEP_HUB_V1 = "hubv1"
STEP_HUB_V2 = "hubv2"
STEP_CHANGE_HUB_CONFIG = "change_hub_config"
STEP_ADD_X10 = "add_x10"
STEP_ADD_OVERRIDE = "add_override"
STEP_REMOVE_OVERRIDE = "remove_override"
STEP_REMOVE_X10 = "remove_x10"
MODEM_TYPE = "modem_type"
PLM = "PowerLinc Modem (PLM)"
HUB1 = "Hub version 1 (pre-2014)"
HUB2 = "Hub version 2"

_LOGGER = logging.getLogger(__name__)


def _only_one_selected(*args):
    """Test if only one item is True."""
    return sum(args) == 1


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

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Define the config flow to handle options."""
        return InsteonOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """Init the config flow."""
        errors = {}
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is not None:
            selection = user_input.get(MODEM_TYPE)

            if selection == PLM:
                return await self.async_step_plm()
            if selection == HUB1:
                return await self.async_step_hubv1()
            return await self.async_step_hubv2()
        modem_types = [PLM, HUB1, HUB2]
        data_schema = vol.Schema({vol.Required(MODEM_TYPE): vol.In(modem_types)})
        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def async_step_plm(self, user_input=None):
        """Set up the PLM modem type."""
        errors = {}
        if user_input is not None:
            if await _async_connect(**user_input):
                return self.async_create_entry(title="", data=user_input)
            errors["base"] = "cannot_connect"
        schema_defaults = user_input if user_input is not None else {}
        data_schema = build_plm_schema(**schema_defaults)
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
        schema_defaults = user_input if user_input is not None else {}
        data_schema = build_hub_schema(hub_version=hub_version, **schema_defaults)
        step_id = STEP_HUB_V2 if hub_version == 2 else STEP_HUB_V1
        return self.async_show_form(
            step_id=step_id, data_schema=data_schema, errors=errors
        )

    async def async_step_import(self, import_info):
        """Import a yaml entry as a config entry."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if not await _async_connect(**import_info):
            return self.async_abort(reason="cannot_connect")
        return self.async_create_entry(title="", data=import_info)


class InsteonOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle an Insteon options flow."""

    def __init__(self, config_entry):
        """Init the InsteonOptionsFlowHandler class."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Init the options config flow."""
        errors = {}
        if user_input is not None:
            change_hub_config = user_input.get(STEP_CHANGE_HUB_CONFIG, False)
            device_override = user_input.get(STEP_ADD_OVERRIDE, False)
            x10_device = user_input.get(STEP_ADD_X10, False)
            remove_override = user_input.get(STEP_REMOVE_OVERRIDE, False)
            remove_x10 = user_input.get(STEP_REMOVE_X10, False)
            if _only_one_selected(
                change_hub_config,
                device_override,
                x10_device,
                remove_override,
                remove_x10,
            ):
                if change_hub_config:
                    return await self.async_step_change_hub_config()
                if device_override:
                    return await self.async_step_add_override()
                if x10_device:
                    return await self.async_step_add_x10()
                if remove_override:
                    return await self.async_step_remove_override()
                if remove_x10:
                    return await self.async_step_remove_x10()
            errors["base"] = "select_single"

        data_schema = {
            vol.Optional(STEP_ADD_OVERRIDE): bool,
            vol.Optional(STEP_ADD_X10): bool,
        }
        if self.config_entry.data.get(CONF_HOST):
            data_schema[vol.Optional(STEP_CHANGE_HUB_CONFIG)] = bool

        options = {**self.config_entry.options}
        if options.get(CONF_OVERRIDE):
            data_schema[vol.Optional(STEP_REMOVE_OVERRIDE)] = bool
        if options.get(CONF_X10):
            data_schema[vol.Optional(STEP_REMOVE_X10)] = bool

        return self.async_show_form(
            step_id="init", data_schema=vol.Schema(data_schema), errors=errors
        )

    async def async_step_change_hub_config(self, user_input=None):
        """Change the Hub configuration."""
        if user_input is not None:
            data = {
                **self.config_entry.data,
                CONF_HOST: user_input[CONF_HOST],
                CONF_PORT: user_input[CONF_PORT],
            }
            if self.config_entry.data[CONF_HUB_VERSION] == 2:
                data[CONF_USERNAME] = user_input[CONF_USERNAME]
                data[CONF_PASSWORD] = user_input[CONF_PASSWORD]
            self.hass.config_entries.async_update_entry(self.config_entry, data=data)
            return self.async_create_entry(
                title="",
                data={**self.config_entry.options},
            )
        data_schema = build_hub_schema(**self.config_entry.data)
        return self.async_show_form(
            step_id=STEP_CHANGE_HUB_CONFIG, data_schema=data_schema
        )

    async def async_step_add_override(self, user_input=None):
        """Add a device override."""
        errors = {}
        if user_input is not None:
            try:
                data = add_device_override({**self.config_entry.options}, user_input)
                async_dispatcher_send(self.hass, SIGNAL_ADD_DEVICE_OVERRIDE, user_input)
                return self.async_create_entry(title="", data=data)
            except ValueError:
                errors["base"] = "input_error"
        schema_defaults = user_input if user_input is not None else {}
        data_schema = build_device_override_schema(**schema_defaults)
        return self.async_show_form(
            step_id=STEP_ADD_OVERRIDE, data_schema=data_schema, errors=errors
        )

    async def async_step_add_x10(self, user_input=None):
        """Add an X10 device."""
        errors = {}
        if user_input is not None:
            options = add_x10_device({**self.config_entry.options}, user_input)
            async_dispatcher_send(self.hass, SIGNAL_ADD_X10_DEVICE, user_input)
            return self.async_create_entry(title="", data=options)
        schema_defaults = user_input if user_input is not None else {}
        data_schema = build_x10_schema(**schema_defaults)
        return self.async_show_form(
            step_id=STEP_ADD_X10, data_schema=data_schema, errors=errors
        )

    async def async_step_remove_override(self, user_input=None):
        """Remove a device override."""
        errors = {}
        options = self.config_entry.options
        if user_input is not None:
            options = _remove_override(user_input[CONF_ADDRESS], options)
            async_dispatcher_send(
                self.hass,
                SIGNAL_REMOVE_DEVICE_OVERRIDE,
                user_input[CONF_ADDRESS],
            )
            return self.async_create_entry(title="", data=options)

        data_schema = build_remove_override_schema(options[CONF_OVERRIDE])
        return self.async_show_form(
            step_id=STEP_REMOVE_OVERRIDE, data_schema=data_schema, errors=errors
        )

    async def async_step_remove_x10(self, user_input=None):
        """Remove an X10 device."""
        errors = {}
        options = self.config_entry.options
        if user_input is not None:
            options, housecode, unitcode = _remove_x10(user_input[CONF_DEVICE], options)
            async_dispatcher_send(
                self.hass, SIGNAL_REMOVE_X10_DEVICE, housecode, unitcode
            )
            return self.async_create_entry(title="", data=options)

        data_schema = build_remove_x10_schema(options[CONF_X10])
        return self.async_show_form(
            step_id=STEP_REMOVE_X10, data_schema=data_schema, errors=errors
        )

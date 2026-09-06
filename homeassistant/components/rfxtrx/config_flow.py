"""Config flow for RFXCOM RFXtrx integration."""

from collections.abc import Mapping
import itertools
from types import MappingProxyType
from typing import Any, override

import RFXtrx as rfxtrxmod
import voluptuous as vol

from homeassistant.components import usb
from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.const import (
    CONF_COMMAND_OFF,
    CONF_COMMAND_ON,
    CONF_DEVICE,
    CONF_HOST,
    CONF_PORT,
    CONF_TYPE,
)
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import VolDictType

from . import DOMAIN, get_device_tuple_from_device, get_rfx_object
from .binary_sensor import supported as binary_supported
from .const import (
    CONF_AUTOMATIC_ADD,
    CONF_DATA_BITS,
    CONF_EVENT_CODE,
    CONF_OFF_DELAY,
    CONF_PROTOCOLS,
    CONF_VENETIAN_BLIND_MODE,
    CONST_VENETIAN_BLIND_MODE_DEFAULT,
    CONST_VENETIAN_BLIND_MODE_EU,
    CONST_VENETIAN_BLIND_MODE_US,
    DEVICE_PACKET_TYPE_LIGHTING4,
    SUBENTRY_TYPE_DEVICE,
)

CONF_MANUAL_PATH = "Enter Manually"

RECV_MODES = sorted(itertools.chain(*rfxtrxmod.lowlevel.Status.RECMODES))


def none_or_int(value: str | None, base: int) -> int | None:
    """Check if string is one otherwise convert to int."""
    if value is None:
        return None
    return int(value, base)


class RfxtrxOptionsFlow(OptionsFlow):
    """Handle Rfxtrx options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            data = {
                **self.config_entry.data,
                CONF_AUTOMATIC_ADD: user_input[CONF_AUTOMATIC_ADD],
                CONF_PROTOCOLS: user_input[CONF_PROTOCOLS] or None,
            }
            self.hass.config_entries.async_update_entry(self.config_entry, data=data)
            return self.async_create_entry(title="", data={})

        options = {
            vol.Optional(
                CONF_AUTOMATIC_ADD,
                default=self.config_entry.data[CONF_AUTOMATIC_ADD],
            ): bool,
            vol.Optional(
                CONF_PROTOCOLS,
                default=self.config_entry.data.get(CONF_PROTOCOLS) or [],
            ): cv.multi_select(RECV_MODES),
        }

        return self.async_show_form(step_id="init", data_schema=vol.Schema(options))


class RfxtrxSubentryFlowHandler(ConfigSubentryFlow):
    """Handle a subentry flow for a single RFXtrx device."""

    def __init__(self) -> None:
        """Initialize rfxtrx device subentry flow."""
        self._event_code: str | None = None
        self._device_object: rfxtrxmod.RFXtrxEvent | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add a new device."""
        errors: dict[str, str] = {}

        if user_input is not None:
            event_code = user_input[CONF_EVENT_CODE]
            device_object = get_rfx_object(event_code)
            if device_object is None:
                errors[CONF_EVENT_CODE] = "invalid_event_code"
            elif not self._can_add_device(device_object):
                errors[CONF_EVENT_CODE] = "already_configured_device"
            else:
                self._event_code = event_code
                self._device_object = device_object
                return await self.async_step_device_options()

        schema = vol.Schema({vol.Required(CONF_EVENT_CODE): str})
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Reconfigure an existing device.

        Also allows pointing the device at different hardware (e.g. after a
        broken unit was physically replaced) by entering a new event code -
        the device, its entities, and their history are kept as-is since
        their identity is the subentry, not the radio address.
        """
        subentry = self._get_reconfigure_subentry()
        errors: dict[str, str] = {}

        if user_input is not None:
            event_code = user_input[CONF_EVENT_CODE]
            device_object = get_rfx_object(event_code)
            if device_object is None:
                errors[CONF_EVENT_CODE] = "invalid_event_code"
            elif not self._can_add_device(
                device_object, exclude_subentry_id=subentry.subentry_id
            ):
                errors[CONF_EVENT_CODE] = "already_configured_device"
            else:
                self._event_code = event_code
                self._device_object = device_object
                return await self.async_step_device_options()

        schema = vol.Schema(
            {vol.Required(CONF_EVENT_CODE, default=subentry.data[CONF_EVENT_CODE]): str}
        )
        return self.async_show_form(
            step_id="reconfigure", data_schema=schema, errors=errors
        )

    async def async_step_device_options(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Manage device options."""
        errors: dict[str, str] = {}
        assert self._device_object
        assert self._event_code

        current_data: Mapping[str, Any] = {}
        if self.source == SOURCE_RECONFIGURE:
            current_data = self._get_reconfigure_subentry().data

        if user_input is not None:
            try:
                command_on = none_or_int(user_input.get(CONF_COMMAND_ON), 16)
            except ValueError:
                errors[CONF_COMMAND_ON] = "invalid_input_2262_on"

            try:
                command_off = none_or_int(user_input.get(CONF_COMMAND_OFF), 16)
            except ValueError:
                errors[CONF_COMMAND_OFF] = "invalid_input_2262_off"

            if not errors:
                device_id = get_device_tuple_from_device(
                    self._device_object.device,
                    data_bits=user_input.get(CONF_DATA_BITS),
                )
                data: dict[str, Any] = {CONF_EVENT_CODE: self._event_code}
                if user_input.get(CONF_OFF_DELAY):
                    data[CONF_OFF_DELAY] = user_input[CONF_OFF_DELAY]
                if user_input.get(CONF_DATA_BITS):
                    data[CONF_DATA_BITS] = user_input[CONF_DATA_BITS]
                if command_on:
                    data[CONF_COMMAND_ON] = command_on
                if command_off:
                    data[CONF_COMMAND_OFF] = command_off
                if user_input.get(CONF_VENETIAN_BLIND_MODE):
                    data[CONF_VENETIAN_BLIND_MODE] = user_input[
                        CONF_VENETIAN_BLIND_MODE
                    ]

                title = (
                    f"{self._device_object.device.type_string} {device_id.id_string}"
                )

                if self.source == SOURCE_RECONFIGURE:
                    return self.async_update_and_abort(
                        self._get_entry(),
                        self._get_reconfigure_subentry(),
                        title=title,
                        data=MappingProxyType(data),
                        unique_id=device_id.unique_id,
                    )
                return self.async_create_entry(
                    title=title,
                    data=MappingProxyType(data),
                    unique_id=device_id.unique_id,
                )

        data_schema: VolDictType = {}

        if binary_supported(self._device_object):
            off_delay_schema: VolDictType
            if current_data.get(CONF_OFF_DELAY):
                off_delay_schema = {
                    vol.Optional(
                        CONF_OFF_DELAY,
                        description={"suggested_value": current_data[CONF_OFF_DELAY]},
                    ): int,
                }
            else:
                off_delay_schema = {
                    vol.Optional(CONF_OFF_DELAY): int,
                }
            data_schema.update(off_delay_schema)

        if self._device_object.device.packettype == DEVICE_PACKET_TYPE_LIGHTING4:
            data_schema.update(
                {
                    vol.Optional(
                        CONF_DATA_BITS, default=current_data.get(CONF_DATA_BITS, 0)
                    ): int,
                    vol.Optional(
                        CONF_COMMAND_ON,
                        default=hex(current_data.get(CONF_COMMAND_ON, 0)),
                    ): str,
                    vol.Optional(
                        CONF_COMMAND_OFF,
                        default=hex(current_data.get(CONF_COMMAND_OFF, 0)),
                    ): str,
                }
            )

        if isinstance(self._device_object.device, rfxtrxmod.RfyDevice):
            data_schema.update(
                {
                    vol.Optional(
                        CONF_VENETIAN_BLIND_MODE,
                        default=current_data.get(
                            CONF_VENETIAN_BLIND_MODE, CONST_VENETIAN_BLIND_MODE_DEFAULT
                        ),
                    ): vol.In(
                        [
                            CONST_VENETIAN_BLIND_MODE_DEFAULT,
                            CONST_VENETIAN_BLIND_MODE_US,
                            CONST_VENETIAN_BLIND_MODE_EU,
                        ]
                    ),
                }
            )

        return self.async_show_form(
            step_id="device_options",
            data_schema=vol.Schema(data_schema),
            errors=errors,
        )

    def _can_add_device(
        self,
        new_rfx_obj: rfxtrxmod.RFXtrxEvent,
        exclude_subentry_id: str | None = None,
    ) -> bool:
        """Check if device does not already exist."""
        new_device_id = get_device_tuple_from_device(new_rfx_obj.device)
        for subentry in self._get_entry().subentries.values():
            if subentry.subentry_type != SUBENTRY_TYPE_DEVICE:
                continue
            if subentry.subentry_id == exclude_subentry_id:
                continue
            rfx_obj = get_rfx_object(subentry.data[CONF_EVENT_CODE])
            assert rfx_obj

            device_id = get_device_tuple_from_device(
                rfx_obj.device, subentry.data.get(CONF_DATA_BITS)
            )
            if new_device_id == device_id:
                return False

        return True


class RfxtrxConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for RFXCOM RFXtrx."""

    VERSION = 3

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step when user initializes a integration."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input[CONF_TYPE] == "Serial":
                return await self.async_step_setup_serial()

            return await self.async_step_setup_network()

        list_of_types = ["Serial", "Network"]

        schema = vol.Schema({vol.Required(CONF_TYPE): vol.In(list_of_types)})
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_setup_network(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step when setting up network configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]

            try:
                data = await self.async_validate_rfx(host=host, port=port)
            except CannotConnect:
                errors["base"] = "cannot_connect"

            if not errors:
                return self.async_create_entry(title="RFXTRX", data=data)

        schema = vol.Schema(
            {vol.Required(CONF_HOST): str, vol.Required(CONF_PORT): int}
        )
        return self.async_show_form(
            step_id="setup_network",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_setup_serial(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step when setting up serial configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            user_selection = user_input[CONF_DEVICE]
            if user_selection == CONF_MANUAL_PATH:
                return await self.async_step_setup_serial_manual_path()

            dev_path = user_selection

            try:
                data = await self.async_validate_rfx(device=dev_path)
            except CannotConnect:
                errors["base"] = "cannot_connect"

            if not errors:
                return self.async_create_entry(title="RFXTRX", data=data)

        ports = await usb.async_scan_serial_ports(self.hass)
        list_of_ports = {}
        for port in ports:
            list_of_ports[port.device] = (
                f"{port.device} - {port.description or 'n/a'}"
                f", s/n: {port.serial_number or 'n/a'}"
                + (f" - {port.manufacturer}" if port.manufacturer else "")
            )
        list_of_ports[CONF_MANUAL_PATH] = CONF_MANUAL_PATH

        schema = vol.Schema({vol.Required(CONF_DEVICE): vol.In(list_of_ports)})
        return self.async_show_form(
            step_id="setup_serial",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_setup_serial_manual_path(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select path manually."""
        errors: dict[str, str] = {}

        if user_input is not None:
            device = user_input[CONF_DEVICE]
            try:
                data = await self.async_validate_rfx(device=device)
            except CannotConnect:
                errors["base"] = "cannot_connect"

            if not errors:
                return self.async_create_entry(title="RFXTRX", data=data)

        schema = vol.Schema({vol.Required(CONF_DEVICE): str})
        return self.async_show_form(
            step_id="setup_serial_manual_path",
            data_schema=schema,
            errors=errors,
        )

    async def async_validate_rfx(
        self,
        host: str | None = None,
        port: int | None = None,
        device: str | None = None,
    ) -> dict[str, Any]:
        """Create data for rfxtrx entry."""
        success = await self.hass.async_add_executor_job(
            _test_transport, host, port, device
        )
        if not success:
            raise CannotConnect

        data: dict[str, Any] = {
            CONF_HOST: host,
            CONF_PORT: port,
            CONF_DEVICE: device,
            CONF_AUTOMATIC_ADD: False,
        }
        return data

    @classmethod
    @callback
    @override
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this handler."""
        return {SUBENTRY_TYPE_DEVICE: RfxtrxSubentryFlowHandler}

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> RfxtrxOptionsFlow:
        """Get the options flow for this handler."""
        return RfxtrxOptionsFlow()


def _test_transport(host: str | None, port: int | None, device: str | None) -> bool:
    """Construct a rfx object based on config."""
    if port is not None:
        conn = rfxtrxmod.PyNetworkTransport((host, port))
    else:
        conn = rfxtrxmod.PySerialTransport(device)

    try:
        conn.connect()
    except rfxtrxmod.RFXtrxTransportError, TimeoutError:
        return False

    return True


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""

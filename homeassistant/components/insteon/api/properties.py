"""Property update methods and schemas."""

from pyinsteon import devices
from pyinsteon.config import RADIO_BUTTON_GROUPS, RAMP_RATE_IN_SEC, get_usable_value
from pyinsteon.constants import (
    RAMP_RATES_SEC,
    PropertyType,
    RelayMode,
    ResponseStatus,
    ToggleMode,
)
from pyinsteon.device_types.device_base import Device
import voluptuous as vol
import voluptuous_serialize

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv

from ..const import (
    DEVICE_ADDRESS,
    ID,
    INSTEON_DEVICE_NOT_FOUND,
    PROPERTY_NAME,
    PROPERTY_VALUE,
    TYPE,
)
from .device import notify_device_not_found

SHOW_ADVANCED = "show_advanced"
RAMP_RATE_SECONDS = list(dict.fromkeys(RAMP_RATES_SEC))
RAMP_RATE_SECONDS.sort()
RAMP_RATE_LIST = [str(seconds) for seconds in RAMP_RATE_SECONDS]
TOGGLE_MODES = [str(ToggleMode(v)).lower() for v in list(ToggleMode)]
RELAY_MODES = [str(RelayMode(v)).lower() for v in list(RelayMode)]


def _bool_schema(name):
    return voluptuous_serialize.convert(vol.Schema({vol.Required(name): bool}))[0]


def _byte_schema(name):
    return voluptuous_serialize.convert(vol.Schema({vol.Required(name): cv.byte}))[0]


def _float_schema(name):
    return voluptuous_serialize.convert(vol.Schema({vol.Required(name): float}))[0]


def _list_schema(name, values):
    return voluptuous_serialize.convert(
        vol.Schema({vol.Required(name): vol.In(values)}),
        custom_serializer=cv.custom_serializer,
    )[0]


def _multi_select_schema(name, values):
    return voluptuous_serialize.convert(
        vol.Schema({vol.Optional(name): cv.multi_select(values)}),
        custom_serializer=cv.custom_serializer,
    )[0]


def _read_only_schema(name, value):
    """Return a constant value schema."""
    return voluptuous_serialize.convert(vol.Schema({vol.Required(name): value}))[0]


def get_schema(prop, name, groups):
    """Return the correct shema type."""
    if prop.is_read_only:
        return _read_only_schema(name, prop.value)
    if name == RAMP_RATE_IN_SEC:
        return _list_schema(name, RAMP_RATE_LIST)
    if name == RADIO_BUTTON_GROUPS:
        button_list = {str(group): groups[group].name for group in groups if group != 1}
        return _multi_select_schema(name, button_list)
    if prop.value_type == bool:
        return _bool_schema(name)
    if prop.value_type == int:
        return _byte_schema(name)
    if prop.value_type == float:
        return _float_schema(name)
    if prop.value_type == ToggleMode:
        return _list_schema(name, TOGGLE_MODES)
    if prop.value_type == RelayMode:
        return _list_schema(name, RELAY_MODES)
    return None


def get_properties(device: Device, show_advanced=False):
    """Get the properties of an Insteon device and return the records and schema."""

    properties = []
    schema = {}

    for name, prop in device.configuration.items():
        if prop.is_read_only and not show_advanced:
            continue

        prop_schema = get_schema(prop, name, device.groups)
        if prop_schema is None:
            continue
        schema[name] = prop_schema
        properties.append(property_to_dict(prop))

    if show_advanced:
        for name, prop in device.operating_flags.items():
            if prop.property_type != PropertyType.ADVANCED:
                continue
            prop_schema = get_schema(prop, name, device.groups)
            if prop_schema is not None:
                schema[name] = prop_schema
                properties.append(property_to_dict(prop))
        for name, prop in device.properties.items():
            if prop.property_type != PropertyType.ADVANCED:
                continue
            prop_schema = get_schema(prop, name, device.groups)
            if prop_schema is not None:
                schema[name] = prop_schema
                properties.append(property_to_dict(prop))

    return properties, schema


def property_to_dict(prop):
    """Return a property data row."""
    value = get_usable_value(prop)
    modified = value == prop.new_value
    if prop.value_type in [ToggleMode, RelayMode] or prop.name == RAMP_RATE_IN_SEC:
        value = str(value).lower()
    prop_dict = {"name": prop.name, "value": value, "modified": modified}
    return prop_dict


def update_property(device, prop_name, value):
    """Update the value of a device property."""
    prop = device.configuration[prop_name]
    if prop.value_type == ToggleMode:
        toggle_mode = getattr(ToggleMode, value.upper())
        prop.new_value = toggle_mode
    elif prop.value_type == RelayMode:
        relay_mode = getattr(RelayMode, value.upper())
        prop.new_value = relay_mode
    else:
        prop.new_value = value


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "insteon/properties/get",
        vol.Required(DEVICE_ADDRESS): str,
        vol.Required(SHOW_ADVANCED): bool,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_get_properties(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict,
) -> None:
    """Add the default All-Link Database records for an Insteon device."""
    if not (device := devices[msg[DEVICE_ADDRESS]]):
        notify_device_not_found(connection, msg, INSTEON_DEVICE_NOT_FOUND)
        return

    properties, schema = get_properties(device, msg[SHOW_ADVANCED])

    connection.send_result(msg[ID], {"properties": properties, "schema": schema})


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "insteon/properties/change",
        vol.Required(DEVICE_ADDRESS): str,
        vol.Required(PROPERTY_NAME): str,
        vol.Required(PROPERTY_VALUE): vol.Any(list, int, float, bool, str),
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_change_properties_record(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict,
) -> None:
    """Add the default All-Link Database records for an Insteon device."""
    if not (device := devices[msg[DEVICE_ADDRESS]]):
        notify_device_not_found(connection, msg, INSTEON_DEVICE_NOT_FOUND)
        return

    update_property(device, msg[PROPERTY_NAME], msg[PROPERTY_VALUE])
    connection.send_result(msg[ID])


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "insteon/properties/write",
        vol.Required(DEVICE_ADDRESS): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_write_properties(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict,
) -> None:
    """Add the default All-Link Database records for an Insteon device."""
    if not (device := devices[msg[DEVICE_ADDRESS]]):
        notify_device_not_found(connection, msg, INSTEON_DEVICE_NOT_FOUND)
        return

    result = await device.async_write_config()
    await devices.async_save(workdir=hass.config.config_dir)
    if result not in [ResponseStatus.SUCCESS, ResponseStatus.RUN_ON_WAKE]:
        connection.send_message(
            websocket_api.error_message(
                msg[ID], "write_failed", "properties not written to device"
            )
        )
        return
    connection.send_result(msg[ID])


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "insteon/properties/load",
        vol.Required(DEVICE_ADDRESS): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_load_properties(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict,
) -> None:
    """Add the default All-Link Database records for an Insteon device."""
    if not (device := devices[msg[DEVICE_ADDRESS]]):
        notify_device_not_found(connection, msg, INSTEON_DEVICE_NOT_FOUND)
        return

    result = await device.async_read_config(read_aldb=False)
    await devices.async_save(workdir=hass.config.config_dir)

    if result not in [ResponseStatus.SUCCESS, ResponseStatus.RUN_ON_WAKE]:
        connection.send_message(
            websocket_api.error_message(
                msg[ID], "load_failed", "properties not loaded from device"
            )
        )
        return
    connection.send_result(msg[ID])


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "insteon/properties/reset",
        vol.Required(DEVICE_ADDRESS): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_reset_properties(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict,
) -> None:
    """Add the default All-Link Database records for an Insteon device."""
    if not (device := devices[msg[DEVICE_ADDRESS]]):
        notify_device_not_found(connection, msg, INSTEON_DEVICE_NOT_FOUND)
        return

    for prop in device.operating_flags:
        device.operating_flags[prop].new_value = None
    for prop in device.properties:
        device.properties[prop].new_value = None
    connection.send_result(msg[ID])

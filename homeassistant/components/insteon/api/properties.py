"""Property update methods and schemas."""
from itertools import chain

from pyinsteon import devices
from pyinsteon.constants import RAMP_RATES, ResponseStatus
from pyinsteon.device_types.device_base import Device
from pyinsteon.extended_property import (
    NON_TOGGLE_MASK,
    NON_TOGGLE_ON_OFF_MASK,
    OFF_MASK,
    ON_MASK,
    RAMP_RATE,
)
from pyinsteon.utils import ramp_rate_to_seconds, seconds_to_ramp_rate
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

TOGGLE_ON_OFF_MODE = "toggle_on_off_mode"
NON_TOGGLE_ON_MODE = "non_toggle_on_mode"
NON_TOGGLE_OFF_MODE = "non_toggle_off_mode"
RADIO_BUTTON_GROUP_PROP = "radio_button_group_"
TOGGLE_PROP = "toggle_"
RAMP_RATE_SECONDS = list(dict.fromkeys(RAMP_RATES.values()))
RAMP_RATE_SECONDS.sort()
TOGGLE_MODES = {TOGGLE_ON_OFF_MODE: 0, NON_TOGGLE_ON_MODE: 1, NON_TOGGLE_OFF_MODE: 2}
TOGGLE_MODES_SCHEMA = {
    0: TOGGLE_ON_OFF_MODE,
    1: NON_TOGGLE_ON_MODE,
    2: NON_TOGGLE_OFF_MODE,
}


def _bool_schema(name):
    return voluptuous_serialize.convert(vol.Schema({vol.Required(name): bool}))[0]


def _byte_schema(name):
    return voluptuous_serialize.convert(vol.Schema({vol.Required(name): cv.byte}))[0]


def _ramp_rate_schema(name):
    return voluptuous_serialize.convert(
        vol.Schema({vol.Required(name): vol.In(RAMP_RATE_SECONDS)}),
        custom_serializer=cv.custom_serializer,
    )[0]


def get_properties(device: Device):
    """Get the properties of an Insteon device and return the records and schema."""

    properties = []
    schema = {}

    # Limit the properties we manage at this time.
    for prop_name in device.operating_flags:
        if not device.operating_flags[prop_name].is_read_only:
            prop_dict, schema_dict = _get_property(device.operating_flags[prop_name])
            properties.append(prop_dict)
            schema[prop_name] = schema_dict

    mask_found = False
    for prop_name in device.properties:
        if device.properties[prop_name].is_read_only:
            continue

        if prop_name == RAMP_RATE:
            rr_prop, rr_schema = _get_ramp_rate_property(device.properties[prop_name])
            properties.append(rr_prop)
            schema[RAMP_RATE] = rr_schema

        elif not mask_found and "mask" in prop_name:
            mask_found = True
            toggle_props, toggle_schema = _get_toggle_properties(device)
            properties.extend(toggle_props)
            schema.update(toggle_schema)

            rb_props, rb_schema = _get_radio_button_properties(device)
            properties.extend(rb_props)
            schema.update(rb_schema)
        else:
            prop_dict, schema_dict = _get_property(device.properties[prop_name])
            properties.append(prop_dict)
            schema[prop_name] = schema_dict

    return properties, schema


def set_property(device, prop_name: str, value):
    """Update a property value."""
    if isinstance(value, bool) and prop_name in device.operating_flags:
        device.operating_flags[prop_name].new_value = value

    elif prop_name == RAMP_RATE:
        device.properties[prop_name].new_value = seconds_to_ramp_rate(value)

    elif prop_name.startswith(RADIO_BUTTON_GROUP_PROP):
        buttons = [int(button) for button in value]
        rb_groups = _calc_radio_button_groups(device)
        curr_group = int(prop_name[len(RADIO_BUTTON_GROUP_PROP) :])
        if len(rb_groups) > curr_group:
            removed = [btn for btn in rb_groups[curr_group] if btn not in buttons]
            if removed:
                device.clear_radio_buttons(removed)
        if buttons:
            device.set_radio_buttons(buttons)

    elif prop_name.startswith(TOGGLE_PROP):
        button_name = prop_name[len(TOGGLE_PROP) :]
        for button in device.groups:
            if device.groups[button].name == button_name:
                device.set_toggle_mode(button, int(value))

    else:
        device.properties[prop_name].new_value = value


def _get_property(prop):
    """Return a property data row."""
    value, modified = _get_usable_value(prop)
    prop_dict = {"name": prop.name, "value": value, "modified": modified}
    if isinstance(prop.value, bool):
        schema = _bool_schema(prop.name)
    else:
        schema = _byte_schema(prop.name)
    return prop_dict, {"name": prop.name, **schema}


def _get_toggle_properties(device):
    """Generate the mask properties for a KPL device."""
    props = []
    schema = {}
    toggle_prop = device.properties[NON_TOGGLE_MASK]
    toggle_on_prop = device.properties[NON_TOGGLE_ON_OFF_MASK]
    for button in device.groups:
        name = f"{TOGGLE_PROP}{device.groups[button].name}"
        value, modified = _toggle_button_value(toggle_prop, toggle_on_prop, button)
        props.append({"name": name, "value": value, "modified": modified})
        toggle_schema = vol.Schema({vol.Required(name): vol.In(TOGGLE_MODES_SCHEMA)})
        toggle_schema_dict = voluptuous_serialize.convert(
            toggle_schema, custom_serializer=cv.custom_serializer
        )
        schema[name] = toggle_schema_dict[0]
    return props, schema


def _toggle_button_value(non_toggle_prop, toggle_on_prop, button):
    """Determine the toggle value of a button."""
    toggle_mask, toggle_modified = _get_usable_value(non_toggle_prop)
    toggle_on_mask, toggle_on_modified = _get_usable_value(toggle_on_prop)

    bit = button - 1
    if not toggle_mask & 1 << bit:
        value = 0
    else:
        if toggle_on_mask & 1 << bit:
            value = 1
        else:
            value = 2

    modified = False
    if toggle_modified:
        curr_bit = non_toggle_prop.value & 1 << bit
        new_bit = non_toggle_prop.new_value & 1 << bit
        modified = not curr_bit == new_bit

    if not modified and value != 0 and toggle_on_modified:
        curr_bit = toggle_on_prop.value & 1 << bit
        new_bit = toggle_on_prop.new_value & 1 << bit
        modified = not curr_bit == new_bit

    return value, modified


def _get_radio_button_properties(device):
    """Return the values and schema to set KPL buttons as radio buttons."""
    rb_groups = _calc_radio_button_groups(device)
    props = []
    schema = {}
    index = 0
    remaining_buttons = []

    buttons_in_groups = list(chain.from_iterable(rb_groups))

    # Identify buttons not belonging to any group
    for button in device.groups:
        if button not in buttons_in_groups:
            remaining_buttons.append(button)

    for rb_group in rb_groups:
        name = f"{RADIO_BUTTON_GROUP_PROP}{index}"
        button_1 = rb_group[0]
        button_str = f"_{button_1}" if button_1 != 1 else ""
        on_mask = device.properties[f"{ON_MASK}{button_str}"]
        off_mask = device.properties[f"{OFF_MASK}{button_str}"]
        modified = on_mask.is_dirty or off_mask.is_dirty

        props.append(
            {
                "name": name,
                "modified": modified,
                "value": rb_group,
            }
        )

        options = {
            button: device.groups[button].name
            for button in chain.from_iterable([rb_group, remaining_buttons])
        }
        rb_schema = vol.Schema({vol.Optional(name): cv.multi_select(options)})

        rb_schema_dict = voluptuous_serialize.convert(
            rb_schema, custom_serializer=cv.custom_serializer
        )
        schema[name] = rb_schema_dict[0]

        index += 1

    if len(remaining_buttons) > 1:
        name = f"{RADIO_BUTTON_GROUP_PROP}{index}"

        props.append(
            {
                "name": name,
                "modified": False,
                "value": [],
            }
        )

        options = {button: device.groups[button].name for button in remaining_buttons}
        rb_schema = vol.Schema({vol.Optional(name): cv.multi_select(options)})

        rb_schema_dict = voluptuous_serialize.convert(
            rb_schema, custom_serializer=cv.custom_serializer
        )
        schema[name] = rb_schema_dict[0]

    return props, schema


def _calc_radio_button_groups(device):
    """Return existing radio button groups."""
    rb_groups = []
    for button in device.groups:
        if button not in list(chain.from_iterable(rb_groups)):
            button_str = "" if button == 1 else f"_{button}"
            on_mask, _ = _get_usable_value(device.properties[f"{ON_MASK}{button_str}"])
            if on_mask != 0:
                rb_group = [button]
                for bit in list(range(0, button - 1)) + list(range(button, 8)):
                    if on_mask & 1 << bit:
                        rb_group.append(bit + 1)
                if len(rb_group) > 1:
                    rb_groups.append(rb_group)
    return rb_groups


def _get_ramp_rate_property(prop):
    """Return the value and schema of a ramp rate property."""
    rr_prop, _ = _get_property(prop)
    rr_prop["value"] = ramp_rate_to_seconds(rr_prop["value"])
    return rr_prop, _ramp_rate_schema(prop.name)


def _get_usable_value(prop):
    """Return the current or the modified value of a property."""
    value = prop.value if prop.new_value is None else prop.new_value
    return value, prop.is_dirty


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "insteon/properties/get",
        vol.Required(DEVICE_ADDRESS): str,
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
    device = devices[msg[DEVICE_ADDRESS]]
    if not device:
        notify_device_not_found(connection, msg, INSTEON_DEVICE_NOT_FOUND)
        return

    properties, schema = get_properties(device)

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
    device = devices[msg[DEVICE_ADDRESS]]
    if not device:
        notify_device_not_found(connection, msg, INSTEON_DEVICE_NOT_FOUND)
        return

    set_property(device, msg[PROPERTY_NAME], msg[PROPERTY_VALUE])
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
    device = devices[msg[DEVICE_ADDRESS]]
    if not device:
        notify_device_not_found(connection, msg, INSTEON_DEVICE_NOT_FOUND)
        return

    result1 = await device.async_write_op_flags()
    result2 = await device.async_write_ext_properties()
    await devices.async_save(workdir=hass.config.config_dir)
    if result1 != ResponseStatus.SUCCESS or result2 != ResponseStatus.SUCCESS:
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
    device = devices[msg[DEVICE_ADDRESS]]
    if not device:
        notify_device_not_found(connection, msg, INSTEON_DEVICE_NOT_FOUND)
        return

    result1 = await device.async_read_op_flags()
    result2 = await device.async_read_ext_properties()
    await devices.async_save(workdir=hass.config.config_dir)
    if result1 != ResponseStatus.SUCCESS or result2 != ResponseStatus.SUCCESS:
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
    device = devices[msg[DEVICE_ADDRESS]]
    if not device:
        notify_device_not_found(connection, msg, INSTEON_DEVICE_NOT_FOUND)
        return

    for prop in device.operating_flags:
        device.operating_flags[prop].new_value = None
    for prop in device.properties:
        device.properties[prop].new_value = None
    connection.send_result(msg[ID])

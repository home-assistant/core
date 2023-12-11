"""API calls to manage Insteon configuration changes."""
from __future__ import annotations

from typing import Any

from pyinsteon import async_close, async_connect, devices
from pyinsteon.address import Address
import voluptuous as vol
import voluptuous_serialize

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_DEVICE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from ..const import (
    CONF_HOUSECODE,
    CONF_OVERRIDE,
    CONF_UNITCODE,
    CONF_X10,
    DEVICE_ADDRESS,
    DOMAIN,
    ID,
    SIGNAL_ADD_DEVICE_OVERRIDE,
    SIGNAL_ADD_X10_DEVICE,
    SIGNAL_REMOVE_DEVICE_OVERRIDE,
    TYPE,
)
from ..schemas import (
    build_device_override_schema,
    build_hub_schema,
    build_plm_manual_schema,
    build_plm_schema,
)
from ..utils import async_get_usb_ports

HUB_V1_SCHEMA = build_hub_schema(hub_version=1)
HUB_V2_SCHEMA = build_hub_schema(hub_version=2)
PLM_SCHEMA = build_plm_manual_schema()
DEVICE_OVERRIDE_SCHEMA = build_device_override_schema()
OVERRIDE = "override"


def get_insteon_config_entry(hass: HomeAssistant) -> ConfigEntry:
    """Return the Insteon configuration entry."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        return entry
    raise ValueError("No Insteon configuration exists")


def add_x10_device(hass: HomeAssistant, x10_device: dict):
    """Add an X10 device to the Insteon integration."""
    config_entry = get_insteon_config_entry(hass)
    options_config = {**config_entry.options}
    x10_config = config_entry.options.get(CONF_X10, [])

    # Check that we are not adding an existing device
    for curr_device in x10_config:
        if (
            curr_device[CONF_HOUSECODE] == x10_device[CONF_HOUSECODE]
            and curr_device[CONF_UNITCODE] == x10_device[CONF_UNITCODE]
        ):
            raise ValueError("Duplicate X10 device")

    x10_config.append(x10_device)
    options_config[CONF_X10] = x10_config
    hass.config_entries.async_update_entry(entry=config_entry, options=options_config)
    async_dispatcher_send(hass, SIGNAL_ADD_X10_DEVICE, x10_device)


def remove_x10_device(hass: HomeAssistant, housecode: str, unitcode: int):
    """Remove an X10 device from the config."""

    config_entry = get_insteon_config_entry(hass)
    new_options = {**config_entry.options}
    new_x10 = []
    try:
        new_options.pop(CONF_X10)
    except KeyError:
        # There are no X10 devices so nothing to do
        return
    for existing_device in config_entry.options[CONF_X10]:
        if (
            existing_device[CONF_HOUSECODE].lower() != housecode.lower()
            or existing_device[CONF_UNITCODE] != unitcode
        ):
            new_x10.append(existing_device)
    if new_x10:
        new_options[CONF_X10] = new_x10
    hass.config_entries.async_update_entry(entry=config_entry, options=new_options)


def add_device_overide(hass: HomeAssistant, override: dict[str, str]):
    """Add an Insteon device override."""

    if has_device_override(hass, Address(override[CONF_ADDRESS])):
        raise ValueError("Duplicate override")

    config_entry = get_insteon_config_entry(hass)
    options_config = {**config_entry.options}
    override_config = config_entry.options.get(CONF_OVERRIDE, [])
    override_config.append(override)
    options_config[CONF_OVERRIDE] = override_config
    hass.config_entries.async_update_entry(entry=config_entry, options=options_config)
    async_dispatcher_send(hass, SIGNAL_ADD_DEVICE_OVERRIDE, override)


def has_device_override(hass: HomeAssistant, address: Address):
    """Test if a device has a device override."""

    config_entry = get_insteon_config_entry(hass)
    override_config = config_entry.options.get(CONF_OVERRIDE, [])
    for existing_override in override_config:
        if Address(existing_override[CONF_ADDRESS]) == address:
            return True
    return False


def remove_device_override(hass: HomeAssistant, address: Address):
    """Remove a device override from config."""

    config_entry = get_insteon_config_entry(hass)
    new_options = {**config_entry.options}
    new_overrides = []
    try:
        new_options.pop(CONF_OVERRIDE)
    except KeyError:
        # There are no overrides so nothing to do
        return
    for existing_override in config_entry.options[CONF_OVERRIDE]:
        if Address(existing_override[CONF_ADDRESS]) != address:
            new_overrides.append(existing_override)
    if new_overrides:
        new_options[CONF_OVERRIDE] = new_overrides
    hass.config_entries.async_update_entry(entry=config_entry, options=new_options)


async def _async_connect(**kwargs):
    """Connect to the Insteon modem."""
    if devices.modem:
        await async_close()
    try:
        await async_connect(**kwargs)
        return True
    except ConnectionError:
        return False


@websocket_api.websocket_command({vol.Required(TYPE): "insteon/config/get"})
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_get_config(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Get Insteon configuration."""
    config_entry = get_insteon_config_entry(hass)
    modem_config = config_entry.data
    options_config = config_entry.options
    x10_config = options_config.get(CONF_X10)
    override_config = options_config.get(CONF_OVERRIDE)
    connection.send_result(
        msg[ID],
        {
            "modem_config": {**modem_config},
            "x10_config": x10_config,
            "override_config": override_config,
        },
    )


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "insteon/config/get_modem_schema",
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_get_modem_schema(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Get the schema for the modem configuration."""
    config_entry = get_insteon_config_entry(hass)
    config_data = config_entry.data
    if device := config_data.get(CONF_DEVICE):
        ports = await async_get_usb_ports(hass=hass)
        plm_schema = voluptuous_serialize.convert(
            build_plm_schema(ports=ports, device=device)
        )
        connection.send_result(msg[ID], plm_schema)
    else:
        hub_schema = voluptuous_serialize.convert(build_hub_schema(**config_data))
        connection.send_result(msg[ID], hub_schema)


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "insteon/config/update_modem_config",
        vol.Required("config"): vol.Any(PLM_SCHEMA, HUB_V2_SCHEMA, HUB_V1_SCHEMA),
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_update_modem_config(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Get the schema for the modem configuration."""
    config = msg["config"]
    config_entry = get_insteon_config_entry(hass)
    is_connected = devices.modem.connected

    if not await _async_connect(**config):
        connection.send_error(
            msg_id=msg[ID], code="connection_failed", message="Connection failed"
        )
        # Try to reconnect using old info
        if is_connected:
            await _async_connect(**config_entry.data)
        return

    hass.config_entries.async_update_entry(
        entry=config_entry,
        data=config,
    )
    connection.send_result(msg[ID], {"status": "success"})


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "insteon/config/device_override/add",
        vol.Required(OVERRIDE): DEVICE_OVERRIDE_SCHEMA,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_add_device_override(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Get the schema for the modem configuration."""
    override = msg[OVERRIDE]
    try:
        add_device_overide(hass, override)
    except ValueError:
        connection.send_error(msg[ID], "duplicate", "Duplicate device address")

    connection.send_result(msg[ID])


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "insteon/config/device_override/remove",
        vol.Required(DEVICE_ADDRESS): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_remove_device_override(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Get the schema for the modem configuration."""
    address = Address(msg[DEVICE_ADDRESS])
    remove_device_override(hass, address)
    async_dispatcher_send(hass, SIGNAL_REMOVE_DEVICE_OVERRIDE, address)
    connection.send_result(msg[ID])

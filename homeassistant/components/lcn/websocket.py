"""LCN Websocket API."""

from __future__ import annotations

from copy import deepcopy
from typing import Final

import lcn_frontend as lcn_panel
import voluptuous as vol

from homeassistant.components import panel_custom, websocket_api
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_DEVICES,
    CONF_DOMAIN,
    CONF_ENTITIES,
    CONF_ID,
    CONF_NAME,
    CONF_RESOURCE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
import homeassistant.helpers.config_validation as cv

from .const import (
    ADD_ENTITIES_CALLBACKS,
    CONF_DOMAIN_DATA,
    CONF_HARDWARE_SERIAL,
    CONF_HARDWARE_TYPE,
    CONF_SOFTWARE_SERIAL,
    CONNECTION,
    DOMAIN,
)
from .helpers import (
    DeviceConnectionType,
    async_update_device_config,
    generate_unique_id,
    get_device_config,
    get_device_connection,
    get_resource,
    purge_device_registry,
    purge_entity_registry,
    register_lcn_address_devices,
)
from .schemas import (
    ADDRESS_SCHEMA,
    DOMAIN_DATA_BINARY_SENSOR,
    DOMAIN_DATA_CLIMATE,
    DOMAIN_DATA_COVER,
    DOMAIN_DATA_LIGHT,
    DOMAIN_DATA_SCENE,
    DOMAIN_DATA_SENSOR,
    DOMAIN_DATA_SWITCH,
)

URL_BASE: Final = "/lcn_static"


async def register_panel(hass: HomeAssistant) -> None:
    """Register the LCN Panel and Websocket API."""
    websocket_api.async_register_command(hass, websocket_get_hosts)
    websocket_api.async_register_command(hass, websocket_get_device_configs)
    websocket_api.async_register_command(hass, websocket_get_entity_configs)
    websocket_api.async_register_command(hass, websocket_scan_devices)
    websocket_api.async_register_command(hass, websocket_add_device)
    websocket_api.async_register_command(hass, websocket_delete_device)
    websocket_api.async_register_command(hass, websocket_add_entity)
    websocket_api.async_register_command(hass, websocket_delete_entity)

    if DOMAIN not in hass.data.get("frontend_panels", {}):
        hass.http.register_static_path(
            URL_BASE,
            path=lcn_panel.locate_dir(),
            cache_headers=lcn_panel.is_prod_build,
        )
        await panel_custom.async_register_panel(
            hass=hass,
            frontend_url_path=DOMAIN,
            webcomponent_name=lcn_panel.webcomponent_name,
            sidebar_title=DOMAIN.upper(),
            sidebar_icon="mdi:cogs",
            module_url=f"{URL_BASE}/{lcn_panel.entrypoint_js}",
            embed_iframe=True,
            require_admin=True,
        )


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "lcn/hosts"})
@websocket_api.async_response
async def websocket_get_hosts(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Get LCN hosts."""
    config_entries = hass.config_entries.async_entries(DOMAIN)

    hosts = [
        {
            CONF_NAME: config_entry.title,
            CONF_ID: config_entry.entry_id,
        }
        for config_entry in config_entries
        if not config_entry.disabled_by
    ]

    connection.send_result(msg["id"], hosts)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {vol.Required("type"): "lcn/devices", vol.Required("host_id"): cv.string}
)
@websocket_api.async_response
async def websocket_get_device_configs(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Get device configs."""
    config_entry = hass.config_entries.async_get_entry(msg["host_id"])
    if config_entry is None:
        return

    connection.send_result(msg["id"], config_entry.data[CONF_DEVICES])


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "lcn/entities",
        vol.Required("host_id"): cv.string,
        vol.Optional(CONF_ADDRESS): ADDRESS_SCHEMA,
    }
)
@websocket_api.async_response
async def websocket_get_entity_configs(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Get entities configs."""
    config_entry = hass.config_entries.async_get_entry(msg["host_id"])
    if config_entry is None:
        return

    if CONF_ADDRESS in msg:
        entity_configs = [
            entity_config
            for entity_config in config_entry.data[CONF_ENTITIES]
            if tuple(entity_config[CONF_ADDRESS]) == msg[CONF_ADDRESS]
        ]
    else:
        entity_configs = config_entry.data[CONF_ENTITIES]

    connection.send_result(msg["id"], entity_configs)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {vol.Required("type"): "lcn/devices/scan", vol.Required("host_id"): cv.string}
)
@websocket_api.async_response
async def websocket_scan_devices(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Scan for new devices."""
    config_entry = hass.config_entries.async_get_entry(msg["host_id"])
    if config_entry is None:
        return

    host_connection = hass.data[DOMAIN][config_entry.entry_id][CONNECTION]
    await host_connection.scan_modules()

    for device_connection in host_connection.address_conns.values():
        if not device_connection.is_group:
            await async_create_or_update_device_in_config_entry(
                hass, device_connection, config_entry
            )

    # create/update devices in device registry
    register_lcn_address_devices(hass, config_entry)

    connection.send_result(msg["id"], config_entry.data[CONF_DEVICES])


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "lcn/devices/add",
        vol.Required("host_id"): cv.string,
        vol.Required(CONF_ADDRESS): ADDRESS_SCHEMA,
        vol.Required(CONF_NAME): cv.string,
    }
)
@websocket_api.async_response
async def websocket_add_device(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Add a device."""
    config_entry = hass.config_entries.async_get_entry(msg["host_id"])
    if config_entry is None:
        return

    if get_device_config(msg[CONF_ADDRESS], config_entry):
        connection.send_result(
            msg["id"], False
        )  # device_config already in config_entry
        return

    device_config = {
        CONF_ADDRESS: msg[CONF_ADDRESS],
        CONF_NAME: "",
        CONF_HARDWARE_SERIAL: -1,
        CONF_SOFTWARE_SERIAL: -1,
        CONF_HARDWARE_TYPE: -1,
    }

    # update device info from LCN
    device_connection = get_device_connection(hass, msg[CONF_ADDRESS], config_entry)
    await async_update_device_config(device_connection, device_config)

    # add device_config to config_entry
    data = deepcopy(dict(config_entry.data))
    data[CONF_DEVICES].append(device_config)
    hass.config_entries.async_update_entry(config_entry, data=data)

    # create/update devices in device registry
    register_lcn_address_devices(hass, config_entry)

    connection.send_result(msg["id"], True)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "lcn/devices/delete",
        vol.Required("host_id"): cv.string,
        vol.Required(CONF_ADDRESS): ADDRESS_SCHEMA,
    }
)
@websocket_api.async_response
async def websocket_delete_device(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Delete a device."""
    config_entry = hass.config_entries.async_get_entry(msg["host_id"])
    if config_entry is None:
        return

    device_config = get_device_config(msg[CONF_ADDRESS], config_entry)

    device_registry = dr.async_get(hass)
    identifiers = {
        (DOMAIN, generate_unique_id(config_entry.entry_id, msg[CONF_ADDRESS]))
    }
    device = device_registry.async_get_device(identifiers, set())

    if not (device and device_config):
        return

    # remove module/group device from config_entry data
    data = deepcopy(dict(config_entry.data))
    data[CONF_DEVICES].remove(device_config)
    hass.config_entries.async_update_entry(config_entry, data=data)

    # remove all child devices (and entities) from config_entry data
    for entity_config in data[CONF_ENTITIES][:]:
        if tuple(entity_config[CONF_ADDRESS]) == msg[CONF_ADDRESS]:
            data[CONF_ENTITIES].remove(entity_config)

    hass.config_entries.async_update_entry(config_entry, data=data)

    # cleanup registries
    purge_entity_registry(hass, config_entry.entry_id, data)
    purge_device_registry(hass, config_entry.entry_id, data)

    # return the device config, not all devices !!!
    connection.send_result(msg["id"])


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "lcn/entities/add",
        vol.Required("host_id"): cv.string,
        vol.Required(CONF_ADDRESS): ADDRESS_SCHEMA,
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_DOMAIN): cv.string,
        vol.Required(CONF_DOMAIN_DATA): vol.Any(
            DOMAIN_DATA_BINARY_SENSOR,
            DOMAIN_DATA_CLIMATE,
            DOMAIN_DATA_COVER,
            DOMAIN_DATA_LIGHT,
            DOMAIN_DATA_SCENE,
            DOMAIN_DATA_SENSOR,
            DOMAIN_DATA_SWITCH,
        ),
    }
)
@websocket_api.async_response
async def websocket_add_entity(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Add an entity."""
    if not (config_entry := hass.config_entries.async_get_entry(msg["host_id"])):
        return

    if not (device_config := get_device_config(msg[CONF_ADDRESS], config_entry)):
        return

    domain_name = msg[CONF_DOMAIN]
    domain_data = msg[CONF_DOMAIN_DATA]
    resource = get_resource(domain_name, domain_data).lower()
    unique_id = generate_unique_id(
        config_entry.entry_id,
        device_config[CONF_ADDRESS],
        resource,
    )

    entity_registry = er.async_get(hass)
    if entity_registry.async_get_entity_id(msg[CONF_DOMAIN], DOMAIN, unique_id):
        connection.send_result(msg["id"], False)
        return

    entity_config = {
        CONF_ADDRESS: msg[CONF_ADDRESS],
        CONF_NAME: msg[CONF_NAME],
        CONF_RESOURCE: resource,
        CONF_DOMAIN: domain_name,
        CONF_DOMAIN_DATA: domain_data,
    }

    # Create new entity and add to corresponding component
    callbacks = hass.data[DOMAIN][msg["host_id"]][ADD_ENTITIES_CALLBACKS]
    async_add_entities, create_lcn_entity = callbacks[msg[CONF_DOMAIN]]

    entity = create_lcn_entity(hass, entity_config, config_entry)
    async_add_entities([entity])

    # Add entity config to config_entry
    data = deepcopy(dict(config_entry.data))
    data[CONF_ENTITIES].append(entity_config)

    # schedule config_entry for save
    hass.config_entries.async_update_entry(config_entry, data=data)

    connection.send_result(msg["id"], True)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "lcn/entities/delete",
        vol.Required("host_id"): cv.string,
        vol.Required(CONF_ADDRESS): ADDRESS_SCHEMA,
        vol.Required(CONF_DOMAIN): cv.string,
        vol.Required(CONF_RESOURCE): cv.string,
    }
)
@websocket_api.async_response
async def websocket_delete_entity(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Delete an entity."""
    config_entry = hass.config_entries.async_get_entry(msg["host_id"])
    if config_entry is None:
        return

    entity_config = next(
        (
            entity_config
            for entity_config in config_entry.data[CONF_ENTITIES]
            if (
                tuple(entity_config[CONF_ADDRESS]) == msg[CONF_ADDRESS]
                and entity_config[CONF_DOMAIN] == msg[CONF_DOMAIN]
                and entity_config[CONF_RESOURCE] == msg[CONF_RESOURCE]
            )
        ),
        None,
    )

    data = deepcopy(dict(config_entry.data))
    data[CONF_ENTITIES].remove(entity_config)
    hass.config_entries.async_update_entry(config_entry, data=data)

    # cleanup registries
    purge_entity_registry(hass, config_entry.entry_id, data)
    purge_device_registry(hass, config_entry.entry_id, data)

    connection.send_result(msg["id"])


async def async_create_or_update_device_in_config_entry(
    hass: HomeAssistant,
    device_connection: DeviceConnectionType,
    config_entry: ConfigEntry,
) -> None:
    """Create or update device in config_entry according to given device_connection."""
    address = (
        device_connection.seg_id,
        device_connection.addr_id,
        device_connection.is_group,
    )

    data = deepcopy(dict(config_entry.data))
    for device_config in data[CONF_DEVICES]:
        if tuple(device_config[CONF_ADDRESS]) == address:
            break  # device already in config_entry
    else:
        # create new device_entry
        device_config = {
            CONF_ADDRESS: address,
            CONF_NAME: "",
            CONF_HARDWARE_SERIAL: -1,
            CONF_SOFTWARE_SERIAL: -1,
            CONF_HARDWARE_TYPE: -1,
        }
        data[CONF_DEVICES].append(device_config)

    # update device_entry
    await async_update_device_config(device_connection, device_config)

    hass.config_entries.async_update_entry(config_entry, data=data)

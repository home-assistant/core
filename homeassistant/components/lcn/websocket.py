"""LCN Websocket API."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from functools import wraps
from typing import TYPE_CHECKING, Any, Final

import lcn_frontend as lcn_panel
import voluptuous as vol

from homeassistant.components import panel_custom, websocket_api
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.websocket_api import AsyncWebSocketCommandHandler
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_DEVICES,
    CONF_DOMAIN,
    CONF_ENTITIES,
    CONF_NAME,
    CONF_RESOURCE,
)
from homeassistant.core import HomeAssistant, callback
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

if TYPE_CHECKING:
    from homeassistant.components.websocket_api import ActiveConnection

type AsyncLcnWebSocketCommandHandler = Callable[
    [HomeAssistant, ActiveConnection, dict[str, Any], ConfigEntry], Awaitable[None]
]

URL_BASE: Final = "/lcn_static"


async def register_panel_and_ws_api(hass: HomeAssistant) -> None:
    """Register the LCN Panel and Websocket API."""
    websocket_api.async_register_command(hass, websocket_get_device_configs)
    websocket_api.async_register_command(hass, websocket_get_entity_configs)
    websocket_api.async_register_command(hass, websocket_scan_devices)
    websocket_api.async_register_command(hass, websocket_add_device)
    websocket_api.async_register_command(hass, websocket_delete_device)
    websocket_api.async_register_command(hass, websocket_add_entity)
    websocket_api.async_register_command(hass, websocket_delete_entity)

    if DOMAIN not in hass.data.get("frontend_panels", {}):
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(
                    URL_BASE,
                    path=lcn_panel.locate_dir(),
                    cache_headers=lcn_panel.is_prod_build,
                )
            ]
        )
        await panel_custom.async_register_panel(
            hass=hass,
            frontend_url_path=DOMAIN,
            webcomponent_name=lcn_panel.webcomponent_name,
            config_panel_domain=DOMAIN,
            module_url=f"{URL_BASE}/{lcn_panel.entrypoint_js}",
            embed_iframe=True,
            require_admin=True,
        )


def get_config_entry(
    func: AsyncLcnWebSocketCommandHandler,
) -> AsyncWebSocketCommandHandler:
    """Websocket decorator to ensure the config_entry exists and return it."""

    @callback
    @wraps(func)
    async def get_entry(
        hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
    ) -> None:
        """Get config_entry."""
        if not (config_entry := hass.config_entries.async_get_entry(msg["entry_id"])):
            connection.send_result(msg["id"], False)
        else:
            await func(hass, connection, msg, config_entry)

    return get_entry


@websocket_api.require_admin
@websocket_api.websocket_command(
    {vol.Required("type"): "lcn/devices", vol.Required("entry_id"): cv.string}
)
@websocket_api.async_response
@get_config_entry
async def websocket_get_device_configs(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
    config_entry: ConfigEntry,
) -> None:
    """Get device configs."""
    connection.send_result(msg["id"], config_entry.data[CONF_DEVICES])


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "lcn/entities",
        vol.Required("entry_id"): cv.string,
        vol.Optional(CONF_ADDRESS): ADDRESS_SCHEMA,
    }
)
@websocket_api.async_response
@get_config_entry
async def websocket_get_entity_configs(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
    config_entry: ConfigEntry,
) -> None:
    """Get entities configs."""
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
    {vol.Required("type"): "lcn/devices/scan", vol.Required("entry_id"): cv.string}
)
@websocket_api.async_response
@get_config_entry
async def websocket_scan_devices(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
    config_entry: ConfigEntry,
) -> None:
    """Scan for new devices."""
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
        vol.Required("entry_id"): cv.string,
        vol.Required(CONF_ADDRESS): ADDRESS_SCHEMA,
    }
)
@websocket_api.async_response
@get_config_entry
async def websocket_add_device(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
    config_entry: ConfigEntry,
) -> None:
    """Add a device."""
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
    device_configs = [*config_entry.data[CONF_DEVICES], device_config]
    data = {**config_entry.data, CONF_DEVICES: device_configs}
    hass.config_entries.async_update_entry(config_entry, data=data)

    # create/update devices in device registry
    register_lcn_address_devices(hass, config_entry)

    connection.send_result(msg["id"], True)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "lcn/devices/delete",
        vol.Required("entry_id"): cv.string,
        vol.Required(CONF_ADDRESS): ADDRESS_SCHEMA,
    }
)
@websocket_api.async_response
@get_config_entry
async def websocket_delete_device(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
    config_entry: ConfigEntry,
) -> None:
    """Delete a device."""
    device_config = get_device_config(msg[CONF_ADDRESS], config_entry)

    device_registry = dr.async_get(hass)
    identifiers = {
        (DOMAIN, generate_unique_id(config_entry.entry_id, msg[CONF_ADDRESS]))
    }
    device = device_registry.async_get_device(identifiers, set())

    if not (device and device_config):
        connection.send_result(msg["id"], False)
        return

    # remove module/group device from config_entry data
    device_configs = [
        dc for dc in config_entry.data[CONF_DEVICES] if dc != device_config
    ]
    data = {**config_entry.data, CONF_DEVICES: device_configs}
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
        vol.Required("entry_id"): cv.string,
        vol.Required(CONF_ADDRESS): ADDRESS_SCHEMA,
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_DOMAIN): cv.string,
        vol.Required(CONF_DOMAIN_DATA): vol.Any(
            DOMAIN_DATA_BINARY_SENSOR,
            DOMAIN_DATA_SENSOR,
            DOMAIN_DATA_SWITCH,
            DOMAIN_DATA_LIGHT,
            DOMAIN_DATA_CLIMATE,
            DOMAIN_DATA_COVER,
            DOMAIN_DATA_SCENE,
        ),
    }
)
@websocket_api.async_response
@get_config_entry
async def websocket_add_entity(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
    config_entry: ConfigEntry,
) -> None:
    """Add an entity."""
    if not (device_config := get_device_config(msg[CONF_ADDRESS], config_entry)):
        connection.send_result(msg["id"], False)
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
    add_entities = hass.data[DOMAIN][msg["entry_id"]][ADD_ENTITIES_CALLBACKS][
        msg[CONF_DOMAIN]
    ]
    add_entities([entity_config])

    # Add entity config to config_entry
    entity_configs = [*config_entry.data[CONF_ENTITIES], entity_config]
    data = {**config_entry.data, CONF_ENTITIES: entity_configs}

    # schedule config_entry for save
    hass.config_entries.async_update_entry(config_entry, data=data)

    connection.send_result(msg["id"], True)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "lcn/entities/delete",
        vol.Required("entry_id"): cv.string,
        vol.Required(CONF_ADDRESS): ADDRESS_SCHEMA,
        vol.Required(CONF_DOMAIN): cv.string,
        vol.Required(CONF_RESOURCE): cv.string,
    }
)
@websocket_api.async_response
@get_config_entry
async def websocket_delete_entity(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
    config_entry: ConfigEntry,
) -> None:
    """Delete an entity."""
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

    if entity_config is None:
        connection.send_result(msg["id"], False)
        return

    entity_configs = [
        ec for ec in config_entry.data[CONF_ENTITIES] if ec != entity_config
    ]
    data = {**config_entry.data, CONF_ENTITIES: entity_configs}

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

    device_configs = [*config_entry.data[CONF_DEVICES]]
    data = {**config_entry.data, CONF_DEVICES: device_configs}
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

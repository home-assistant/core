"""deCONZ services."""

import asyncio

from pydeconz.utils import normalize_bridge_id
import voluptuous as vol

from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.entity_registry import (
    async_entries_for_config_entry,
    async_entries_for_device,
)

from .config_flow import get_master_gateway
from .const import (
    CONF_BRIDGE_ID,
    DOMAIN,
    LOGGER,
    NEW_GROUP,
    NEW_LIGHT,
    NEW_SCENE,
    NEW_SENSOR,
)

DECONZ_SERVICES = "deconz_services"

SERVICE_FIELD = "field"
SERVICE_ENTITY = "entity"
SERVICE_DATA = "data"

SERVICE_CONFIGURE_DEVICE = "configure"
SERVICE_CONFIGURE_DEVICE_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Optional(SERVICE_ENTITY): cv.entity_id,
            vol.Optional(SERVICE_FIELD): cv.matches_regex("/.*"),
            vol.Required(SERVICE_DATA): dict,
            vol.Optional(CONF_BRIDGE_ID): str,
        }
    ),
    cv.has_at_least_one_key(SERVICE_ENTITY, SERVICE_FIELD),
)

SERVICE_DEVICE_REFRESH = "device_refresh"
SERVICE_REMOVE_ORPHANED_ENTRIES = "remove_orphaned_entries"
SELECT_GATEWAY_SCHEMA = vol.All(vol.Schema({vol.Optional(CONF_BRIDGE_ID): str}))


async def async_setup_services(hass):
    """Set up services for deCONZ integration."""
    if hass.data.get(DECONZ_SERVICES, False):
        return

    hass.data[DECONZ_SERVICES] = True

    async def async_call_deconz_service(service_call):
        """Call correct deCONZ service."""
        service = service_call.service
        service_data = service_call.data

        gateway = get_master_gateway(hass)
        if CONF_BRIDGE_ID in service_data:
            found_gateway = False
            bridge_id = normalize_bridge_id(service_data[CONF_BRIDGE_ID])

            for possible_gateway in hass.data[DOMAIN].values():
                if possible_gateway.bridgeid == bridge_id:
                    gateway = possible_gateway
                    found_gateway = True
                    break

            if not found_gateway:
                LOGGER.error("Could not find the gateway %s", bridge_id)
                return

        if service == SERVICE_CONFIGURE_DEVICE:
            await async_configure_service(gateway, service_data)

        elif service == SERVICE_DEVICE_REFRESH:
            await async_refresh_devices_service(gateway)

        elif service == SERVICE_REMOVE_ORPHANED_ENTRIES:
            await async_remove_orphaned_entries_service(gateway)

    hass.services.async_register(
        DOMAIN,
        SERVICE_CONFIGURE_DEVICE,
        async_call_deconz_service,
        schema=SERVICE_CONFIGURE_DEVICE_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_DEVICE_REFRESH,
        async_call_deconz_service,
        schema=SELECT_GATEWAY_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_REMOVE_ORPHANED_ENTRIES,
        async_call_deconz_service,
        schema=SELECT_GATEWAY_SCHEMA,
    )


async def async_unload_services(hass):
    """Unload deCONZ services."""
    if not hass.data.get(DECONZ_SERVICES):
        return

    hass.data[DECONZ_SERVICES] = False

    hass.services.async_remove(DOMAIN, SERVICE_CONFIGURE_DEVICE)
    hass.services.async_remove(DOMAIN, SERVICE_DEVICE_REFRESH)
    hass.services.async_remove(DOMAIN, SERVICE_REMOVE_ORPHANED_ENTRIES)


async def async_configure_service(gateway, data):
    """Set attribute of device in deCONZ.

    Entity is used to resolve to a device path (e.g. '/lights/1').
    Field is a string representing either a full path
    (e.g. '/lights/1/state') when entity is not specified, or a
    subpath (e.g. '/state') when used together with entity.
    Data is a json object with what data you want to alter
    e.g. data={'on': true}.
    {
        "field": "/lights/1/state",
        "data": {"on": true}
    }
    See Dresden Elektroniks REST API documentation for details:
    http://dresden-elektronik.github.io/deconz-rest-doc/rest/
    """
    field = data.get(SERVICE_FIELD, "")
    entity_id = data.get(SERVICE_ENTITY)
    data = data[SERVICE_DATA]

    if entity_id:
        try:
            field = gateway.deconz_ids[entity_id] + field
        except KeyError:
            LOGGER.error("Could not find the entity %s", entity_id)
            return

    await gateway.api.request("put", field, json=data)


async def async_refresh_devices_service(gateway):
    """Refresh available devices from deCONZ."""
    gateway.ignore_state_updates = True
    await gateway.api.refresh_state()
    gateway.ignore_state_updates = False

    for new_device_type in [NEW_GROUP, NEW_LIGHT, NEW_SCENE, NEW_SENSOR]:
        gateway.async_add_device_callback(new_device_type, force=True)


async def async_remove_orphaned_entries_service(gateway):
    """Remove orphaned deCONZ entries from device and entity registries."""
    device_registry, entity_registry = await asyncio.gather(
        gateway.hass.helpers.device_registry.async_get_registry(),
        gateway.hass.helpers.entity_registry.async_get_registry(),
    )

    entity_entries = async_entries_for_config_entry(
        entity_registry, gateway.config_entry.entry_id
    )

    entities_to_be_removed = []
    devices_to_be_removed = [
        entry.id
        for entry in device_registry.devices.values()
        if gateway.config_entry.entry_id in entry.config_entries
    ]

    # Don't remove the Gateway host entry
    gateway_host = device_registry.async_get_device(
        connections={(CONNECTION_NETWORK_MAC, gateway.api.config.mac)},
        identifiers=set(),
    )
    if gateway_host.id in devices_to_be_removed:
        devices_to_be_removed.remove(gateway_host.id)

    # Don't remove the Gateway service entry
    gateway_service = device_registry.async_get_device(
        identifiers={(DOMAIN, gateway.api.config.bridgeid)}, connections=set()
    )
    if gateway_service.id in devices_to_be_removed:
        devices_to_be_removed.remove(gateway_service.id)

    # Don't remove devices belonging to available events
    for event in gateway.events:
        if event.device_id in devices_to_be_removed:
            devices_to_be_removed.remove(event.device_id)

    for entry in entity_entries:

        # Don't remove available entities
        if entry.unique_id in gateway.entities[entry.domain]:

            # Don't remove devices with available entities
            if entry.device_id in devices_to_be_removed:
                devices_to_be_removed.remove(entry.device_id)
            continue
        # Remove entities that are not available
        entities_to_be_removed.append(entry.entity_id)

    # Remove unavailable entities
    for entity_id in entities_to_be_removed:
        entity_registry.async_remove(entity_id)

    # Remove devices that don't belong to any entity
    for device_id in devices_to_be_removed:
        if (
            len(
                async_entries_for_device(
                    entity_registry, device_id, include_disabled_entities=True
                )
            )
            == 0
        ):
            device_registry.async_remove_device(device_id)

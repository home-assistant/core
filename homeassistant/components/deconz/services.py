"""deCONZ services."""
from pydeconz.utils import normalize_bridge_id
import voluptuous as vol

from homeassistant.helpers import config_validation as cv

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
SERVICE_DEVICE_REFRESH_SCHEMA = vol.All(vol.Schema({vol.Optional(CONF_BRIDGE_ID): str}))


async def async_setup_services(hass):
    """Set up services for deCONZ integration."""
    if hass.data.get(DECONZ_SERVICES, False):
        return

    hass.data[DECONZ_SERVICES] = True

    async def async_call_deconz_service(service_call):
        """Call correct deCONZ service."""
        service = service_call.service
        service_data = service_call.data

        if service == SERVICE_CONFIGURE_DEVICE:
            await async_configure_service(hass, service_data)

        elif service == SERVICE_DEVICE_REFRESH:
            await async_refresh_devices_service(hass, service_data)

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
        schema=SERVICE_DEVICE_REFRESH_SCHEMA,
    )


async def async_unload_services(hass):
    """Unload deCONZ services."""
    if not hass.data.get(DECONZ_SERVICES):
        return

    hass.data[DECONZ_SERVICES] = False

    hass.services.async_remove(DOMAIN, SERVICE_CONFIGURE_DEVICE)
    hass.services.async_remove(DOMAIN, SERVICE_DEVICE_REFRESH)


async def async_configure_service(hass, data):
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
    gateway = get_master_gateway(hass)
    if CONF_BRIDGE_ID in data:
        gateway = hass.data[DOMAIN][normalize_bridge_id(data[CONF_BRIDGE_ID])]

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


async def async_refresh_devices_service(hass, data):
    """Refresh available devices from deCONZ."""
    gateway = get_master_gateway(hass)
    if CONF_BRIDGE_ID in data:
        gateway = hass.data[DOMAIN][normalize_bridge_id(data[CONF_BRIDGE_ID])]

    groups = set(gateway.api.groups.keys())
    lights = set(gateway.api.lights.keys())
    scenes = set(gateway.api.scenes.keys())
    sensors = set(gateway.api.sensors.keys())

    await gateway.api.refresh_state(ignore_update=True)

    gateway.async_add_device_callback(
        NEW_GROUP,
        [
            group
            for group_id, group in gateway.api.groups.items()
            if group_id not in groups
        ],
    )

    gateway.async_add_device_callback(
        NEW_LIGHT,
        [
            light
            for light_id, light in gateway.api.lights.items()
            if light_id not in lights
        ],
    )

    gateway.async_add_device_callback(
        NEW_SCENE,
        [
            scene
            for scene_id, scene in gateway.api.scenes.items()
            if scene_id not in scenes
        ],
    )

    gateway.async_add_device_callback(
        NEW_SENSOR,
        [
            sensor
            for sensor_id, sensor in gateway.api.sensors.items()
            if sensor_id not in sensors
        ],
    )

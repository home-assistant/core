"""Support for deCONZ devices."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_API_KEY, CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_STOP)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC

# Loading the config flow file will register the flow
from .config_flow import configured_hosts
from .const import DEFAULT_PORT, DOMAIN, _LOGGER
from .gateway import DeconzGateway

REQUIREMENTS = ['pydeconz==54']

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_API_KEY): cv.string,
        vol.Optional(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    })
}, extra=vol.ALLOW_EXTRA)

SERVICE_DECONZ = 'configure'

SERVICE_FIELD = 'field'
SERVICE_ENTITY = 'entity'
SERVICE_DATA = 'data'

SERVICE_SCHEMA = vol.All(vol.Schema({
    vol.Optional(SERVICE_ENTITY): cv.entity_id,
    vol.Optional(SERVICE_FIELD): cv.matches_regex('/.*'),
    vol.Required(SERVICE_DATA): dict,
}), cv.has_at_least_one_key(SERVICE_ENTITY, SERVICE_FIELD))

SERVICE_DEVICE_REFRESH = 'device_refresh'


async def async_setup(hass, config):
    """Load configuration for deCONZ component.

    Discovery has loaded the component if DOMAIN is not present in config.
    """
    if DOMAIN in config:
        deconz_config = None
        if CONF_HOST in config[DOMAIN]:
            deconz_config = config[DOMAIN]
        if deconz_config and not configured_hosts(hass):
            hass.async_add_job(hass.config_entries.flow.async_init(
                DOMAIN,
                context={'source': config_entries.SOURCE_IMPORT},
                data=deconz_config
            ))
    return True


async def async_setup_entry(hass, config_entry):
    """Set up a deCONZ bridge for a config entry.

    Load config, group, light and sensor data for server information.
    Start websocket for push notification of state changes from deCONZ.
    """
    if DOMAIN in hass.data:
        _LOGGER.error(
            "Config entry failed since one deCONZ instance already exists")
        return False

    gateway = DeconzGateway(hass, config_entry)

    if not await gateway.async_setup():
        return False

    hass.data[DOMAIN] = gateway

    device_registry = await \
        hass.helpers.device_registry.async_get_registry()
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(CONNECTION_NETWORK_MAC, gateway.api.config.mac)},
        identifiers={(DOMAIN, gateway.api.config.bridgeid)},
        manufacturer='Dresden Elektronik', model=gateway.api.config.modelid,
        name=gateway.api.config.name, sw_version=gateway.api.config.swversion)

    async def async_configure(call):
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
        field = call.data.get(SERVICE_FIELD, '')
        entity_id = call.data.get(SERVICE_ENTITY)
        data = call.data.get(SERVICE_DATA)
        gateway = hass.data[DOMAIN]

        if entity_id:
            try:
                field = gateway.deconz_ids[entity_id] + field
            except KeyError:
                _LOGGER.error('Could not find the entity %s', entity_id)
                return

        await gateway.api.async_put_state(field, data)

    hass.services.async_register(
        DOMAIN, SERVICE_DECONZ, async_configure, schema=SERVICE_SCHEMA)

    async def async_refresh_devices(call):
        """Refresh available devices from deCONZ."""
        gateway = hass.data[DOMAIN]

        groups = set(gateway.api.groups.keys())
        lights = set(gateway.api.lights.keys())
        scenes = set(gateway.api.scenes.keys())
        sensors = set(gateway.api.sensors.keys())

        await gateway.api.async_load_parameters()

        gateway.async_add_device_callback(
            'group', [group
                      for group_id, group in gateway.api.groups.items()
                      if group_id not in groups]
        )

        gateway.async_add_device_callback(
            'light', [light
                      for light_id, light in gateway.api.lights.items()
                      if light_id not in lights]
        )

        gateway.async_add_device_callback(
            'scene', [scene
                      for scene_id, scene in gateway.api.scenes.items()
                      if scene_id not in scenes]
        )

        gateway.async_add_device_callback(
            'sensor', [sensor
                       for sensor_id, sensor in gateway.api.sensors.items()
                       if sensor_id not in sensors]
        )

    hass.services.async_register(
        DOMAIN, SERVICE_DEVICE_REFRESH, async_refresh_devices)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, gateway.shutdown)
    return True


async def async_unload_entry(hass, config_entry):
    """Unload deCONZ config entry."""
    gateway = hass.data.pop(DOMAIN)
    hass.services.async_remove(DOMAIN, SERVICE_DECONZ)
    hass.services.async_remove(DOMAIN, SERVICE_DEVICE_REFRESH)
    return await gateway.async_reset()

"""Support for deCONZ devices."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_API_KEY, CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_STOP)
from homeassistant.helpers import config_validation as cv

# Loading the config flow file will register the flow
from .config_flow import get_master_gateway
from .const import (
    CONF_ALLOW_CLIP_SENSOR, CONF_ALLOW_DECONZ_GROUPS, CONF_BRIDGEID,
    CONF_MASTER_GATEWAY, DEFAULT_PORT, DOMAIN, _LOGGER)
from .gateway import DeconzGateway

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
    vol.Optional(CONF_BRIDGEID): str
}), cv.has_at_least_one_key(SERVICE_ENTITY, SERVICE_FIELD))

SERVICE_DEVICE_REFRESH = 'device_refresh'

SERVICE_DEVICE_REFRESCH_SCHEMA = vol.All(vol.Schema({
    vol.Optional(CONF_BRIDGEID): str
}))


async def async_setup(hass, config):
    """Load configuration for deCONZ component.

    Discovery has loaded the component if DOMAIN is not present in config.
    """
    if not hass.config_entries.async_entries(DOMAIN) and DOMAIN in config:
        deconz_config = config[DOMAIN]
        hass.async_create_task(hass.config_entries.flow.async_init(
            DOMAIN, context={'source': config_entries.SOURCE_IMPORT},
            data=deconz_config
        ))
    return True


async def async_setup_entry(hass, config_entry):
    """Set up a deCONZ bridge for a config entry.

    Load config, group, light and sensor data for server information.
    Start websocket for push notification of state changes from deCONZ.
    """
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    if not config_entry.options:
        await async_populate_options(hass, config_entry)

    gateway = DeconzGateway(hass, config_entry)

    if not await gateway.async_setup():
        return False

    hass.data[DOMAIN][gateway.bridgeid] = gateway

    await gateway.async_update_device_registry()

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
        data = call.data[SERVICE_DATA]

        gateway = get_master_gateway(hass)
        if CONF_BRIDGEID in call.data:
            gateway = hass.data[DOMAIN][call.data[CONF_BRIDGEID]]

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
        gateway = get_master_gateway(hass)
        if CONF_BRIDGEID in call.data:
            gateway = hass.data[DOMAIN][call.data[CONF_BRIDGEID]]

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
        DOMAIN, SERVICE_DEVICE_REFRESH, async_refresh_devices,
        schema=SERVICE_DEVICE_REFRESCH_SCHEMA)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, gateway.shutdown)
    return True


async def async_unload_entry(hass, config_entry):
    """Unload deCONZ config entry."""
    gateway = hass.data[DOMAIN].pop(config_entry.data[CONF_BRIDGEID])

    if not hass.data[DOMAIN]:
        hass.services.async_remove(DOMAIN, SERVICE_DECONZ)
        hass.services.async_remove(DOMAIN, SERVICE_DEVICE_REFRESH)
    elif gateway.master:
        await async_populate_options(hass, config_entry)
        new_master_gateway = next(iter(hass.data[DOMAIN].values()))
        await async_populate_options(hass, new_master_gateway.config_entry)

    return await gateway.async_reset()


async def async_populate_options(hass, config_entry):
    """Populate default options for gateway.

    Called by setup_entry and unload_entry.
    Makes sure there is always one master available.
    """
    master = not get_master_gateway(hass)

    options = {
        CONF_MASTER_GATEWAY: master,
        CONF_ALLOW_CLIP_SENSOR: config_entry.data.get(
            CONF_ALLOW_CLIP_SENSOR, False),
        CONF_ALLOW_DECONZ_GROUPS: config_entry.data.get(
            CONF_ALLOW_DECONZ_GROUPS, True)
    }

    hass.config_entries.async_update_entry(config_entry, options=options)

"""
Support for deCONZ devices.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/deconz/
"""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_API_KEY, CONF_EVENT, CONF_HOST,
    CONF_ID, CONF_PORT, EVENT_HOMEASSISTANT_STOP)
from homeassistant.core import EventOrigin, callback
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect, async_dispatcher_send)
from homeassistant.util import slugify
from homeassistant.util.json import load_json

# Loading the config flow file will register the flow
from .config_flow import configured_hosts
from .const import (
    CONF_ALLOW_CLIP_SENSOR, CONFIG_FILE, DATA_DECONZ_EVENT,
    DATA_DECONZ_ID, DATA_DECONZ_UNSUB, DOMAIN, _LOGGER)

REQUIREMENTS = ['pydeconz==47']

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_API_KEY): cv.string,
        vol.Optional(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=80): cv.port,
    })
}, extra=vol.ALLOW_EXTRA)

SERVICE_DECONZ = 'configure'

SERVICE_FIELD = 'field'
SERVICE_ENTITY = 'entity'
SERVICE_DATA = 'data'

SERVICE_SCHEMA = vol.Schema({
    vol.Exclusive(SERVICE_FIELD, 'deconz_id'): cv.string,
    vol.Exclusive(SERVICE_ENTITY, 'deconz_id'): cv.entity_id,
    vol.Required(SERVICE_DATA): dict,
})

SERVICE_DEVICE_REFRESH = 'device_refresh'


async def async_setup(hass, config):
    """Load configuration for deCONZ component.

    Discovery has loaded the component if DOMAIN is not present in config.
    """
    if DOMAIN in config:
        deconz_config = None
        config_file = await hass.async_add_job(
            load_json, hass.config.path(CONFIG_FILE))
        if config_file:
            deconz_config = config_file
        elif CONF_HOST in config[DOMAIN]:
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
    from pydeconz import DeconzSession
    if DOMAIN in hass.data:
        _LOGGER.error(
            "Config entry failed since one deCONZ instance already exists")
        return False

    @callback
    def async_add_device_callback(device_type, device):
        """Handle event of new device creation in deCONZ."""
        if not isinstance(device, list):
            device = [device]
        async_dispatcher_send(
            hass, 'deconz_new_{}'.format(device_type), device)

    session = aiohttp_client.async_get_clientsession(hass)
    deconz = DeconzSession(hass.loop, session, **config_entry.data,
                           async_add_device=async_add_device_callback)
    result = await deconz.async_load_parameters()

    if result is False:
        return False

    hass.data[DOMAIN] = deconz
    hass.data[DATA_DECONZ_ID] = {}
    hass.data[DATA_DECONZ_EVENT] = []
    hass.data[DATA_DECONZ_UNSUB] = []

    for component in ['binary_sensor', 'light', 'scene', 'sensor', 'switch']:
        hass.async_create_task(hass.config_entries.async_forward_entry_setup(
            config_entry, component))

    @callback
    def async_add_remote(sensors):
        """Set up remote from deCONZ."""
        from pydeconz.sensor import SWITCH as DECONZ_REMOTE
        allow_clip_sensor = config_entry.data.get(CONF_ALLOW_CLIP_SENSOR, True)
        for sensor in sensors:
            if sensor.type in DECONZ_REMOTE and \
               not (not allow_clip_sensor and sensor.type.startswith('CLIP')):
                hass.data[DATA_DECONZ_EVENT].append(DeconzEvent(hass, sensor))
    hass.data[DATA_DECONZ_UNSUB].append(
        async_dispatcher_connect(hass, 'deconz_new_sensor', async_add_remote))

    async_add_remote(deconz.sensors.values())

    deconz.start()

    device_registry = await \
        hass.helpers.device_registry.async_get_registry()
    device_registry.async_get_or_create(
        config_entry=config_entry.entry_id,
        connections={(CONNECTION_NETWORK_MAC, deconz.config.mac)},
        identifiers={(DOMAIN, deconz.config.bridgeid)},
        manufacturer='Dresden Elektronik', model=deconz.config.modelid,
        name=deconz.config.name, sw_version=deconz.config.swversion)

    async def async_configure(call):
        """Set attribute of device in deCONZ.

        Field is a string representing a specific device in deCONZ
        e.g. field='/lights/1/state'.
        Entity_id can be used to retrieve the proper field.
        Data is a json object with what data you want to alter
        e.g. data={'on': true}.
        {
            "field": "/lights/1/state",
            "data": {"on": true}
        }
        See Dresden Elektroniks REST API documentation for details:
        http://dresden-elektronik.github.io/deconz-rest-doc/rest/
        """
        field = call.data.get(SERVICE_FIELD)
        entity_id = call.data.get(SERVICE_ENTITY)
        data = call.data.get(SERVICE_DATA)
        deconz = hass.data[DOMAIN]
        if entity_id:

            entities = hass.data.get(DATA_DECONZ_ID)

            if entities:
                field = entities.get(entity_id)

            if field is None:
                _LOGGER.error('Could not find the entity %s', entity_id)
                return

        await deconz.async_put_state(field, data)

    hass.services.async_register(
        DOMAIN, SERVICE_DECONZ, async_configure, schema=SERVICE_SCHEMA)

    async def async_refresh_devices(call):
        """Refresh available devices from deCONZ."""
        deconz = hass.data[DOMAIN]

        groups = list(deconz.groups.keys())
        lights = list(deconz.lights.keys())
        scenes = list(deconz.scenes.keys())
        sensors = list(deconz.sensors.keys())

        if not await deconz.async_load_parameters():
            return

        async_add_device_callback(
            'group', [group
                      for group_id, group in deconz.groups.items()
                      if group_id not in groups]
        )

        async_add_device_callback(
            'light', [light
                      for light_id, light in deconz.lights.items()
                      if light_id not in lights]
        )

        async_add_device_callback(
            'scene', [scene
                      for scene_id, scene in deconz.scenes.items()
                      if scene_id not in scenes]
        )

        async_add_device_callback(
            'sensor', [sensor
                       for sensor_id, sensor in deconz.sensors.items()
                       if sensor_id not in sensors]
        )

    hass.services.async_register(
        DOMAIN, SERVICE_DEVICE_REFRESH, async_refresh_devices)

    @callback
    def deconz_shutdown(event):
        """
        Wrap the call to deconz.close.

        Used as an argument to EventBus.async_listen_once - EventBus calls
        this method with the event as the first argument, which should not
        be passed on to deconz.close.
        """
        deconz.close()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, deconz_shutdown)
    return True


async def async_unload_entry(hass, config_entry):
    """Unload deCONZ config entry."""
    deconz = hass.data.pop(DOMAIN)
    hass.services.async_remove(DOMAIN, SERVICE_DECONZ)
    deconz.close()

    for component in ['binary_sensor', 'light', 'scene', 'sensor', 'switch']:
        await hass.config_entries.async_forward_entry_unload(
            config_entry, component)

    dispatchers = hass.data[DATA_DECONZ_UNSUB]
    for unsub_dispatcher in dispatchers:
        unsub_dispatcher()
    hass.data[DATA_DECONZ_UNSUB] = []

    for event in hass.data[DATA_DECONZ_EVENT]:
        event.async_will_remove_from_hass()
        hass.data[DATA_DECONZ_EVENT].remove(event)

    hass.data[DATA_DECONZ_ID] = []

    return True


class DeconzEvent:
    """When you want signals instead of entities.

    Stateless sensors such as remotes are expected to generate an event
    instead of a sensor entity in hass.
    """

    def __init__(self, hass, device):
        """Register callback that will be used for signals."""
        self._hass = hass
        self._device = device
        self._device.register_async_callback(self.async_update_callback)
        self._event = 'deconz_{}'.format(CONF_EVENT)
        self._id = slugify(self._device.name)

    @callback
    def async_will_remove_from_hass(self) -> None:
        """Disconnect event object when removed."""
        self._device.remove_callback(self.async_update_callback)
        self._device = None

    @callback
    def async_update_callback(self, reason):
        """Fire the event if reason is that state is updated."""
        if reason['state']:
            data = {CONF_ID: self._id, CONF_EVENT: self._device.state}
            self._hass.bus.async_fire(self._event, data, EventOrigin.remote)

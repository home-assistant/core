"""Support for Notion."""
import asyncio
import logging

import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import ATTR_ATTRIBUTION, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect, async_dispatcher_send)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval

from .config_flow import configured_instances
from .const import (
    DATA_CLIENT, DEFAULT_SCAN_INTERVAL, DOMAIN, TOPIC_DATA_UPDATE)

_LOGGER = logging.getLogger(__name__)

ATTR_SYSTEM_MODE = 'system_mode'
ATTR_SYSTEM_NAME = 'system_name'

DATA_LISTENER = 'listener'

DEFAULT_ATTRIBUTION = 'Data provided by Notion'

SENSOR_BATTERY = 'low_battery'
SENSOR_DOOR = 'door'
SENSOR_GARAGE_DOOR = 'garage_door'
SENSOR_LEAK = 'leak'
SENSOR_MISSING = 'missing'
SENSOR_SAFE = 'safe'
SENSOR_SLIDING = 'sliding'
SENSOR_SMOKE_CO = 'alarm'
SENSOR_TEMPERATURE = 'temperature'
SENSOR_WINDOW_HINGED_HORIZONTAL = 'window_hinged_horizontal'
SENSOR_WINDOW_HINGED_VERTICAL = 'window_hinged_vertical'

BINARY_SENSOR_TYPES = {
    SENSOR_BATTERY: ('Low Battery', 'battery'),
    SENSOR_DOOR: ('Door', 'door'),
    SENSOR_GARAGE_DOOR: ('Garage Door', 'garage_door'),
    SENSOR_LEAK: ('Leak Detector', 'moisture'),
    SENSOR_MISSING: ('Missing', 'connectivity'),
    SENSOR_SAFE: ('Safe', 'door'),
    SENSOR_SLIDING: ('Sliding Door/Window', 'door'),
    SENSOR_SMOKE_CO: ('Smoke/Carbon Monoxide Detector', 'smoke'),
    SENSOR_WINDOW_HINGED_HORIZONTAL: ('Hinged Window', 'window'),
    SENSOR_WINDOW_HINGED_VERTICAL: ('Hinged Window', 'window'),
}
SENSOR_TYPES = {
    SENSOR_TEMPERATURE: ('Temperature', 'temperature', '°C'),
}

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    })
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the Notion component."""
    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][DATA_CLIENT] = {}
    hass.data[DOMAIN][DATA_LISTENER] = {}

    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]

    if conf[CONF_USERNAME] in configured_instances(hass):
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={'source': SOURCE_IMPORT},
            data={
                CONF_USERNAME: conf[CONF_USERNAME],
                CONF_PASSWORD: conf[CONF_PASSWORD]
            }))

    return True


async def async_setup_entry(hass, config_entry):
    """Set up Notion as a config entry."""
    from aionotion import async_get_client
    from aionotion.errors import NotionError

    session = aiohttp_client.async_get_clientsession(hass)

    try:
        client = await async_get_client(
            config_entry.data[CONF_USERNAME],
            config_entry.data[CONF_PASSWORD],
            session)
    except NotionError as err:
        _LOGGER.error('Config entry failed: %s', err)
        raise ConfigEntryNotReady

    notion = Notion(client)
    await notion.async_update(initialize=True)
    hass.data[DOMAIN][DATA_CLIENT][config_entry.entry_id] = notion

    for component in ('binary_sensor', 'sensor'):
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(
                config_entry, component))

    async def refresh(event_time):
        """Refresh Notion sensor data."""
        _LOGGER.debug('Refreshing Notion sensor data')
        await notion.async_update()
        async_dispatcher_send(hass, TOPIC_DATA_UPDATE)

    hass.data[DOMAIN][DATA_LISTENER][
        config_entry.entry_id] = async_track_time_interval(
            hass,
            refresh,
            DEFAULT_SCAN_INTERVAL)

    return True


async def async_unload_entry(hass, config_entry):
    """Unload a Notion config entry."""
    hass.data[DOMAIN][DATA_CLIENT].pop(config_entry.entry_id)
    cancel = hass.data[DOMAIN][DATA_LISTENER].pop(config_entry.entry_id)
    cancel()

    for component in ('binary_sensor', 'sensor'):
        await hass.config_entries.async_forward_entry_unload(
            config_entry, component)

    return True


class Notion:
    """Define a class to handle the Notion API."""

    def __init__(self, client):
        """Initialize."""
        self._client = client
        self.bridges = []
        self.sensors = []
        self.systems = []
        self.tasks = []

    async def async_update(self, *, initialize=False):
        """Get the latest Notion data."""
        from aionotion.errors import NotionError

        tasks = {
            'bridges': self._client.bridge.async_all(),
            'sensors': self._client.sensor.async_all(),
            'tasks': self._client.task.async_all(),
        }
        if initialize:
            tasks['systems'] = self._client.system.async_all()

        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        for attr, result in zip(tasks, results):
            if isinstance(result, NotionError):
                _LOGGER.error(
                    'There was an error while updating %s: %s', attr, result)
                continue

            setattr(self, attr, result)


class NotionEntity(Entity):
    """Define a base Notion entity."""

    def __init__(
            self,
            notion,
            task,
            sensor,
            bridge,
            system,
            name,
            device_class):
        """Initialize the entity."""
        self._async_unsub_dispatcher_connect = None
        self._attrs = {ATTR_ATTRIBUTION: DEFAULT_ATTRIBUTION}
        self._bridge = bridge
        self._device_class = device_class
        self._name = name
        self._notion = notion
        self._sensor = sensor
        self._state = None
        self._system = system
        self._task = task

    @property
    def available(self):
        """Return True if entity is available."""
        return any(self._task['id'] == t['id'] for t in self._notion.tasks)

    @property
    def device_class(self):
        """Return the device class."""
        return self._device_class

    @property
    def device_state_attributes(self) -> dict:
        """Return the state attributes."""
        return self._attrs

    @property
    def device_info(self):
        """Return device registry information for this entity."""
        return {
            'identifiers': {
                (DOMAIN, self._sensor['hardware_id'])
            },
            'manufacturer': 'Notion',
            'model': self._sensor['hardware_revision'],
            'name': self._sensor['name'],
            'sw_version': self._sensor['firmware_version'],
            'via_device': (DOMAIN, self._bridge['hardware_id'])
        }

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{0}: {1}'.format(self._sensor['name'], self._name)

    @property
    def should_poll(self):
        """Disable entity polling."""
        return False

    @property
    def unique_id(self):
        """Return a unique, unchanging string that represents this sensor."""
        return self._task['id']

    async def async_added_to_hass(self):
        """Register callbacks."""
        @callback
        def update():
            """Update the state."""
            self.async_schedule_update_ha_state(True)

        self._async_unsub_dispatcher_connect = async_dispatcher_connect(
            self.hass, TOPIC_DATA_UPDATE, update)

    async def async_will_remove_from_hass(self):
        """Disconnect dispatcher listener when removed."""
        if self._async_unsub_dispatcher_connect:
            self._async_unsub_dispatcher_connect()

"""
Support for RainMachine devices.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/rainmachine/
"""
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.const import (
    ATTR_ATTRIBUTION, CONF_BINARY_SENSORS, CONF_IP_ADDRESS, CONF_PASSWORD,
    CONF_PORT, CONF_SCAN_INTERVAL, CONF_SENSORS, CONF_SSL,
    CONF_MONITORED_CONDITIONS, CONF_SWITCHES)
from homeassistant.helpers import (
    aiohttp_client, config_validation as cv, discovery)
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval

REQUIREMENTS = ['regenmaschine==1.0.2']

_LOGGER = logging.getLogger(__name__)

DATA_RAINMACHINE = 'data_rainmachine'
DOMAIN = 'rainmachine'

NOTIFICATION_ID = 'rainmachine_notification'
NOTIFICATION_TITLE = 'RainMachine Component Setup'

PROGRAM_UPDATE_TOPIC = '{0}_program_update'.format(DOMAIN)
SENSOR_UPDATE_TOPIC = '{0}_data_update'.format(DOMAIN)
ZONE_UPDATE_TOPIC = '{0}_zone_update'.format(DOMAIN)

CONF_PROGRAM_ID = 'program_id'
CONF_ZONE_ID = 'zone_id'
CONF_ZONE_RUN_TIME = 'zone_run_time'

DEFAULT_ATTRIBUTION = 'Data provided by Green Electronics LLC'
DEFAULT_ICON = 'mdi:water'
DEFAULT_PORT = 8080
DEFAULT_SCAN_INTERVAL = timedelta(seconds=60)
DEFAULT_SSL = True
DEFAULT_ZONE_RUN = 60 * 10

TYPE_FREEZE = 'freeze'
TYPE_FREEZE_PROTECTION = 'freeze_protection'
TYPE_FREEZE_TEMP = 'freeze_protect_temp'
TYPE_HOT_DAYS = 'extra_water_on_hot_days'
TYPE_HOURLY = 'hourly'
TYPE_MONTH = 'month'
TYPE_RAINDELAY = 'raindelay'
TYPE_RAINSENSOR = 'rainsensor'
TYPE_WEEKDAY = 'weekday'

BINARY_SENSORS = {
    TYPE_FREEZE: ('Freeze Restrictions', 'mdi:cancel'),
    TYPE_FREEZE_PROTECTION: ('Freeze Protection', 'mdi:weather-snowy'),
    TYPE_HOT_DAYS: ('Extra Water on Hot Days', 'mdi:thermometer-lines'),
    TYPE_HOURLY: ('Hourly Restrictions', 'mdi:cancel'),
    TYPE_MONTH: ('Month Restrictions', 'mdi:cancel'),
    TYPE_RAINDELAY: ('Rain Delay Restrictions', 'mdi:cancel'),
    TYPE_RAINSENSOR: ('Rain Sensor Restrictions', 'mdi:cancel'),
    TYPE_WEEKDAY: ('Weekday Restrictions', 'mdi:cancel'),
}

SENSORS = {
    TYPE_FREEZE_TEMP: ('Freeze Protect Temperature', 'mdi:thermometer', '°C'),
}

BINARY_SENSOR_SCHEMA = vol.Schema({
    vol.Optional(CONF_MONITORED_CONDITIONS, default=list(BINARY_SENSORS)):
        vol.All(cv.ensure_list, [vol.In(BINARY_SENSORS)])
})

SENSOR_SCHEMA = vol.Schema({
    vol.Optional(CONF_MONITORED_CONDITIONS, default=list(SENSORS)):
        vol.All(cv.ensure_list, [vol.In(SENSORS)])
})

SERVICE_START_PROGRAM_SCHEMA = vol.Schema({
    vol.Required(CONF_PROGRAM_ID): cv.positive_int,
})

SERVICE_START_ZONE_SCHEMA = vol.Schema({
    vol.Required(CONF_ZONE_ID): cv.positive_int,
    vol.Optional(CONF_ZONE_RUN_TIME, default=DEFAULT_ZONE_RUN):
        cv.positive_int,
})

SERVICE_STOP_PROGRAM_SCHEMA = vol.Schema({
    vol.Required(CONF_PROGRAM_ID): cv.positive_int,
})

SERVICE_STOP_ZONE_SCHEMA = vol.Schema({
    vol.Required(CONF_ZONE_ID): cv.positive_int,
})

SWITCH_SCHEMA = vol.Schema({vol.Optional(CONF_ZONE_RUN_TIME): cv.positive_int})

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN:
        vol.Schema({
            vol.Required(CONF_IP_ADDRESS): cv.string,
            vol.Required(CONF_PASSWORD): cv.string,
            vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
            vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
            vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL):
                cv.time_period,
            vol.Optional(CONF_BINARY_SENSORS, default={}):
                BINARY_SENSOR_SCHEMA,
            vol.Optional(CONF_SENSORS, default={}): SENSOR_SCHEMA,
            vol.Optional(CONF_SWITCHES, default={}): SWITCH_SCHEMA,
        })
    },
    extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the RainMachine component."""
    from regenmaschine import Client
    from regenmaschine.errors import RequestError

    conf = config[DOMAIN]
    ip_address = conf[CONF_IP_ADDRESS]
    password = conf[CONF_PASSWORD]
    port = conf[CONF_PORT]
    ssl = conf[CONF_SSL]

    try:
        websession = aiohttp_client.async_get_clientsession(hass)
        client = Client(ip_address, websession, port=port, ssl=ssl)
        await client.authenticate(password)
        rainmachine = RainMachine(client)
        await rainmachine.async_update()
        hass.data[DATA_RAINMACHINE] = rainmachine
    except RequestError as err:
        _LOGGER.error('An error occurred: %s', str(err))
        hass.components.persistent_notification.create(
            'Error: {0}<br />'
            'You will need to restart hass after fixing.'
            ''.format(err),
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID)
        return False

    for component, schema in [
            ('binary_sensor', conf[CONF_BINARY_SENSORS]),
            ('sensor', conf[CONF_SENSORS]),
            ('switch', conf[CONF_SWITCHES]),
    ]:
        hass.async_create_task(
            discovery.async_load_platform(hass, component, DOMAIN, schema,
                                          config))

    async def refresh_sensors(event_time):
        """Refresh RainMachine sensor data."""
        _LOGGER.debug('Updating RainMachine sensor data')
        await rainmachine.async_update()
        async_dispatcher_send(hass, SENSOR_UPDATE_TOPIC)

    async_track_time_interval(hass, refresh_sensors, conf[CONF_SCAN_INTERVAL])

    async def start_program(service):
        """Start a particular program."""
        await rainmachine.client.programs.start(service.data[CONF_PROGRAM_ID])
        async_dispatcher_send(hass, PROGRAM_UPDATE_TOPIC)

    async def start_zone(service):
        """Start a particular zone for a certain amount of time."""
        await rainmachine.client.zones.start(service.data[CONF_ZONE_ID],
                                             service.data[CONF_ZONE_RUN_TIME])
        async_dispatcher_send(hass, ZONE_UPDATE_TOPIC)

    async def stop_all(service):
        """Stop all watering."""
        await rainmachine.client.watering.stop_all()
        async_dispatcher_send(hass, PROGRAM_UPDATE_TOPIC)

    async def stop_program(service):
        """Stop a program."""
        await rainmachine.client.programs.stop(service.data[CONF_PROGRAM_ID])
        async_dispatcher_send(hass, PROGRAM_UPDATE_TOPIC)

    async def stop_zone(service):
        """Stop a zone."""
        await rainmachine.client.zones.stop(service.data[CONF_ZONE_ID])
        async_dispatcher_send(hass, ZONE_UPDATE_TOPIC)

    for service, method, schema in [
            ('start_program', start_program, SERVICE_START_PROGRAM_SCHEMA),
            ('start_zone', start_zone, SERVICE_START_ZONE_SCHEMA),
            ('stop_all', stop_all, {}),
            ('stop_program', stop_program, SERVICE_STOP_PROGRAM_SCHEMA),
            ('stop_zone', stop_zone, SERVICE_STOP_ZONE_SCHEMA)
    ]:
        hass.services.async_register(DOMAIN, service, method, schema=schema)

    return True


class RainMachine:
    """Define a generic RainMachine object."""

    def __init__(self, client):
        """Initialize."""
        self.client = client
        self.device_mac = self.client.mac
        self.restrictions = {}

    async def async_update(self):
        """Update sensor/binary sensor data."""
        self.restrictions.update({
            'current': await self.client.restrictions.current(),
            'global': await self.client.restrictions.universal()
        })


class RainMachineEntity(Entity):
    """Define a generic RainMachine entity."""

    def __init__(self, rainmachine):
        """Initialize."""
        self._attrs = {ATTR_ATTRIBUTION: DEFAULT_ATTRIBUTION}
        self._name = None
        self.rainmachine = rainmachine

    @property
    def device_state_attributes(self) -> dict:
        """Return the state attributes."""
        return self._attrs

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

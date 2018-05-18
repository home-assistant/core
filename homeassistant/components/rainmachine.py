"""
Support for RainMachine devices.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/rainmachine/
"""
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.components.binary_sensor.rainmachine import (
    SENSORS as BINARY_SENSORS)
from homeassistant.components.sensor.rainmachine import SENSORS
from homeassistant.const import (
    ATTR_ATTRIBUTION, CONF_BINARY_SENSORS, CONF_IP_ADDRESS, CONF_PASSWORD,
    CONF_PORT, CONF_SENSORS, CONF_SSL, CONF_MONITORED_CONDITIONS,
    CONF_SWITCHES)
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import track_time_interval

REQUIREMENTS = ['regenmaschine==0.4.1']

_LOGGER = logging.getLogger(__name__)

DATA_RAINMACHINE = 'data_rainmachine'
DOMAIN = 'rainmachine'

NOTIFICATION_ID = 'rainmachine_notification'
NOTIFICATION_TITLE = 'RainMachine Component Setup'

CONF_PROGRAM_ID = 'program_id'
CONF_ZONE_ID = 'zone_id'
CONF_ZONE_RUN_TIME = 'zone_run_time'

DEFAULT_ATTRIBUTION = 'Data provided by Green Electronics LLC'
DEFAULT_ICON = 'mdi:water'
DEFAULT_PORT = 8080
DEFAULT_SCAN_INTERVAL = timedelta(seconds=60)
DEFAULT_SSL = True
DEFAULT_ZONE_RUN = 60 * 10

DATA_UPDATE_TOPIC = '{0}_data_update'.format(DOMAIN)
PROGRAM_UPDATE_TOPIC = '{0}_program_update'.format(DOMAIN)

BINARY_SENSOR_SCHEMA = vol.Schema({
    vol.Optional(CONF_MONITORED_CONDITIONS):
        vol.All(cv.ensure_list, [vol.In(BINARY_SENSORS)])
})

SENSOR_SCHEMA = vol.Schema({
    vol.Optional(CONF_MONITORED_CONDITIONS):
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

SWITCH_SCHEMA = vol.Schema({
    vol.Optional(CONF_ZONE_RUN_TIME): cv.positive_int
})

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema({
            vol.Required(CONF_IP_ADDRESS): cv.string,
            vol.Required(CONF_PASSWORD): cv.string,
            vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
            vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
            vol.Optional(CONF_BINARY_SENSORS): BINARY_SENSOR_SCHEMA,
            vol.Optional(CONF_SENSORS): SENSOR_SCHEMA,
            vol.Optional(CONF_SWITCHES): SWITCH_SCHEMA,
        })
    },
    extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the RainMachine component."""
    from regenmaschine import Authenticator, Client
    from regenmaschine.exceptions import HTTPError
    from requests.exceptions import ConnectTimeout

    conf = config[DOMAIN]
    ip_address = conf[CONF_IP_ADDRESS]
    password = conf[CONF_PASSWORD]
    port = conf[CONF_PORT]
    ssl = conf[CONF_SSL]

    try:
        auth = Authenticator.create_local(
            ip_address, password, port=port, https=ssl)
        rainmachine = RainMachine(hass, Client(auth))
        rainmachine.update()
        hass.data[DATA_RAINMACHINE] = rainmachine
    except (HTTPError, ConnectTimeout, UnboundLocalError) as exc:
        _LOGGER.error('An error occurred: %s', str(exc))
        hass.components.persistent_notification.create(
            'Error: {0}<br />'
            'You will need to restart hass after fixing.'
            ''.format(exc),
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID)
        return False

    binary_sensor_config = conf.get(CONF_BINARY_SENSORS, {})
    discovery.load_platform(
        hass, 'binary_sensor', DOMAIN, binary_sensor_config, config)

    sensor_config = conf.get(CONF_SENSORS, {})
    discovery.load_platform(
        hass, 'sensor', DOMAIN, sensor_config, config)

    switch_config = conf.get(CONF_SWITCHES, {})
    discovery.load_platform(hass, 'switch', DOMAIN, switch_config, config)

    def refresh(event_time):
        """Refresh RainMachine data."""
        _LOGGER.debug('Updating RainMachine data')
        hass.data[DATA_RAINMACHINE].update()
        dispatcher_send(hass, DATA_UPDATE_TOPIC)

    track_time_interval(hass, refresh, DEFAULT_SCAN_INTERVAL)

    def start_program(service):
        """Start a particular program."""
        rainmachine.client.programs.start(service.data[CONF_PROGRAM_ID])

    def start_zone(service):
        """Start a particular zone for a certain amount of time."""
        rainmachine.client.zones.start(
            service.data[CONF_ZONE_ID], service.data[CONF_ZONE_RUN_TIME])

    def stop_all(service):
        """Stop all watering."""
        rainmachine.client.watering.stop_all()

    def stop_program(service):
        """Stop a program."""
        rainmachine.client.programs.stop(service.data[CONF_PROGRAM_ID])

    def stop_zone(service):
        """Stop a zone."""
        rainmachine.client.zones.stop(service.data[CONF_ZONE_ID])

    hass.services.register(
        DOMAIN, 'start_program',
        start_program,
        schema=SERVICE_START_PROGRAM_SCHEMA)

    hass.services.register(
        DOMAIN, 'start_zone', start_zone, schema=SERVICE_START_ZONE_SCHEMA)

    hass.services.register(DOMAIN, 'stop_all', stop_all)

    hass.services.register(
        DOMAIN,
        'stop_program',
        stop_program,
        schema=SERVICE_STOP_PROGRAM_SCHEMA)

    hass.services.register(
        DOMAIN, 'stop_zone', stop_zone, schema=SERVICE_STOP_ZONE_SCHEMA)

    return True


class RainMachine(object):
    """Define a generic RainMachine object."""

    def __init__(self, hass, client):
        """Initialize."""
        self.client = client
        self.device_mac = self.client.provision.wifi()['macAddress']
        self.restrictions = {}

    def update(self):
        """Update sensor/binary sensor data."""
        self.restrictions.update({
            'current': self.client.restrictions.current(),
            'global': self.client.restrictions.universal()
        })


class RainMachineEntity(Entity):
    """Define a generic RainMachine entity."""

    def __init__(self,
                 rainmachine,
                 rainmachine_type,
                 rainmachine_entity_id,
                 name,
                 icon=DEFAULT_ICON):
        """Initialize."""
        self._attrs = {ATTR_ATTRIBUTION: DEFAULT_ATTRIBUTION}
        self._icon = icon
        self._name = name
        self._rainmachine_type = rainmachine_type
        self._rainmachine_entity_id = rainmachine_entity_id
        self._state = None
        self._unit = None
        self.rainmachine = rainmachine

    @property
    def device_state_attributes(self) -> dict:
        """Return the state attributes."""
        return self._attrs

    @property
    def icon(self) -> str:
        """Return the icon."""
        return self._icon

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return a unique, HASS-friendly identifier for this entity."""
        return '{0}_{1}_{2}'.format(
            self.rainmachine.device_mac.replace(':', ''),
            self._rainmachine_type, self._rainmachine_entity_id)

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit

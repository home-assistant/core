"""Implements a RainMachine sprinkler controller for Home Assistant."""

import asyncio
from datetime import timedelta
from logging import getLogger

import regenmaschine as rm
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.switch import SwitchDevice, PLATFORM_SCHEMA
from homeassistant.const import (ATTR_ATTRIBUTION, ATTR_DEVICE_CLASS,
                                 CONF_EMAIL, CONF_IP_ADDRESS, CONF_PASSWORD)
from homeassistant.util import Throttle

_LOGGER = getLogger(__name__)
REQUIREMENTS = ['regenmaschine==0.3.2']

ATTR_CYCLES = 'cycles'
ATTR_TOTAL_DURATION = 'total_duration'

CONF_HIDE_DISABLED_ENTITIES = 'hide_disabled_entities'
CONF_ZONE_RUN_TIME = 'zone_run_time'

DEFAULT_ZONE_RUN_SECONDS = 60 * 10

MIN_SCAN_TIME_LOCAL = timedelta(seconds=1)
MIN_SCAN_TIME_REMOTE = timedelta(seconds=5)
MIN_SCAN_TIME_FORCED = timedelta(milliseconds=100)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_IP_ADDRESS):
    cv.string,
    vol.Optional(CONF_EMAIL):
    cv.string,
    vol.Required(CONF_PASSWORD):
    cv.string,
    vol.Optional(CONF_ZONE_RUN_TIME, default=DEFAULT_ZONE_RUN_SECONDS):
    cv.positive_int,
    vol.Optional(CONF_HIDE_DISABLED_ENTITIES, default=True):
    cv.boolean
})


def aware_throttle(api_type):
    """Create an API type-aware throttler."""
    _decorator = None
    if api_type == 'local':

        @Throttle(MIN_SCAN_TIME_LOCAL, MIN_SCAN_TIME_FORCED)
        def decorator(function):
            """Create a local API throttler."""
            return function

        _decorator = decorator
    else:

        @Throttle(MIN_SCAN_TIME_REMOTE, MIN_SCAN_TIME_FORCED)
        def decorator(function):
            """Create a remote API throttler."""
            return function

        _decorator = decorator

    return _decorator


class RainMachineEntity(SwitchDevice):
    """A class to represent a generic RainMachine entity."""

    def __init__(self, client, entity_json, **kwargs):
        """Initialize a generic RainMachine entity."""
        self._api_type = 'remote' if client.auth.using_remote_api else 'local'
        self._client = client
        self._device_name = kwargs.get('device_name')
        self._entity_json = entity_json

        self._attrs = {
            ATTR_ATTRIBUTION: '© RainMachine',
            ATTR_DEVICE_CLASS: self._device_name
        }

    @property
    def device_state_attributes(self) -> dict:
        """Return the state attributes."""
        if self._client:
            return self._attrs

    @property
    def is_enabled(self) -> bool:
        """Return whether the entity is enabled."""
        return self._entity_json.get('active')

    @property
    def rainmachine_id(self) -> int:
        """Return the RainMachine ID for this entity."""
        return self._entity_json.get('uid')

    @property
    def should_poll(self) -> bool:
        """Return the polling state."""
        return True

    @property
    def unique_id(self) -> str:
        """Return a unique, HASS-friendly identifier for this entity."""
        return '{}.{}.{}'.format(self.__class__, self._device_name,
                                 self.rainmachine_id)

    @aware_throttle('local')
    def _local_update(self) -> None:
        """Call an update with scan times appropriate for the local API."""
        self._update()

    @aware_throttle('remote')
    def _remote_update(self) -> None:
        """Call an update with scan times appropriate for the remote API."""
        self._update()

    def _update(self) -> None:  # pylint: disable=no-self-use
        """Logic for update method, regardless of API type."""
        _LOGGER.warning('Update method not defined for base class')

    def update(self) -> None:
        """Determine how the entity updates itself."""
        if self._api_type == 'remote':
            self._remote_update()
        else:
            self._local_update()


class RainMachineProgram(RainMachineEntity):
    """A RainMachine program."""

    @property
    def is_on(self) -> bool:
        """Return whether the program is running."""
        return bool(self._entity_json.get('status'))

    @property
    def name(self) -> str:
        """Return the name of the program."""
        return 'Program: {}'.format(self._entity_json.get('name'))

    def turn_off(self, **kwargs) -> None:
        """Turn the program off."""
        try:
            self._client.programs.stop(self.rainmachine_id)
        except rm.exceptions.BrokenAPICall:
            _LOGGER.error('programs.stop currently broken in remote API')
        except rm.exceptions.HTTPError as exc_info:
            _LOGGER.error('Unable to turn off program "%s"',
                          self.rainmachine_id)
            _LOGGER.debug(str(exc_info))

    def turn_on(self, **kwargs) -> None:
        """Turn the program on."""
        try:
            self._client.programs.start(self.rainmachine_id)
        except rm.exceptions.BrokenAPICall:
            _LOGGER.error('programs.start currently broken in remote API')
        except rm.exceptions.HTTPError as exc_info:
            _LOGGER.error('Unable to turn on program "%s"',
                          self.rainmachine_id)
            _LOGGER.debug(str(exc_info))

    def _update(self) -> None:
        """Update info for the program."""
        try:
            self._entity_json = self._client.programs.get(self.rainmachine_id)
        except rm.exceptions.HTTPError as exc_info:
            _LOGGER.error('Unable to update info for program "%s"',
                          self.rainmachine_id)
            _LOGGER.debug(str(exc_info))


class RainMachineZone(RainMachineEntity):
    """A RainMachine zone."""

    def __init__(self, client, zone_json, **kwargs):
        """Initialize a RainMachine zone."""
        super(RainMachineZone, self).__init__(client, zone_json, **kwargs)
        self._run_time = kwargs.get(CONF_ZONE_RUN_TIME)
        self._attrs.update({
            ATTR_CYCLES:
            self._entity_json.get('noOfCycles'),
            ATTR_TOTAL_DURATION:
            self._entity_json.get('userDuration')
        })

    @property
    def is_on(self) -> bool:
        """Return whether the zone is running."""
        return bool(self._entity_json.get('state'))

    @property
    def name(self) -> str:
        """Return the name of the zone."""
        return 'Zone: {}'.format(self._entity_json.get('name'))

    def turn_off(self, **kwargs) -> None:
        """Turn the zone off."""
        try:
            self._client.zones.stop(self.rainmachine_id)
        except rm.exceptions.HTTPError as exc_info:
            _LOGGER.error('Unable to turn off zone "%s"',
                          self.rainmachine_id)
            _LOGGER.debug(str(exc_info))

    def turn_on(self, **kwargs) -> None:
        """Turn the zone on."""
        try:
            self._client.zones.start(self.rainmachine_id, self._run_time)
        except rm.exceptions.HTTPError as exc_info:
            _LOGGER.error('Unable to turn on zone "%s"',
                          self.rainmachine_id)
            _LOGGER.debug(str(exc_info))

    def _update(self) -> None:
        """Update info for the zone."""
        try:
            self._entity_json = self._client.zones.get(self.rainmachine_id)
        except rm.exceptions.HTTPError as exc_info:
            _LOGGER.error('Unable to update info for zone "%s"',
                          self.rainmachine_id)
            _LOGGER.debug(str(exc_info))


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set this component up under its platform."""
    ip_address = config.get(CONF_IP_ADDRESS)
    _LOGGER.debug('IP address: %s', ip_address)

    email_address = config.get(CONF_EMAIL)
    _LOGGER.debug('Email address: %s', email_address)

    password = config.get(CONF_PASSWORD)
    _LOGGER.debug('Password: %s', password)

    hide_disabled_entities = config.get(CONF_HIDE_DISABLED_ENTITIES)
    _LOGGER.debug('Show disabled entities: %s', hide_disabled_entities)

    zone_run_time = config.get(CONF_ZONE_RUN_TIME)
    _LOGGER.debug('Zone run time: %s', zone_run_time)

    try:
        if ip_address:
            _LOGGER.debug('Configuring local API...')
            auth = rm.Authenticator.create_local(ip_address, password)
        elif email_address:
            _LOGGER.debug('Configuring remote API...')
            auth = rm.Authenticator.create_remote(email_address, password)
        else:
            _LOGGER.error('Neither IP address nor email address given')
            return False
    except rm.exceptions.HTTPError as exec_info:
        _LOGGER.error('HTTP error during authentication: %s', str(exec_info))
        return False

    try:
        _LOGGER.debug('Instantiating RainMachine client...')
        client = rm.Client(auth)

        rainmachine_device_name = client.provision.device_name().get('name')

        entities = []
        for program in client.programs.all().get('programs'):
            if hide_disabled_entities and program.get('active') is False:
                continue

            _LOGGER.debug('Adding program: %s', program)
            entities.append(
                RainMachineProgram(
                    client, program, device_name=rainmachine_device_name))

        for zone in client.zones.all().get('zones'):
            if hide_disabled_entities and zone.get('active') is False:
                continue

            _LOGGER.debug('Adding zone: %s', zone)
            entities.append(
                RainMachineZone(
                    client,
                    zone,
                    device_name=rainmachine_device_name,
                    zone_run_time=zone_run_time))

        async_add_devices(entities)
    except rm.exceptions.HTTPError as exec_info:
        _LOGGER.error('Request failed: %s', str(exec_info))
        return False
    except Exception as exec_info:  # pylint: disable=broad-except
        _LOGGER.error('Unknown error: %s', str(exec_info))
        return False

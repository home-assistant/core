"""Implements a RainMachine sprinkler controller for Home Assistant."""

from datetime import timedelta
from logging import getLogger

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.switch import SwitchDevice
from homeassistant.const import (
    ATTR_ATTRIBUTION, ATTR_DEVICE_CLASS, CONF_EMAIL, CONF_IP_ADDRESS,
    CONF_PASSWORD, CONF_PLATFORM, CONF_PORT, CONF_SCAN_INTERVAL, CONF_SSL)
from homeassistant.util import Throttle

_LOGGER = getLogger(__name__)
REQUIREMENTS = ['regenmaschine==0.4.1']

ATTR_CYCLES = 'cycles'
ATTR_TOTAL_DURATION = 'total_duration'

CONF_ZONE_RUN_TIME = 'zone_run_time'

DEFAULT_PORT = 8080
DEFAULT_SSL = True
DEFAULT_ZONE_RUN_SECONDS = 60 * 10

MIN_SCAN_TIME_LOCAL = timedelta(seconds=1)
MIN_SCAN_TIME_REMOTE = timedelta(seconds=5)
MIN_SCAN_TIME_FORCED = timedelta(milliseconds=100)

PLATFORM_SCHEMA = vol.Schema(
    vol.All(
        cv.has_at_least_one_key(CONF_IP_ADDRESS, CONF_EMAIL),
        {
            vol.Required(CONF_PLATFORM):
            cv.string,
            vol.Optional(CONF_SCAN_INTERVAL):
            cv.time_period,
            vol.Exclusive(CONF_IP_ADDRESS, 'auth'):
            cv.string,
            vol.Exclusive(CONF_EMAIL, 'auth'):
            vol.Email(),  # pylint: disable=no-value-for-parameter
            vol.Required(CONF_PASSWORD):
            cv.string,
            vol.Optional(CONF_PORT, default=DEFAULT_PORT):
            cv.port,
            vol.Optional(CONF_SSL, default=DEFAULT_SSL):
            cv.boolean,
            vol.Optional(CONF_ZONE_RUN_TIME, default=DEFAULT_ZONE_RUN_SECONDS):
            cv.positive_int
        }),
    extra=vol.ALLOW_EXTRA)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set this component up under its platform."""
    import regenmaschine as rm

    ip_address = config.get(CONF_IP_ADDRESS)
    _LOGGER.debug('IP address: %s', ip_address)

    email_address = config.get(CONF_EMAIL)
    _LOGGER.debug('Email address: %s', email_address)

    password = config.get(CONF_PASSWORD)
    _LOGGER.debug('Password: %s', password)

    zone_run_time = config.get(CONF_ZONE_RUN_TIME)
    _LOGGER.debug('Zone run time: %s', zone_run_time)

    try:
        if ip_address:
            port = config.get(CONF_PORT)
            _LOGGER.debug('Port: %s', port)

            ssl = config.get(CONF_SSL)
            _LOGGER.debug('SSL: %s', ssl)

            _LOGGER.debug('Configuring local API')
            auth = rm.Authenticator.create_local(
                ip_address, password, port=port, https=ssl)
        elif email_address:
            _LOGGER.debug('Configuring remote API')
            auth = rm.Authenticator.create_remote(email_address, password)

        _LOGGER.debug('Querying against: %s', auth.url)

        _LOGGER.debug('Instantiating RainMachine client')
        client = rm.Client(auth)

        rainmachine_device_name = client.provision.device_name().get('name')

        entities = []
        for program in client.programs.all().get('programs'):
            if not program.get('active'):
                continue

            _LOGGER.debug('Adding program: %s', program)
            entities.append(
                RainMachineProgram(
                    client, program, device_name=rainmachine_device_name))

        for zone in client.zones.all().get('zones'):
            if not zone.get('active'):
                continue

            _LOGGER.debug('Adding zone: %s', zone)
            entities.append(
                RainMachineZone(
                    client,
                    zone,
                    zone_run_time,
                    device_name=rainmachine_device_name, ))

        add_devices(entities)
    except rm.exceptions.HTTPError as exc_info:
        _LOGGER.error('An HTTP error occurred while talking with RainMachine')
        _LOGGER.debug(exc_info)
        return False
    except UnboundLocalError as exc_info:
        _LOGGER.error('Could not authenticate against RainMachine')
        _LOGGER.debug(exc_info)
        return False


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
    def unique_id(self) -> str:
        """Return a unique, HASS-friendly identifier for this entity."""
        return self.rainmachine_id

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
        raise NotImplementedError()

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
        import regenmaschine.exceptions as exceptions

        try:
            self._client.programs.stop(self.rainmachine_id)
        except exceptions.BrokenAPICall:
            _LOGGER.error('programs.stop currently broken in remote API')
        except exceptions.HTTPError as exc_info:
            _LOGGER.error('Unable to turn off program "%s"',
                          self.rainmachine_id)
            _LOGGER.debug(exc_info)

    def turn_on(self, **kwargs) -> None:
        """Turn the program on."""
        import regenmaschine.exceptions as exceptions

        try:
            self._client.programs.start(self.rainmachine_id)
        except exceptions.BrokenAPICall:
            _LOGGER.error('programs.start currently broken in remote API')
        except exceptions.HTTPError as exc_info:
            _LOGGER.error('Unable to turn on program "%s"',
                          self.rainmachine_id)
            _LOGGER.debug(exc_info)

    def _update(self) -> None:
        """Update info for the program."""
        import regenmaschine.exceptions as exceptions

        try:
            self._entity_json = self._client.programs.get(self.rainmachine_id)
        except exceptions.HTTPError as exc_info:
            _LOGGER.error('Unable to update info for program "%s"',
                          self.rainmachine_id)
            _LOGGER.debug(exc_info)


class RainMachineZone(RainMachineEntity):
    """A RainMachine zone."""

    def __init__(self, client, zone_json, zone_run_time, **kwargs):
        """Initialize a RainMachine zone."""
        super().__init__(client, zone_json, **kwargs)
        self._run_time = zone_run_time
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
        import regenmaschine.exceptions as exceptions

        try:
            self._client.zones.stop(self.rainmachine_id)
        except exceptions.HTTPError as exc_info:
            _LOGGER.error('Unable to turn off zone "%s"', self.rainmachine_id)
            _LOGGER.debug(exc_info)

    def turn_on(self, **kwargs) -> None:
        """Turn the zone on."""
        import regenmaschine.exceptions as exceptions

        try:
            self._client.zones.start(self.rainmachine_id, self._run_time)
        except exceptions.HTTPError as exc_info:
            _LOGGER.error('Unable to turn on zone "%s"', self.rainmachine_id)
            _LOGGER.debug(exc_info)

    def _update(self) -> None:
        """Update info for the zone."""
        import regenmaschine.exceptions as exceptions

        try:
            self._entity_json = self._client.zones.get(self.rainmachine_id)
        except exceptions.HTTPError as exc_info:
            _LOGGER.error('Unable to update info for zone "%s"',
                          self.rainmachine_id)
            _LOGGER.debug(exc_info)

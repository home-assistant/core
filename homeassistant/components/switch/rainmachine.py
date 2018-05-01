"""Implements a RainMachine sprinkler controller for Home Assistant."""

from logging import getLogger

from homeassistant.components.rainmachine import (
    CONF_ZONE_RUN_TIME, DATA_RAINMACHINE, DEFAULT_ATTRIBUTION, MIN_SCAN_TIME,
    MIN_SCAN_TIME_FORCED)
from homeassistant.components.switch import SwitchDevice
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.util import Throttle

DEPENDENCIES = ['rainmachine']

_LOGGER = getLogger(__name__)

ATTR_CYCLES = 'cycles'
ATTR_TOTAL_DURATION = 'total_duration'

DEFAULT_ZONE_RUN = 60 * 10


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set this component up under its platform."""
    if discovery_info is None:
        return

    _LOGGER.debug('Config received: %s', discovery_info)

    zone_run_time = discovery_info.get(CONF_ZONE_RUN_TIME, DEFAULT_ZONE_RUN)

    client, device_mac = hass.data.get(DATA_RAINMACHINE)

    entities = []
    for program in client.programs.all().get('programs', {}):
        if not program.get('active'):
            continue

        _LOGGER.debug('Adding program: %s', program)
        entities.append(
            RainMachineProgram(client, device_mac, program))

    for zone in client.zones.all().get('zones', {}):
        if not zone.get('active'):
            continue

        _LOGGER.debug('Adding zone: %s', zone)
        entities.append(
            RainMachineZone(client, device_mac, zone,
                            zone_run_time))

    add_devices(entities, True)


class RainMachineEntity(SwitchDevice):
    """A class to represent a generic RainMachine entity."""

    def __init__(self, client, device_mac, entity_json):
        """Initialize a generic RainMachine entity."""
        self._api_type = 'remote' if client.auth.using_remote_api else 'local'
        self._client = client
        self._entity_json = entity_json

        self.device_mac = device_mac

        self._attrs = {
            ATTR_ATTRIBUTION: DEFAULT_ATTRIBUTION
        }

    @property
    def device_state_attributes(self) -> dict:
        """Return the state attributes."""
        return self._attrs

    @property
    def icon(self) -> str:
        """Return the icon."""
        return 'mdi:water'

    @property
    def is_enabled(self) -> bool:
        """Return whether the entity is enabled."""
        return self._entity_json.get('active')

    @property
    def rainmachine_entity_id(self) -> int:
        """Return the RainMachine ID for this entity."""
        return self._entity_json.get('uid')


class RainMachineProgram(RainMachineEntity):
    """A RainMachine program."""

    @property
    def is_on(self) -> bool:
        """Return whether the program is running."""
        return bool(self._entity_json.get('status'))

    @property
    def name(self) -> str:
        """Return the name of the program."""
        return 'Program: {0}'.format(self._entity_json.get('name'))

    @property
    def unique_id(self) -> str:
        """Return a unique, HASS-friendly identifier for this entity."""
        return '{0}_program_{1}'.format(
            self.device_mac.replace(':', ''), self.rainmachine_entity_id)

    def turn_off(self, **kwargs) -> None:
        """Turn the program off."""
        import regenmaschine.exceptions as exceptions

        try:
            self._client.programs.stop(self.rainmachine_entity_id)
        except exceptions.BrokenAPICall:
            _LOGGER.error('programs.stop currently broken in remote API')
        except exceptions.HTTPError as exc_info:
            _LOGGER.error('Unable to turn off program "%s"', self.unique_id)
            _LOGGER.debug(exc_info)

    def turn_on(self, **kwargs) -> None:
        """Turn the program on."""
        import regenmaschine.exceptions as exceptions

        try:
            self._client.programs.start(self.rainmachine_entity_id)
        except exceptions.BrokenAPICall:
            _LOGGER.error('programs.start currently broken in remote API')
        except exceptions.HTTPError as exc_info:
            _LOGGER.error('Unable to turn on program "%s"', self.unique_id)
            _LOGGER.debug(exc_info)

    @Throttle(MIN_SCAN_TIME, MIN_SCAN_TIME_FORCED)
    def update(self) -> None:
        """Update info for the program."""
        import regenmaschine.exceptions as exceptions

        try:
            self._entity_json = self._client.programs.get(
                self.rainmachine_entity_id)
        except exceptions.HTTPError as exc_info:
            _LOGGER.error('Unable to update info for program "%s"',
                          self.unique_id)
            _LOGGER.debug(exc_info)


class RainMachineZone(RainMachineEntity):
    """A RainMachine zone."""

    def __init__(self, client, device_mac, zone_json,
                 zone_run_time):
        """Initialize a RainMachine zone."""
        super().__init__(client, device_mac, zone_json)
        self._run_time = zone_run_time
        self._attrs.update({
            ATTR_CYCLES: self._entity_json.get('noOfCycles'),
            ATTR_TOTAL_DURATION: self._entity_json.get('userDuration')
        })

    @property
    def is_on(self) -> bool:
        """Return whether the zone is running."""
        return bool(self._entity_json.get('state'))

    @property
    def name(self) -> str:
        """Return the name of the zone."""
        return 'Zone: {0}'.format(self._entity_json.get('name'))

    @property
    def unique_id(self) -> str:
        """Return a unique, HASS-friendly identifier for this entity."""
        return '{0}_zone_{1}'.format(
            self.device_mac.replace(':', ''), self.rainmachine_entity_id)

    def turn_off(self, **kwargs) -> None:
        """Turn the zone off."""
        import regenmaschine.exceptions as exceptions

        try:
            self._client.zones.stop(self.rainmachine_entity_id)
        except exceptions.HTTPError as exc_info:
            _LOGGER.error('Unable to turn off zone "%s"', self.unique_id)
            _LOGGER.debug(exc_info)

    def turn_on(self, **kwargs) -> None:
        """Turn the zone on."""
        import regenmaschine.exceptions as exceptions

        try:
            self._client.zones.start(self.rainmachine_entity_id,
                                     self._run_time)
        except exceptions.HTTPError as exc_info:
            _LOGGER.error('Unable to turn on zone "%s"', self.unique_id)
            _LOGGER.debug(exc_info)

    @Throttle(MIN_SCAN_TIME, MIN_SCAN_TIME_FORCED)
    def update(self) -> None:
        """Update info for the zone."""
        import regenmaschine.exceptions as exceptions

        try:
            self._entity_json = self._client.zones.get(
                self.rainmachine_entity_id)
        except exceptions.HTTPError as exc_info:
            _LOGGER.error('Unable to update info for zone "%s"',
                          self.unique_id)
            _LOGGER.debug(exc_info)

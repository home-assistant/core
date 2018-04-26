"""
This component provides support for RainMachine programs and zones.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/switch.rainmachine/
"""

from logging import getLogger

from homeassistant.components.rainmachine import (
    CONF_ZONE_RUN_TIME, DATA_RAINMACHINE, DEFAULT_ATTRIBUTION, MIN_SCAN_TIME,
    MIN_SCAN_TIME_FORCED)
from homeassistant.components.switch import SwitchDevice
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.util import Throttle

DEPENDENCIES = ['rainmachine']

_LOGGER = getLogger(__name__)

ATTR_CS_ON = 'cs_on'
ATTR_CYCLES = 'cycles'
ATTR_DELAY = 'delay'
ATTR_DELAY_ON = 'delay_on'
ATTR_FREQUENCY = 'frequency'
ATTR_IGNORE_WEATHER = 'ignoring_weather_data'
ATTR_NEXT_RUN = 'next_run'
ATTR_SIMULATION_EXPIRED = 'simulation_expired'
ATTR_SOAK = 'soak'
ATTR_START_TIME = 'start_time'
ATTR_STATUS = 'status'
ATTR_TOTAL_DURATION = 'total_duration'
ATTR_USE_WATERSENSE = 'using_watersense'
ATTR_WATER_SKIP = 'watering_percentage_skip_amount'
ATTR_YEARLY_RECURRING = 'yearly_recurring'
ATTR_ZONES = 'zones'

DEFAULT_ZONE_RUN = 60 * 10

DAYS = [
    'Monday',
    'Tuesday',
    'Wednesday',
    'Thursday',
    'Friday',
    'Saturday',
    'Sunday'
]

PROGRAM_STATUS_MAP = {
    0: 'Not Running',
    1: 'Running',
    2: 'Queued'
}


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

    def __init__(self, client, device_mac, program_json):
        """Initialize."""
        super().__init__(client, device_mac, program_json)

        self._attrs.update({
            ATTR_CS_ON: self._entity_json['cs_on'],
            ATTR_CYCLES: self._entity_json['cycles'],
            ATTR_DELAY: self._entity_json['delay'],
            ATTR_DELAY_ON: self._entity_json['delay_on'],
            ATTR_FREQUENCY: self._calculate_running_days(),
            ATTR_SOAK: self._entity_json['soak'],
            ATTR_START_TIME: self._entity_json['startTime'],
            ATTR_STATUS: PROGRAM_STATUS_MAP[self._entity_json['status']]
        })

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

    @property
    def zones(self) -> list:
        """Return a list of active zones associated with this program."""
        return [z for z in self._entity_json['wateringTimes'] if z['active']]

    def _calculate_running_days(self) -> str:
        """Calculate running days from an RM string ("0010001100")."""
        freq_type = self._entity_json['frequency']['type']
        freq_param = self._entity_json['frequency']['param']
        if freq_type == 0:
            return 'Daily'

        if freq_type == 1:
            return 'Every {0} Days'.format(freq_param)

        if freq_type == 2:
            return ', '.join([
                DAYS[idx] for idx, val in enumerate(freq_param[2:-1][::-1])
                if val == '1'
            ])

        if freq_type == 4:
            return '{0} Days'.format('Odd' if freq_param == '1' else 'Even')

        return None

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

            self._attrs.update({
                ATTR_CS_ON: self._entity_json.get('cs_on'),
                ATTR_CYCLES: self._entity_json.get('cycles'),
                ATTR_DELAY: self._entity_json.get('delay'),
                ATTR_DELAY_ON: self._entity_json.get('delay_on'),
                ATTR_FREQUENCY: self._calculate_running_days(),
                ATTR_IGNORE_WEATHER:
                    self._entity_json.get('ignoreInternetWeather'),
                ATTR_NEXT_RUN: self._entity_json.get('nextRun'),
                ATTR_SIMULATION_EXPIRED:
                    self._entity_json.get('simulationExpired'),
                ATTR_SOAK: self._entity_json.get('soak'),
                ATTR_START_TIME: self._entity_json.get('startTime'),
                ATTR_STATUS:
                    PROGRAM_STATUS_MAP[self._entity_json.get('status')],
                ATTR_USE_WATERSENSE: self._entity_json.get('useWaterSense'),
                ATTR_WATER_SKIP: self._entity_json.get('freq_modified'),
                ATTR_YEARLY_RECURRING:
                    self._entity_json.get('yearlyRecurring'),
                ATTR_ZONES: ', '.join(z['name'] for z in self.zones)
            })
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

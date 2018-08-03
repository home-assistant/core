"""
This component provides support for RainMachine programs and zones.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/switch.rainmachine/
"""
import logging

from homeassistant.components.rainmachine import (
    CONF_ZONE_RUN_TIME, DATA_RAINMACHINE, DEFAULT_ZONE_RUN,
    PROGRAM_UPDATE_TOPIC, ZONE_UPDATE_TOPIC, RainMachineEntity)
from homeassistant.const import ATTR_ID
from homeassistant.components.switch import SwitchDevice
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect, async_dispatcher_send)

DEPENDENCIES = ['rainmachine']

_LOGGER = logging.getLogger(__name__)

ATTR_AREA = 'area'
ATTR_CS_ON = 'cs_on'
ATTR_CURRENT_CYCLE = 'current_cycle'
ATTR_CYCLES = 'cycles'
ATTR_DELAY = 'delay'
ATTR_DELAY_ON = 'delay_on'
ATTR_FIELD_CAPACITY = 'field_capacity'
ATTR_NO_CYCLES = 'number_of_cycles'
ATTR_PRECIP_RATE = 'sprinkler_head_precipitation_rate'
ATTR_RESTRICTIONS = 'restrictions'
ATTR_SLOPE = 'slope'
ATTR_SOAK = 'soak'
ATTR_SOIL_TYPE = 'soil_type'
ATTR_SPRINKLER_TYPE = 'sprinkler_head_type'
ATTR_STATUS = 'status'
ATTR_SUN_EXPOSURE = 'sun_exposure'
ATTR_VEGETATION_TYPE = 'vegetation_type'
ATTR_ZONES = 'zones'

DAYS = [
    'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday',
    'Sunday'
]

PROGRAM_STATUS_MAP = {0: 'Not Running', 1: 'Running', 2: 'Queued'}

SOIL_TYPE_MAP = {
    0: 'Not Set',
    1: 'Clay Loam',
    2: 'Silty Clay',
    3: 'Clay',
    4: 'Loam',
    5: 'Sandy Loam',
    6: 'Loamy Sand',
    7: 'Sand',
    8: 'Sandy Clay',
    9: 'Silt Loam',
    10: 'Silt',
    99: 'Other'
}

SLOPE_TYPE_MAP = {
    0: 'Not Set',
    1: 'Flat',
    2: 'Moderate',
    3: 'High',
    4: 'Very High',
    99: 'Other'
}

SPRINKLER_TYPE_MAP = {
    0: 'Not Set',
    1: 'Popup Spray',
    2: 'Rotors',
    3: 'Surface Drip',
    4: 'Bubblers Drip',
    99: 'Other'
}

SUN_EXPOSURE_MAP = {
    0: 'Not Set',
    1: 'Full Sun',
    2: 'Partial Shade',
    3: 'Full Shade'
}

VEGETATION_MAP = {
    0: 'Not Set',
    2: 'Cool Season Grass',
    3: 'Fruit Trees',
    4: 'Flowers',
    5: 'Vegetables',
    6: 'Citrus',
    7: 'Trees and Bushes',
    9: 'Drought Tolerant Plants',
    10: 'Warm Season Grass',
    99: 'Other'
}


async def async_setup_platform(
        hass, config, async_add_devices, discovery_info=None):
    """Set up the RainMachine Switch platform."""
    if discovery_info is None:
        return

    _LOGGER.debug('Config received: %s', discovery_info)

    zone_run_time = discovery_info.get(CONF_ZONE_RUN_TIME, DEFAULT_ZONE_RUN)

    rainmachine = hass.data[DATA_RAINMACHINE]

    entities = []

    programs = await rainmachine.client.programs.all()
    for program in programs:
        if not program.get('active'):
            continue

        _LOGGER.debug('Adding program: %s', program)
        entities.append(RainMachineProgram(rainmachine, program))

    zones = await rainmachine.client.zones.all()
    for zone in zones:
        if not zone.get('active'):
            continue

        _LOGGER.debug('Adding zone: %s', zone)
        entities.append(RainMachineZone(rainmachine, zone, zone_run_time))

    async_add_devices(entities, True)


class RainMachineSwitch(RainMachineEntity, SwitchDevice):
    """A class to represent a generic RainMachine switch."""

    def __init__(self, rainmachine, switch_type, obj):
        """Initialize a generic RainMachine switch."""
        super().__init__(rainmachine)

        self._name = obj['name']
        self._obj = obj
        self._rainmachine_entity_id = obj['uid']
        self._switch_type = switch_type

    @property
    def icon(self) -> str:
        """Return the icon."""
        return 'mdi:water'

    @property
    def is_enabled(self) -> bool:
        """Return whether the entity is enabled."""
        return self._obj.get('active')

    @property
    def unique_id(self) -> str:
        """Return a unique, HASS-friendly identifier for this entity."""
        return '{0}_{1}_{2}'.format(
            self.rainmachine.device_mac.replace(':', ''), self._switch_type,
            self._rainmachine_entity_id)

    @callback
    def _program_updated(self):
        """Update state, trigger updates."""
        self.async_schedule_update_ha_state(True)


class RainMachineProgram(RainMachineSwitch):
    """A RainMachine program."""

    def __init__(self, rainmachine, obj):
        """Initialize a generic RainMachine switch."""
        super().__init__(rainmachine, 'program', obj)

    @property
    def is_on(self) -> bool:
        """Return whether the program is running."""
        return bool(self._obj.get('status'))

    @property
    def zones(self) -> list:
        """Return a list of active zones associated with this program."""
        return [z for z in self._obj['wateringTimes'] if z['active']]

    async def async_added_to_hass(self):
        """Register callbacks."""
        async_dispatcher_connect(
            self.hass, PROGRAM_UPDATE_TOPIC, self._program_updated)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the program off."""
        from regenmaschine.errors import RequestError

        try:
            await self.rainmachine.client.programs.stop(
                self._rainmachine_entity_id)
            async_dispatcher_send(self.hass, PROGRAM_UPDATE_TOPIC)
        except RequestError as err:
            _LOGGER.error(
                'Unable to turn off program "%s": %s', self.unique_id,
                str(err))

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the program on."""
        from regenmaschine.errors import RequestError

        try:
            await self.rainmachine.client.programs.start(
                self._rainmachine_entity_id)
            async_dispatcher_send(self.hass, PROGRAM_UPDATE_TOPIC)
        except RequestError as err:
            _LOGGER.error(
                'Unable to turn on program "%s": %s', self.unique_id, str(err))

    async def async_update(self) -> None:
        """Update info for the program."""
        from regenmaschine.errors import RequestError

        try:
            self._obj = await self.rainmachine.client.programs.get(
                self._rainmachine_entity_id)

            self._attrs.update({
                ATTR_ID: self._obj['uid'],
                ATTR_SOAK: self._obj.get('soak'),
                ATTR_STATUS: PROGRAM_STATUS_MAP[self._obj.get('status')],
                ATTR_ZONES: ', '.join(z['name'] for z in self.zones)
            })
        except RequestError as err:
            _LOGGER.error(
                'Unable to update info for program "%s": %s', self.unique_id,
                str(err))


class RainMachineZone(RainMachineSwitch):
    """A RainMachine zone."""

    def __init__(self, rainmachine, obj, zone_run_time):
        """Initialize a RainMachine zone."""
        super().__init__(rainmachine, 'zone', obj)

        self._properties_json = {}
        self._run_time = zone_run_time

    @property
    def is_on(self) -> bool:
        """Return whether the zone is running."""
        return bool(self._obj.get('state'))

    async def async_added_to_hass(self):
        """Register callbacks."""
        async_dispatcher_connect(
            self.hass, PROGRAM_UPDATE_TOPIC, self._program_updated)
        async_dispatcher_connect(
            self.hass, ZONE_UPDATE_TOPIC, self._program_updated)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the zone off."""
        from regenmaschine.errors import RequestError

        try:
            await self.rainmachine.client.zones.stop(
                self._rainmachine_entity_id)
        except RequestError as err:
            _LOGGER.error(
                'Unable to turn off zone "%s": %s', self.unique_id, str(err))

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the zone on."""
        from regenmaschine.errors import RequestError

        try:
            await self.rainmachine.client.zones.start(
                self._rainmachine_entity_id, self._run_time)
        except RequestError as err:
            _LOGGER.error(
                'Unable to turn on zone "%s": %s', self.unique_id, str(err))

    async def async_update(self) -> None:
        """Update info for the zone."""
        from regenmaschine.errors import RequestError

        try:
            self._obj = await self.rainmachine.client.zones.get(
                self._rainmachine_entity_id)

            self._properties_json = await self.rainmachine.client.zones.get(
                self._rainmachine_entity_id, details=True)

            self._attrs.update({
                ATTR_ID:
                    self._obj['uid'],
                ATTR_AREA:
                    self._properties_json.get('waterSense').get('area'),
                ATTR_CURRENT_CYCLE:
                    self._obj.get('cycle'),
                ATTR_FIELD_CAPACITY:
                    self._properties_json.get('waterSense')
                    .get('fieldCapacity'),
                ATTR_NO_CYCLES:
                    self._obj.get('noOfCycles'),
                ATTR_PRECIP_RATE:
                    self._properties_json.get('waterSense')
                    .get('precipitationRate'),
                ATTR_RESTRICTIONS:
                    self._obj.get('restriction'),
                ATTR_SLOPE:
                    SLOPE_TYPE_MAP.get(self._properties_json.get('slope')),
                ATTR_SOIL_TYPE:
                    SOIL_TYPE_MAP.get(self._properties_json.get('sun')),
                ATTR_SPRINKLER_TYPE:
                    SPRINKLER_TYPE_MAP.get(
                        self._properties_json.get('group_id')),
                ATTR_SUN_EXPOSURE:
                    SUN_EXPOSURE_MAP.get(self._properties_json.get('sun')),
                ATTR_VEGETATION_TYPE:
                    VEGETATION_MAP.get(self._obj.get('type')),
            })
        except RequestError as err:
            _LOGGER.error(
                'Unable to update info for zone "%s": %s', self.unique_id,
                str(err))

"""
Support for Eight Sleep sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.eight_sleep/
"""
import logging

from homeassistant.components.eight_sleep import (
    DATA_EIGHT, EightSleepHeatEntity, EightSleepUserEntity,
    CONF_SENSORS, NAME_MAP)

DEPENDENCIES = ['eight_sleep']

ATTR_ROOM_TEMP = 'Room Temperature'
ATTR_AVG_ROOM_TEMP = 'Average Room Temperature'
ATTR_BED_TEMP = 'Bed Temperature'
ATTR_AVG_BED_TEMP = 'Average Bed Temperature'
ATTR_RESP_RATE = 'Respiratory Rate'
ATTR_AVG_RESP_RATE = 'Average Respiratory Rate'
ATTR_HEART_RATE = 'Heart Rate'
ATTR_AVG_HEART_RATE = 'Average Heart Rate'
ATTR_SLEEP_DUR = 'Time Slept'
ATTR_LIGHT_PERC = 'Light Sleep %'
ATTR_DEEP_PERC = 'Deep Sleep %'
ATTR_REM_PERC = 'REM Sleep %'
ATTR_TNT = 'Tosses & Turns'
ATTR_SLEEP_STAGE = 'Sleep Stage'
ATTR_TARGET_HEAT = 'Target Heating Level'
ATTR_ACTIVE_HEAT = 'Heating Active'
ATTR_DURATION_HEAT = 'Heating Time Remaining'
ATTR_PROCESSING = 'Processing'
ATTR_SESSION_START = 'Session Start'

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the eight sleep sensors."""
    if discovery_info is None:
        return

    name = 'Eight'
    sensors = discovery_info[CONF_SENSORS]
    eight = hass.data[DATA_EIGHT]

    if hass.config.units.is_metric:
        units = 'si'
    else:
        units = 'us'

    all_sensors = []

    for sensor in sensors:
        if 'bed_state' in sensor:
            all_sensors.append(EightHeatSensor(name, eight, sensor))
        elif 'room_temp' in sensor:
            all_sensors.append(EightRoomSensor(name, eight, sensor, units))
        else:
            all_sensors.append(EightUserSensor(name, eight, sensor, units))

    async_add_entities(all_sensors, True)


class EightHeatSensor(EightSleepHeatEntity):
    """Representation of an eight sleep heat-based sensor."""

    def __init__(self, name, eight, sensor):
        """Initialize the sensor."""
        super().__init__(eight)

        self._sensor = sensor
        self._mapped_name = NAME_MAP.get(self._sensor, self._sensor)
        self._name = '{} {}'.format(name, self._mapped_name)
        self._state = None

        self._side = self._sensor.split('_')[0]
        self._userid = self._eight.fetch_userid(self._side)
        self._usrobj = self._eight.users[self._userid]

        _LOGGER.debug("Heat Sensor: %s, Side: %s, User: %s",
                      self._sensor, self._side, self._userid)

    @property
    def name(self):
        """Return the name of the sensor, if any."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return '%'

    async def async_update(self):
        """Retrieve latest state."""
        _LOGGER.debug("Updating Heat sensor: %s", self._sensor)
        self._state = self._usrobj.heating_level

    @property
    def device_state_attributes(self):
        """Return device state attributes."""
        state_attr = {ATTR_TARGET_HEAT: self._usrobj.target_heating_level}
        state_attr[ATTR_ACTIVE_HEAT] = self._usrobj.now_heating
        state_attr[ATTR_DURATION_HEAT] = self._usrobj.heating_remaining

        return state_attr


class EightUserSensor(EightSleepUserEntity):
    """Representation of an eight sleep user-based sensor."""

    def __init__(self, name, eight, sensor, units):
        """Initialize the sensor."""
        super().__init__(eight)

        self._sensor = sensor
        self._sensor_root = self._sensor.split('_', 1)[1]
        self._mapped_name = NAME_MAP.get(self._sensor, self._sensor)
        self._name = '{} {}'.format(name, self._mapped_name)
        self._state = None
        self._attr = None
        self._units = units

        self._side = self._sensor.split('_', 1)[0]
        self._userid = self._eight.fetch_userid(self._side)
        self._usrobj = self._eight.users[self._userid]

        _LOGGER.debug("User Sensor: %s, Side: %s, User: %s",
                      self._sensor, self._side, self._userid)

    @property
    def name(self):
        """Return the name of the sensor, if any."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        if 'current_sleep' in self._sensor or 'last_sleep' in self._sensor:
            return 'Score'
        if 'bed_temp' in self._sensor:
            if self._units == 'si':
                return '°C'
            return '°F'
        return None

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        if 'bed_temp' in self._sensor:
            return 'mdi:thermometer'

    async def async_update(self):
        """Retrieve latest state."""
        _LOGGER.debug("Updating User sensor: %s", self._sensor)
        if 'current' in self._sensor:
            self._state = self._usrobj.current_sleep_score
            self._attr = self._usrobj.current_values
        elif 'last' in self._sensor:
            self._state = self._usrobj.last_sleep_score
            self._attr = self._usrobj.last_values
        elif 'bed_temp' in self._sensor:
            temp = self._usrobj.current_values['bed_temp']
            try:
                if self._units == 'si':
                    self._state = round(temp, 2)
                else:
                    self._state = round((temp*1.8)+32, 2)
            except TypeError:
                self._state = None
        elif 'sleep_stage' in self._sensor:
            self._state = self._usrobj.current_values['stage']

    @property
    def device_state_attributes(self):
        """Return device state attributes."""
        if self._attr is None:
            # Skip attributes if sensor type doesn't support
            return None

        state_attr = {ATTR_SESSION_START: self._attr['date']}
        state_attr[ATTR_TNT] = self._attr['tnt']
        state_attr[ATTR_PROCESSING] = self._attr['processing']

        sleep_time = sum(self._attr['breakdown'].values()) - \
            self._attr['breakdown']['awake']
        state_attr[ATTR_SLEEP_DUR] = sleep_time
        try:
            state_attr[ATTR_LIGHT_PERC] = round((
                self._attr['breakdown']['light'] / sleep_time) * 100, 2)
        except ZeroDivisionError:
            state_attr[ATTR_LIGHT_PERC] = 0
        try:
            state_attr[ATTR_DEEP_PERC] = round((
                self._attr['breakdown']['deep'] / sleep_time) * 100, 2)
        except ZeroDivisionError:
            state_attr[ATTR_DEEP_PERC] = 0

        try:
            state_attr[ATTR_REM_PERC] = round((
                self._attr['breakdown']['rem'] / sleep_time) * 100, 2)
        except ZeroDivisionError:
            state_attr[ATTR_REM_PERC] = 0

        try:
            if self._units == 'si':
                room_temp = round(self._attr['room_temp'], 2)
            else:
                room_temp = round((self._attr['room_temp']*1.8)+32, 2)
        except TypeError:
            room_temp = None

        try:
            if self._units == 'si':
                bed_temp = round(self._attr['bed_temp'], 2)
            else:
                bed_temp = round((self._attr['bed_temp']*1.8)+32, 2)
        except TypeError:
            bed_temp = None

        if 'current' in self._sensor_root:
            state_attr[ATTR_RESP_RATE] = round(self._attr['resp_rate'], 2)
            state_attr[ATTR_HEART_RATE] = round(self._attr['heart_rate'], 2)
            state_attr[ATTR_SLEEP_STAGE] = self._attr['stage']
            state_attr[ATTR_ROOM_TEMP] = room_temp
            state_attr[ATTR_BED_TEMP] = bed_temp
        elif 'last' in self._sensor_root:
            state_attr[ATTR_AVG_RESP_RATE] = round(self._attr['resp_rate'], 2)
            state_attr[ATTR_AVG_HEART_RATE] = round(
                self._attr['heart_rate'], 2)
            state_attr[ATTR_AVG_ROOM_TEMP] = room_temp
            state_attr[ATTR_AVG_BED_TEMP] = bed_temp

        return state_attr


class EightRoomSensor(EightSleepUserEntity):
    """Representation of an eight sleep room sensor."""

    def __init__(self, name, eight, sensor, units):
        """Initialize the sensor."""
        super().__init__(eight)

        self._sensor = sensor
        self._mapped_name = NAME_MAP.get(self._sensor, self._sensor)
        self._name = '{} {}'.format(name, self._mapped_name)
        self._state = None
        self._attr = None
        self._units = units

    @property
    def name(self):
        """Return the name of the sensor, if any."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    async def async_update(self):
        """Retrieve latest state."""
        _LOGGER.debug("Updating Room sensor: %s", self._sensor)
        temp = self._eight.room_temperature()
        try:
            if self._units == 'si':
                self._state = round(temp, 2)
            else:
                self._state = round((temp*1.8)+32, 2)
        except TypeError:
            self._state = None

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        if self._units == 'si':
            return '°C'
        return '°F'

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return 'mdi:thermometer'

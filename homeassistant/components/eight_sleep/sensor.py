"""Support for Eight Sleep sensors."""
import logging

from homeassistant.const import PERCENTAGE, TEMP_CELSIUS, TEMP_FAHRENHEIT

from . import EightSleepHeatEntity, EightSleepUserEntity
from .const import DATA_EIGHT, NAME_MAP, SENSORS

ATTR_ROOM_TEMP = "Room Temperature"
ATTR_AVG_ROOM_TEMP = "Average Room Temperature"
ATTR_BED_TEMP = "Bed Temperature"
ATTR_AVG_BED_TEMP = "Average Bed Temperature"
ATTR_RESP_RATE = "Respiratory Rate"
ATTR_AVG_RESP_RATE = "Average Respiratory Rate"
ATTR_HEART_RATE = "Heart Rate"
ATTR_AVG_HEART_RATE = "Average Heart Rate"
ATTR_SLEEP_DUR = "Time Slept"
ATTR_LIGHT_PERC = f"Light Sleep {PERCENTAGE}"
ATTR_DEEP_PERC = f"Deep Sleep {PERCENTAGE}"
ATTR_REM_PERC = f"REM Sleep {PERCENTAGE}"
ATTR_TNT = "Tosses & Turns"
ATTR_SLEEP_STAGE = "Sleep Stage"
ATTR_TARGET_HEAT = "Target Heating Level"
ATTR_ACTIVE_HEAT = "Heating Active"
ATTR_DURATION_HEAT = "Heating Time Remaining"
ATTR_PROCESSING = "Processing"
ATTR_SESSION_START = "Session Start"
ATTR_FIT_DATE = "Fitness Date"
ATTR_FIT_DURATION_SCORE = "Fitness Duration Score"
ATTR_FIT_ASLEEP_SCORE = "Fitness Asleep Score"
ATTR_FIT_OUT_SCORE = "Fitness Out-of-Bed Score"
ATTR_FIT_WAKEUP_SCORE = "Fitness Wakeup Score"

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Discover and configure Eight Sleep sensors."""

    eight = hass.data[DATA_EIGHT]

    if hass.config.units.is_metric:
        units = "si"
    else:
        units = "us"

    all_sensors = []
    if eight.users:
        for user in eight.users:
            obj = eight.users[user]
            for sensor_type in SENSORS:
                if sensor_type == "bed_state":
                    all_sensors.append(EightHeatSensor(eight, sensor_type, obj.side))
                elif sensor_type == "room_temp":
                    all_sensors.append(EightRoomSensor(eight, sensor_type, units))
                else:
                    all_sensors.append(
                        EightUserSensor(eight, sensor_type, units, obj.side)
                    )

    async_add_entities(all_sensors, True)


class EightHeatSensor(EightSleepHeatEntity):
    """Representation of an eight sleep heat-based sensor."""

    def __init__(self, eight, sensor_type, side):
        """Initialize the sensor."""
        super().__init__(eight)

        self._sensor_type = sensor_type
        self._mapped_name = NAME_MAP.get(f"{side}_{self._sensor_type}")
        self._name = f"Eight Sleep - {self._mapped_name}"
        self._state = None

        self._side = side
        self._userid = self._eight.fetch_userid(self._side)
        self._usrobj = self._eight.users[self._userid]

        _LOGGER.debug(
            "Heat Sensor: %s, Side: %s, User: %s",
            self._sensor_type,
            self._side,
            self._userid,
        )

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
        return PERCENTAGE

    async def async_update(self):
        """Retrieve latest state."""
        _LOGGER.debug("Updating Heat sensor: %s", self._sensor_type)
        self._state = self._usrobj.heating_level

    @property
    def device_state_attributes(self):
        """Return device state attributes."""
        return {
            ATTR_TARGET_HEAT: self._usrobj.target_heating_level,
            ATTR_ACTIVE_HEAT: self._usrobj.now_heating,
            ATTR_DURATION_HEAT: self._usrobj.heating_remaining,
        }

    @property
    def unique_id(self):
        """Return a unique ID for the sensor."""
        return f"{self._userid}_{self._sensor_type}"


class EightUserSensor(EightSleepUserEntity):
    """Representation of an eight sleep user-based sensor."""

    def __init__(self, eight, sensor_type, units, side):
        """Initialize the sensor."""
        super().__init__(eight)

        self._sensor_type = sensor_type
        self._mapped_name = NAME_MAP.get(f"{side}_{self._sensor_type}")
        self._name = f"Eight Sleep - {self._mapped_name}"
        self._state = None
        self._attr = None
        self._units = units

        self._side = side
        self._userid = self._eight.fetch_userid(self._side)
        self._usrobj = self._eight.users[self._userid]

        _LOGGER.debug(
            "User Sensor: %s, Side: %s, User: %s",
            self._sensor_type,
            self._side,
            self._userid,
        )

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
        if (
            "current_sleep" in self._sensor_type
            or "last_sleep" in self._sensor_type
            or "current_sleep_fitness" in self._sensor_type
        ):
            return "Score"
        if "bed_temp" in self._sensor_type:
            if self._units == "si":
                return TEMP_CELSIUS
            return TEMP_FAHRENHEIT
        return None

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        if "bed_temp" in self._sensor_type:
            return "mdi:thermometer"

    async def async_update(self):
        """Retrieve latest state."""
        _LOGGER.debug("Updating User sensor: %s", self._sensor_type)
        if "current" in self._sensor_type:
            if "fitness" in self._sensor_type:
                self._state = self._usrobj.current_sleep_fitness_score
                self._attr = self._usrobj.current_fitness_values
            else:
                self._state = self._usrobj.current_sleep_score
                self._attr = self._usrobj.current_values
        elif "last" in self._sensor_type:
            self._state = self._usrobj.last_sleep_score
            self._attr = self._usrobj.last_values
        elif "bed_temp" in self._sensor_type:
            temp = self._usrobj.current_values["bed_temp"]
            try:
                if self._units == "si":
                    self._state = round(temp, 2)
                else:
                    self._state = round((temp * 1.8) + 32, 2)
            except TypeError:
                self._state = None
        elif "sleep_stage" in self._sensor_type:
            self._state = self._usrobj.current_values["stage"]

    @property
    def device_state_attributes(self):
        """Return device state attributes."""
        if self._attr is None:
            # Skip attributes if sensor type doesn't support
            return None

        if "fitness" in self._sensor_type:
            state_attr = {
                ATTR_FIT_DATE: self._attr["date"],
                ATTR_FIT_DURATION_SCORE: self._attr["duration"],
                ATTR_FIT_ASLEEP_SCORE: self._attr["asleep"],
                ATTR_FIT_OUT_SCORE: self._attr["out"],
                ATTR_FIT_WAKEUP_SCORE: self._attr["wakeup"],
            }
            return state_attr

        state_attr = {ATTR_SESSION_START: self._attr["date"]}
        state_attr[ATTR_TNT] = self._attr["tnt"]
        state_attr[ATTR_PROCESSING] = self._attr["processing"]

        sleep_time = (
            sum(self._attr["breakdown"].values()) - self._attr["breakdown"]["awake"]
        )
        state_attr[ATTR_SLEEP_DUR] = sleep_time
        try:
            state_attr[ATTR_LIGHT_PERC] = round(
                (self._attr["breakdown"]["light"] / sleep_time) * 100, 2
            )
        except ZeroDivisionError:
            state_attr[ATTR_LIGHT_PERC] = 0
        try:
            state_attr[ATTR_DEEP_PERC] = round(
                (self._attr["breakdown"]["deep"] / sleep_time) * 100, 2
            )
        except ZeroDivisionError:
            state_attr[ATTR_DEEP_PERC] = 0

        try:
            state_attr[ATTR_REM_PERC] = round(
                (self._attr["breakdown"]["rem"] / sleep_time) * 100, 2
            )
        except ZeroDivisionError:
            state_attr[ATTR_REM_PERC] = 0

        try:
            if self._units == "si":
                room_temp = round(self._attr["room_temp"], 2)
            else:
                room_temp = round((self._attr["room_temp"] * 1.8) + 32, 2)
        except TypeError:
            room_temp = None

        try:
            if self._units == "si":
                bed_temp = round(self._attr["bed_temp"], 2)
            else:
                bed_temp = round((self._attr["bed_temp"] * 1.8) + 32, 2)
        except TypeError:
            bed_temp = None

        if "current" in self._sensor_type:
            try:
                state_attr[ATTR_RESP_RATE] = round(self._attr["resp_rate"], 2)
            except TypeError:
                state_attr[ATTR_RESP_RATE] = None
            try:
                state_attr[ATTR_HEART_RATE] = round(self._attr["heart_rate"], 2)
            except TypeError:
                state_attr[ATTR_HEART_RATE] = None
            state_attr[ATTR_SLEEP_STAGE] = self._attr["stage"]
            state_attr[ATTR_ROOM_TEMP] = room_temp
            state_attr[ATTR_BED_TEMP] = bed_temp
        elif "last" in self._sensor_type:
            try:
                state_attr[ATTR_AVG_RESP_RATE] = round(self._attr["resp_rate"], 2)
            except TypeError:
                state_attr[ATTR_AVG_RESP_RATE] = None
            try:
                state_attr[ATTR_AVG_HEART_RATE] = round(self._attr["heart_rate"], 2)
            except TypeError:
                state_attr[ATTR_AVG_HEART_RATE] = None
            state_attr[ATTR_AVG_ROOM_TEMP] = room_temp
            state_attr[ATTR_AVG_BED_TEMP] = bed_temp

        return state_attr

    @property
    def unique_id(self):
        """Return a unique ID for the sensor."""
        return f"{self._userid}_{self._sensor_type}"


class EightRoomSensor(EightSleepUserEntity):
    """Representation of an eight sleep room sensor."""

    def __init__(self, eight, sensor_type, units):
        """Initialize the sensor."""
        super().__init__(eight)

        self._sensor_type = sensor_type
        self._mapped_name = NAME_MAP.get(self._sensor_type)
        self._name = f"Eight Sleep - {self._mapped_name}"
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
        _LOGGER.debug("Updating Room sensor: %s", self._sensor_type)
        temp = self._eight.room_temperature()
        try:
            if self._units == "si":
                self._state = round(temp, 2)
            else:
                self._state = round((temp * 1.8) + 32, 2)
        except TypeError:
            self._state = None

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        if self._units == "si":
            return TEMP_CELSIUS
        return TEMP_FAHRENHEIT

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return "mdi:thermometer"

    @property
    def unique_id(self):
        """Return a unique ID for the sensor."""
        return self._sensor_type

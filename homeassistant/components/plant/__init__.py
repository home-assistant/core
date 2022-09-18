"""Support for monitoring plants."""
from collections import deque
from contextlib import suppress
from datetime import datetime, timedelta
import logging

import voluptuous as vol

from homeassistant.components.recorder import get_instance, history
from homeassistant.const import (
    ATTR_TEMPERATURE,
    ATTR_UNIT_OF_MEASUREMENT,
    CONDUCTIVITY,
    CONF_SENSORS,
    LIGHT_LUX,
    PERCENTAGE,
    STATE_OK,
    STATE_PROBLEM,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "plant"

READING_BATTERY = "battery"
READING_TEMPERATURE = ATTR_TEMPERATURE
READING_MOISTURE = "moisture"
READING_CONDUCTIVITY = "conductivity"
READING_BRIGHTNESS = "brightness"

ATTR_PROBLEM = "problem"
ATTR_SENSORS = "sensors"
PROBLEM_NONE = "none"
ATTR_MAX_BRIGHTNESS_HISTORY = "max_brightness"

# we're not returning only one value, we're returning a dict here. So we need
# to have a separate literal for it to avoid confusion.
ATTR_DICT_OF_UNITS_OF_MEASUREMENT = "unit_of_measurement_dict"

CONF_MIN_BATTERY_LEVEL = f"min_{READING_BATTERY}"
CONF_MIN_TEMPERATURE = f"min_{READING_TEMPERATURE}"
CONF_MAX_TEMPERATURE = f"max_{READING_TEMPERATURE}"
CONF_MIN_MOISTURE = f"min_{READING_MOISTURE}"
CONF_MAX_MOISTURE = f"max_{READING_MOISTURE}"
CONF_MIN_CONDUCTIVITY = f"min_{READING_CONDUCTIVITY}"
CONF_MAX_CONDUCTIVITY = f"max_{READING_CONDUCTIVITY}"
CONF_MIN_BRIGHTNESS = f"min_{READING_BRIGHTNESS}"
CONF_MAX_BRIGHTNESS = f"max_{READING_BRIGHTNESS}"
CONF_CHECK_DAYS = "check_days"

CONF_SENSOR_BATTERY_LEVEL = READING_BATTERY
CONF_SENSOR_MOISTURE = READING_MOISTURE
CONF_SENSOR_CONDUCTIVITY = READING_CONDUCTIVITY
CONF_SENSOR_TEMPERATURE = READING_TEMPERATURE
CONF_SENSOR_BRIGHTNESS = READING_BRIGHTNESS

DEFAULT_MIN_BATTERY_LEVEL = 20
DEFAULT_MIN_MOISTURE = 20
DEFAULT_MAX_MOISTURE = 60
DEFAULT_MIN_CONDUCTIVITY = 500
DEFAULT_MAX_CONDUCTIVITY = 3000
DEFAULT_CHECK_DAYS = 3

SCHEMA_SENSORS = vol.Schema(
    {
        vol.Optional(CONF_SENSOR_BATTERY_LEVEL): cv.entity_id,
        vol.Optional(CONF_SENSOR_MOISTURE): cv.entity_id,
        vol.Optional(CONF_SENSOR_CONDUCTIVITY): cv.entity_id,
        vol.Optional(CONF_SENSOR_TEMPERATURE): cv.entity_id,
        vol.Optional(CONF_SENSOR_BRIGHTNESS): cv.entity_id,
    }
)

PLANT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SENSORS): vol.Schema(SCHEMA_SENSORS),
        vol.Optional(
            CONF_MIN_BATTERY_LEVEL, default=DEFAULT_MIN_BATTERY_LEVEL
        ): cv.positive_int,
        vol.Optional(CONF_MIN_TEMPERATURE): vol.Coerce(float),
        vol.Optional(CONF_MAX_TEMPERATURE): vol.Coerce(float),
        vol.Optional(CONF_MIN_MOISTURE, default=DEFAULT_MIN_MOISTURE): cv.positive_int,
        vol.Optional(CONF_MAX_MOISTURE, default=DEFAULT_MAX_MOISTURE): cv.positive_int,
        vol.Optional(
            CONF_MIN_CONDUCTIVITY, default=DEFAULT_MIN_CONDUCTIVITY
        ): cv.positive_int,
        vol.Optional(
            CONF_MAX_CONDUCTIVITY, default=DEFAULT_MAX_CONDUCTIVITY
        ): cv.positive_int,
        vol.Optional(CONF_MIN_BRIGHTNESS): cv.positive_int,
        vol.Optional(CONF_MAX_BRIGHTNESS): cv.positive_int,
        vol.Optional(CONF_CHECK_DAYS, default=DEFAULT_CHECK_DAYS): cv.positive_int,
    }
)

DOMAIN = "plant"

CONFIG_SCHEMA = vol.Schema({DOMAIN: {cv.string: PLANT_SCHEMA}}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Plant component."""
    component = EntityComponent[Plant](_LOGGER, DOMAIN, hass)

    entities = []
    for plant_name, plant_config in config[DOMAIN].items():
        _LOGGER.info("Added plant %s", plant_name)
        entity = Plant(plant_name, plant_config)
        entities.append(entity)

    await component.async_add_entities(entities)
    return True


class Plant(Entity):
    """Plant monitors the well-being of a plant.

    It also checks the measurements against
    configurable min and max values.
    """

    _attr_should_poll = False

    READINGS = {
        READING_BATTERY: {
            ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
            "min": CONF_MIN_BATTERY_LEVEL,
        },
        READING_TEMPERATURE: {
            ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
            "min": CONF_MIN_TEMPERATURE,
            "max": CONF_MAX_TEMPERATURE,
        },
        READING_MOISTURE: {
            ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
            "min": CONF_MIN_MOISTURE,
            "max": CONF_MAX_MOISTURE,
        },
        READING_CONDUCTIVITY: {
            ATTR_UNIT_OF_MEASUREMENT: CONDUCTIVITY,
            "min": CONF_MIN_CONDUCTIVITY,
            "max": CONF_MAX_CONDUCTIVITY,
        },
        READING_BRIGHTNESS: {
            ATTR_UNIT_OF_MEASUREMENT: LIGHT_LUX,
            "min": CONF_MIN_BRIGHTNESS,
            "max": CONF_MAX_BRIGHTNESS,
        },
    }

    def __init__(self, name, config):
        """Initialize the Plant component."""
        self._config = config
        self._sensormap = {}
        self._readingmap = {}
        self._unit_of_measurement = {}
        for reading, entity_id in config["sensors"].items():
            self._sensormap[entity_id] = reading
            self._readingmap[reading] = entity_id
        self._state = None
        self._name = name
        self._battery = None
        self._moisture = None
        self._conductivity = None
        self._temperature = None
        self._brightness = None
        self._problems = PROBLEM_NONE

        self._conf_check_days = 3  # default check interval: 3 days
        if CONF_CHECK_DAYS in self._config:
            self._conf_check_days = self._config[CONF_CHECK_DAYS]
        self._brightness_history = DailyHistory(self._conf_check_days)

    @callback
    def _state_changed_event(self, event):
        """Sensor state change event."""
        self.state_changed(event.data.get("entity_id"), event.data.get("new_state"))

    @callback
    def state_changed(self, entity_id, new_state):
        """Update the sensor status."""
        if new_state is None:
            return
        value = new_state.state
        _LOGGER.debug("Received callback from %s with value %s", entity_id, value)
        if value == STATE_UNKNOWN:
            return

        reading = self._sensormap[entity_id]
        if reading == READING_MOISTURE:
            if value != STATE_UNAVAILABLE:
                value = int(float(value))
            self._moisture = value
        elif reading == READING_BATTERY:
            if value != STATE_UNAVAILABLE:
                value = int(float(value))
            self._battery = value
        elif reading == READING_TEMPERATURE:
            if value != STATE_UNAVAILABLE:
                value = float(value)
            self._temperature = value
        elif reading == READING_CONDUCTIVITY:
            if value != STATE_UNAVAILABLE:
                value = int(float(value))
            self._conductivity = value
        elif reading == READING_BRIGHTNESS:
            if value != STATE_UNAVAILABLE:
                value = int(float(value))
            self._brightness = value
            self._brightness_history.add_measurement(
                self._brightness, new_state.last_updated
            )
        else:
            raise HomeAssistantError(
                f"Unknown reading from sensor {entity_id}: {value}"
            )
        if ATTR_UNIT_OF_MEASUREMENT in new_state.attributes:
            self._unit_of_measurement[reading] = new_state.attributes.get(
                ATTR_UNIT_OF_MEASUREMENT
            )
        self._update_state()

    def _update_state(self):
        """Update the state of the class based sensor data."""
        result = []
        for sensor_name in self._sensormap.values():
            params = self.READINGS[sensor_name]
            if (value := getattr(self, f"_{sensor_name}")) is not None:
                if value == STATE_UNAVAILABLE:
                    result.append(f"{sensor_name} unavailable")
                else:
                    if sensor_name == READING_BRIGHTNESS:
                        result.append(
                            self._check_min(
                                sensor_name, self._brightness_history.max, params
                            )
                        )
                    else:
                        result.append(self._check_min(sensor_name, value, params))
                    result.append(self._check_max(sensor_name, value, params))

        result = [r for r in result if r is not None]

        if result:
            self._state = STATE_PROBLEM
            self._problems = ", ".join(result)
        else:
            self._state = STATE_OK
            self._problems = PROBLEM_NONE
        _LOGGER.debug("New data processed")
        self.async_write_ha_state()

    def _check_min(self, sensor_name, value, params):
        """If configured, check the value against the defined minimum value."""
        if "min" in params and params["min"] in self._config:
            min_value = self._config[params["min"]]
            if value < min_value:
                return f"{sensor_name} low"

    def _check_max(self, sensor_name, value, params):
        """If configured, check the value against the defined maximum value."""
        if "max" in params and params["max"] in self._config:
            max_value = self._config[params["max"]]
            if value > max_value:
                return f"{sensor_name} high"
        return None

    async def async_added_to_hass(self):
        """After being added to hass, load from history."""
        if "recorder" in self.hass.config.components:
            # only use the database if it's configured
            await get_instance(self.hass).async_add_executor_job(
                self._load_history_from_db
            )
            self.async_write_ha_state()

        async_track_state_change_event(
            self.hass, list(self._sensormap), self._state_changed_event
        )

        for entity_id in self._sensormap:
            if (state := self.hass.states.get(entity_id)) is not None:
                self.state_changed(entity_id, state)

    def _load_history_from_db(self):
        """Load the history of the brightness values from the database.

        This only needs to be done once during startup.
        """

        start_date = dt_util.utcnow() - timedelta(days=self._conf_check_days)
        entity_id = self._readingmap.get(READING_BRIGHTNESS)
        if entity_id is None:
            _LOGGER.debug(
                "Not reading the history from the database as "
                "there is no brightness sensor configured"
            )
            return
        _LOGGER.debug("Initializing values for %s from the database", self._name)
        lower_entity_id = entity_id.lower()
        history_list = history.state_changes_during_period(
            self.hass,
            start_date,
            entity_id=lower_entity_id,
            no_attributes=True,
        )
        for state in history_list.get(lower_entity_id, []):
            # filter out all None, NaN and "unknown" states
            # only keep real values
            with suppress(ValueError):
                self._brightness_history.add_measurement(
                    int(state.state), state.last_updated
                )

        _LOGGER.debug("Initializing from database completed")

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the entity."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the attributes of the entity.

        Provide the individual measurements from the
        sensor in the attributes of the device.
        """
        attrib = {
            ATTR_PROBLEM: self._problems,
            ATTR_SENSORS: self._readingmap,
            ATTR_DICT_OF_UNITS_OF_MEASUREMENT: self._unit_of_measurement,
        }

        for reading in self._sensormap.values():
            attrib[reading] = getattr(self, f"_{reading}")

        if self._brightness_history.max is not None:
            attrib[ATTR_MAX_BRIGHTNESS_HISTORY] = self._brightness_history.max

        return attrib


class DailyHistory:
    """Stores one measurement per day for a maximum number of days.

    At the moment only the maximum value per day is kept.
    """

    def __init__(self, max_length):
        """Create new DailyHistory with a maximum length of the history."""
        self.max_length = max_length
        self._days = None
        self._max_dict = {}
        self.max = None

    def add_measurement(self, value, timestamp=None):
        """Add a new measurement for a certain day."""
        day = (timestamp or datetime.now()).date()
        if not isinstance(value, (int, float)):
            return
        if self._days is None:
            self._days = deque()
            self._add_day(day, value)
        else:
            current_day = self._days[-1]
            if day == current_day:
                self._max_dict[day] = max(value, self._max_dict[day])
            elif day > current_day:
                self._add_day(day, value)
            else:
                _LOGGER.warning("Received old measurement, not storing it")

        self.max = max(self._max_dict.values())

    def _add_day(self, day, value):
        """Add a new day to the history.

        Deletes the oldest day, if the queue becomes too long.
        """
        if len(self._days) == self.max_length:
            oldest = self._days.popleft()
            del self._max_dict[oldest]
        self._days.append(day)
        if not isinstance(value, (int, float)):
            return
        self._max_dict[day] = value

"""
Provides functionality to interact with boiler/geyser controller units.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/boiler/
"""
import logging
import os
from numbers import Number
import voluptuous as vol

from homeassistant.helpers.entity_component import EntityComponent

from homeassistant.config import load_yaml_config_file
from homeassistant.util.temperature import convert as convert_temperature
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA  # noqa
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_TEMPERATURE, STATE_ON, STATE_OFF, STATE_UNKNOWN,
    # TEMP_CELSIUS
    )

DOMAIN = "boiler"

BOILER_CLASSES = [
    None,                   # Default - electric?
    'electric',             # Normal electric element
    'heatpump',             # Uses heatpump as element
    'on demand electric',   # Probably don't have/need controllers
    'on demand gas',        # Probably don't have/need controllers
    'pv solar',             # Uses DC Element
    'pumped solar',         # Pumps between tank and solar collector
    'thermosiphon solar',   # Siphons between tank and solar collector
]

BOILER_CLASSES_SCHEMA = vol.All(vol.Lower, vol.In(BOILER_CLASSES))

ENTITY_ID_FORMAT = DOMAIN + ".{}"
SCAN_INTERVAL = 60  # Every hour

SERVICE_SET_AWAY_MODE = "set_away_mode"  # trigger to lower target water temp
SERVICE_SET_GUEST_MODE = "set_guest_mode"  # trigger to raise min temp
SERVICE_SET_HOLIDAY_MODE = "set_holiday_mode"  # trigger to power off
SERVICE_SET_WATER_TEMP = "set_water_temperature"  # adjust temps
SERVICE_SET_OPERATION_MODE = "set_operation_mode"

STATE_IDLE = "idle"  # element off
STATE_HEAT = "heat"  # element on
# exchange colder collector water at night with hot geyser water
STATE_COOL = "cool"  # pump on/element off; relevant in holiday mode
# exchange hot collector water with warm geyser water
STATE_PUMP = "pump"  # pump on/element off
# exchange warm/hot geyser water with cold collector water to prevent freezing
STATE_DEFROST = "defrost"  # pump on/element might need to be switched on
# bump temp to kill bacteria if geyser temp has been below 50C for n days
STATE_KILL = "kill"  # element on
# geyser controller detected an error
STATE_ERROR = "error"

ATTR_CURRENT_WATER_TEMPERATURE = "current_water_temperature"
ATTR_CURRENT_PANEL_TEMPERATURE = "current_panel_temperature"
ATTR_TARGET_WATER_TEMPERATURE = "target_water_temperature"
ATTR_PANEL_DIFF_TEMP = "panel_differential_temp"
ATTR_AWAY_MODE = "away_mode"
ATTR_GUEST_MODE = "guest_mode"
ATTR_TOTAL_GUESTS = "total_guests"
ATTR_HOLIDAY_MODE = "holiday_mode"
ATTR_HOLIDAY_DURATION = "holiday_duration"
ATTR_OPERATION_MODE = "operation_mode"
ATTR_OPERATION_LIST = "operation_list"

CONVERTIBLE_ATTRIBUTE = [
    ATTR_TEMPERATURE,
    ATTR_TARGET_WATER_TEMPERATURE,
]

_LOGGER = logging.getLogger(__name__)

SET_AWAY_MODE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_AWAY_MODE): cv.boolean,
})
SET_GUEST_MODE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_GUEST_MODE): cv.boolean,
    vol.Required(ATTR_TOTAL_GUESTS): cv.positive_int,
})
SET_HOLIDAY_MODE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_HOLIDAY_MODE): cv.boolean,
    vol.Required(ATTR_HOLIDAY_DURATION): cv.positive_int,
})
SET_WATER_TEMPERATURE_SCHEMA = vol.Schema({
    vol.Exclusive(ATTR_TARGET_WATER_TEMPERATURE,
                  'temperature'): vol.Coerce(float),
    vol.Optional(ATTR_PANEL_DIFF_TEMP, 'temperature'): vol.Coerce(float),
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
})
SET_OPERATION_MODE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_OPERATION_MODE): cv.string,
})


def set_away_mode(hass, away_mode, entity_id=None):
    """Turn all or specified boiler controller devices away mode on."""
    data = {
        ATTR_AWAY_MODE: away_mode
    }
    # Add duration to work out new idle temp
    # e.g. off to work, out to dinner or overnight

    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_SET_AWAY_MODE, data)


def set_guest_mode(hass, guest_mode, total_guests, entity_id=None):
    """Turn all or specified boiler controller devices guest mode on."""
    data = {
        ATTR_GUEST_MODE: guest_mode,
        ATTR_TOTAL_GUESTS: total_guests
    }

    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_SET_GUEST_MODE, data)


def set_holiday_mode(hass, holiday_mode, holiday_duration, entity_id=None):
    """Turn all or specified boiler controller devices holiday mode on."""
    # Can away mode be used for this?
    data = {
        ATTR_HOLIDAY_MODE: holiday_mode,
        ATTR_HOLIDAY_DURATION: holiday_duration
    }

    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_SET_HOLIDAY_MODE, data)


# pylint: disable=too-many-arguments
def set_temperature(hass, entity_id=None,
                    target_water_temperature=None,
                    panel_diff_temp=None):
    """
    Set new target temperatures.

    Used when either new target temp or panel differential temp is required.
    """
    kwargs = {
        key: value for key, value in [
            (ATTR_TARGET_WATER_TEMPERATURE, target_water_temperature),
            (ATTR_PANEL_DIFF_TEMP, panel_diff_temp),
            (ATTR_ENTITY_ID, entity_id),
        ] if value is not None
    }
    _LOGGER.debug("set_temperature start data=%s", kwargs)
    hass.services.call(DOMAIN, SERVICE_SET_WATER_TEMP, kwargs)


def set_operation_mode(hass, operation_mode, entity_id=None):
    """Set new target operation mode."""
    data = {ATTR_OPERATION_MODE: operation_mode}

    if entity_id is not None:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_SET_OPERATION_MODE, data)


# pylint: disable=too-many-branches
def setup(hass, config):
    """Setup boiler/geyser controller."""
    component = EntityComponent(_LOGGER, DOMAIN, hass, SCAN_INTERVAL)
    component.setup(config)

    descriptions = load_yaml_config_file(
        os.path.join(os.path.dirname(__file__), 'services.yaml'))

    def away_mode_set_service(service):
        """Set away mode on target boiler controller devices."""
        target_boiler = component.extract_from_service(service)

        away_mode = service.data.get(ATTR_AWAY_MODE)

        if away_mode is None:
            _LOGGER.error(
                "Received call to %s without attribute %s",
                SERVICE_SET_AWAY_MODE, ATTR_AWAY_MODE)
            return

        for boiler in target_boiler:
            if away_mode:
                boiler.turn_away_mode_on()
            else:
                boiler.turn_away_mode_off()

            if boiler.should_poll:
                boiler.update_ha_state(True)

    hass.services.register(
        DOMAIN, SERVICE_SET_AWAY_MODE, away_mode_set_service,
        descriptions.get(SERVICE_SET_AWAY_MODE),
        schema=SET_AWAY_MODE_SCHEMA)

    def guest_mode_set_service(service):
        """Set guest mode on target boiler devices."""
        target_boiler = component.extract_from_service(service)

        guest_mode = service.data.get(ATTR_GUEST_MODE)
        total_guests = service.data.get(ATTR_TOTAL_GUESTS)

        if guest_mode is None:
            _LOGGER.error(
                "Received call to %s without attribute %s",
                SERVICE_SET_GUEST_MODE, ATTR_GUEST_MODE)
            return

        for boiler in target_boiler:
            if guest_mode:
                boiler.turn_guest_mode_on(total_guests)
            else:
                # Assuming no needs to set days to zero, thus no kwargs
                boiler.turn_guest_mode_off()

            if boiler.should_poll:
                boiler.update_ha_state(True)

    hass.services.register(
        DOMAIN, SERVICE_SET_GUEST_MODE, guest_mode_set_service,
        descriptions.get(SERVICE_SET_GUEST_MODE),
        schema=SET_GUEST_MODE_SCHEMA)

    def holiday_mode_set_service(service):
        """Set holiday mode on target boiler devices."""
        target_boiler = component.extract_from_service(service)

        holiday_mode = service.data.get(ATTR_HOLIDAY_MODE)
        holiday_duration = service.data.get(ATTR_HOLIDAY_DURATION)

        if holiday_mode is None:
            _LOGGER.error(
                "Received call to %s without attribute %s",
                SERVICE_SET_HOLIDAY_MODE, ATTR_HOLIDAY_MODE)
            return

        for boiler in target_boiler:
            if holiday_mode:
                boiler.turn_holiday_mode_on(holiday_duration)
            else:
                # Assuming no needs to set days to zero, thus no kwargs
                boiler.turn_holiday_mode_off()

            if boiler.should_poll:
                boiler.update_ha_state(True)

    hass.services.register(
        DOMAIN, SERVICE_SET_HOLIDAY_MODE, holiday_mode_set_service,
        descriptions.get(SERVICE_SET_HOLIDAY_MODE),
        schema=SET_HOLIDAY_MODE_SCHEMA)

    def temperature_set_service(service):
        """Set temperatures on the target climate devices."""
        target_boiler = component.extract_from_service(service)

        for boiler in target_boiler:
            kwargs = {}
            for value, temp in service.data.items():
                if value in CONVERTIBLE_ATTRIBUTE:
                    kwargs[value] = convert_temperature(
                        temp,
                        hass.config.units.temperature_unit,
                        boiler.unit_of_measurement
                    )
                else:
                    kwargs[value] = temp

            # why kwargs and not target_temp and diff_temp?
            boiler.set_temperature(**kwargs)
            if boiler.should_poll:
                boiler.update_ha_state(True)

    hass.services.register(
        DOMAIN, SERVICE_SET_WATER_TEMP, temperature_set_service,
        descriptions.get(SERVICE_SET_WATER_TEMP),
        schema=SET_WATER_TEMPERATURE_SCHEMA)

    def operation_set_service(service):
        """Set operating mode on the target boiler devices."""
        target_boiler = component.extract_from_service(service)

        operation_mode = service.data.get(ATTR_OPERATION_MODE)

        if operation_mode is None:
            _LOGGER.error(
                "Received call to %s without attribute %s",
                SERVICE_SET_OPERATION_MODE, ATTR_OPERATION_MODE)
            return

        for boiler in target_boiler:
            boiler.set_operation_mode(operation_mode)

            if boiler.should_poll:
                boiler.update_ha_state(True)

    hass.services.register(
        DOMAIN, SERVICE_SET_OPERATION_MODE, operation_set_service,
        descriptions.get(SERVICE_SET_OPERATION_MODE),
        schema=SET_OPERATION_MODE_SCHEMA)

    return True


class BoilerDevice(Entity):
    """Representation of a boiler device."""

    # pylint: disable=too-many-public-methods,no-self-use
    @property
    def boiler_class(self):
        """Return the class of this boiler, from BOILER_CLASSES."""
        return None

    @property
    def state(self):
        """Return the current state."""
        return self.current_operation or STATE_UNKNOWN

    @property
    def state_attributes(self):
        """Return the optional state attributes."""
        data = {
            ATTR_CURRENT_WATER_TEMPERATURE:
            self._convert_for_display(self.current_water_temperature),
            ATTR_TARGET_WATER_TEMPERATURE:
            self._convert_for_display(self.target_water_temperature),
            ATTR_PANEL_DIFF_TEMP:
            self._convert_for_display(self.panel_differential_temperature)
        }

        operation_mode = self.current_operation
        if operation_mode is not None:
            data[ATTR_OPERATION_MODE] = operation_mode
            data[ATTR_OPERATION_LIST] = self.operation_list

        is_away = self.is_away_mode_on
        if is_away is not None:
            data[ATTR_AWAY_MODE] = STATE_ON if is_away else STATE_OFF

        is_guest = self.is_guest_mode_on
        if is_guest is not None:
            data[ATTR_GUEST_MODE] = STATE_ON if is_guest else STATE_OFF
            data[ATTR_TOTAL_GUESTS] = self.total_guests

        is_holiday = self.is_holiday_mode_on
        if is_holiday is not None:
            data[ATTR_HOLIDAY_MODE] = STATE_ON if is_holiday else STATE_OFF
            data[ATTR_HOLIDAY_DURATION] = self.holiday_duration

        return data

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        raise NotImplementedError

    @property
    def current_operation(self):
        """Return current operation ie. heating, cooling, pumping, idle."""
        return None

    @property
    def operation_list(self):
        """List of available operation modes."""
        return None

    @property
    def current_water_temperature(self):
        """Return the current water temperature."""
        return None

    @property
    def target_water_temperature(self):
        """Return the target water temperature."""
        return None

    @property
    def panel_differential_temperature(self):
        """Return the differential temperature at which to start pumping."""
        return None

    @property
    def panel_temperature(self):
        """Return the temperature of the solar collector."""
        return None

    @property
    def is_away_mode_on(self):
        """Return true if away mode is on."""
        return None

    @property
    def is_guest_mode_on(self):
        """Return true if guest mode is on."""
        return None

    @property
    def total_guests(self):
        """Return number of guests."""
        return None

    @property
    def is_holiday_mode_on(self):
        """Return true if holiday mode is on."""
        return None

    @property
    def holiday_duration(self):
        """Return the duration of the holiday, in days."""
        return None

    @property
    def is_pump_on(self):
        """Return true if pump is on."""
        return None

    @property
    def is_element_on(self):
        """Return true if element is on."""
        return None

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        # Number of guests and holiday duration are deviation off target temp.
        raise NotImplementedError()

    def set_operation_mode(self, operation_mode):
        """Set new target operation mode."""
        raise NotImplementedError()

    def turn_element_on(self):
        """Turn element on."""
        raise NotImplementedError()

    def turn_element_off(self):
        """Turn element off."""
        raise NotImplementedError()

    def turn_pump_on(self):
        """Turn pump on."""
        raise NotImplementedError()

    def turn_pump_off(self):
        """Turn pump off."""
        raise NotImplementedError()

    def turn_away_mode_on(self):
        """Turn away mode on."""
        raise NotImplementedError()

    def turn_away_mode_off(self):
        """Turn away mode off."""
        raise NotImplementedError()

    def turn_guest_mode_on(self, total_guests):
        """Turn guest mode on."""
        raise NotImplementedError()

    def turn_guest_mode_off(self):
        """Turn guest mode off."""
        raise NotImplementedError()

    def turn_holiday_mode_on(self, holiday_duration):
        """Turn holiday mode on."""
        raise NotImplementedError()

    def turn_holiday_mode_off(self):
        """Turn holiday mode off."""
        raise NotImplementedError()

    def _convert_for_display(self, temp):
        """Convert temperature into preferred units for display purposes."""
        if temp is None or not isinstance(temp, Number):
            return temp

        value = convert_temperature(temp, self.unit_of_measurement,
                                    self.hass.config.units.temperature_unit)

        # boiler controllers unlikely to supply decimals
        decimal_count = 0
        return round(value, decimal_count)

"""
Tado component to create a climate device for each zone.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.tado/
"""
import logging

from homeassistant.const import (PRECISION_TENTHS, TEMP_CELSIUS)
from homeassistant.components.climate import (
    ClimateDevice, SUPPORT_TARGET_TEMPERATURE, SUPPORT_OPERATION_MODE,
    DEFAULT_MIN_TEMP, DEFAULT_MAX_TEMP)
from homeassistant.util.temperature import convert as convert_temperature
from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.components.tado import DATA_TADO

_LOGGER = logging.getLogger(__name__)

CONST_MODE_SMART_SCHEDULE = 'SMART_SCHEDULE'  # Default mytado mode
CONST_MODE_OFF = 'OFF'  # Switch off heating in a zone
CONST_MODE_COOL = 'COOL'  # Turn an ac device into cooling mode
CONST_MODE_HEAT = 'HEAT'  # Turn an ac device into heating mode

# When we change the temperature setting, we need an overlay mode
# wait until tado changes the mode automatic
CONST_OVERLAY_TADO_MODE = 'TADO_MODE'
# the user has change the temperature or mode manually
CONST_OVERLAY_MANUAL = 'MANUAL'
# the temperature will be reset after a timespan
CONST_OVERLAY_TIMER = 'TIMER'

CONST_MODE_FAN_HIGH = 'HIGH'
CONST_MODE_FAN_MIDDLE = 'MIDDLE'
CONST_MODE_FAN_LOW = 'LOW'

FAN_MODES_LIST = {
    CONST_MODE_FAN_HIGH: 'High',
    CONST_MODE_FAN_MIDDLE: 'Middle',
    CONST_MODE_FAN_LOW: 'Low',
    CONST_MODE_OFF: 'Off',
}

OPERATION_MANUAL_HOT_WATER_ON = {
    CONST_OVERLAY_MANUAL: 'Manual (On)',
    CONST_OVERLAY_TIMER: 'Timer (On)',
    CONST_OVERLAY_TADO_MODE: 'Tado mode (On)',
}

OPERATION_MANUAL_COOL = {
    CONST_OVERLAY_MANUAL: 'Manual (Cool)',
    CONST_OVERLAY_TIMER: 'Timer (Cool)',
    CONST_OVERLAY_TADO_MODE: 'Tado mode (Cool)',
}

OPERATION_MANUAL = {
    CONST_OVERLAY_MANUAL: 'Manual',
    CONST_OVERLAY_TIMER: 'Timer',
    CONST_OVERLAY_TADO_MODE: 'Tado mode',
}

OPERATION_LIST = {
    CONST_MODE_SMART_SCHEDULE: 'Smart schedule',
    CONST_MODE_OFF: 'Off',
}

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_OPERATION_MODE


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Tado climate platform."""
    tado = hass.data[DATA_TADO]

    try:
        zones = tado.get_zones()
    except RuntimeError:
        _LOGGER.error("Unable to get zone info from mytado")
        return

    climate_devices = []
    for zone in zones:
        device = create_climate_device(
            tado, hass, zone, zone['name'], zone['id'])
        if not device:
            continue
        climate_devices.append(device)

    if climate_devices:
        add_entities(climate_devices, True)


def create_climate_device(tado, hass, zone, name, zone_id):
    """Create a Tado climate device."""
    capabilities = tado.get_capabilities(zone_id)

    unit = TEMP_CELSIUS
    device_type = capabilities['type']
    min_temp = {}
    max_temp = {}
    is_device_climate_controllable = False
    is_manual_temperature = False

    if CONST_MODE_COOL in capabilities:
        is_device_climate_controllable = True
        is_manual_temperature = True
        temperatures = capabilities[CONST_MODE_COOL]['temperatures']
        min_temp[CONST_MODE_COOL] = hass.config.units.temperature(
            float(temperatures['celsius']['min']), unit)
        max_temp[CONST_MODE_COOL] = hass.config.units.temperature(
            float(temperatures['celsius']['max']), unit)
    if CONST_MODE_HEAT in capabilities:
        is_device_climate_controllable = True
        is_manual_temperature = True
        temperatures = capabilities[CONST_MODE_HEAT]['temperatures']
        min_temp[CONST_MODE_HEAT] = hass.config.units.temperature(
            float(temperatures['celsius']['min']), unit)
        max_temp[CONST_MODE_HEAT] = hass.config.units.temperature(
            float(temperatures['celsius']['max']), unit)
    if 'temperatures' in capabilities:
        is_device_climate_controllable = True
        is_manual_temperature = True
        temperatures = capabilities['temperatures']
        min_temp[CONST_MODE_HEAT] = hass.config.units.temperature(
            float(temperatures['celsius']['min']), unit)
        max_temp[CONST_MODE_HEAT] = hass.config.units.temperature(
            float(temperatures['celsius']['max']), unit)
    if device_type == "HOT_WATER" and 'temperatures' not in capabilities:
        is_device_climate_controllable = True
        is_manual_temperature = False
    if not is_device_climate_controllable:
        _LOGGER.debug("Received zone %s has no temperature; not adding", name)
        return

    data_id = 'zone {} {}'.format(name, zone_id)
    device = TadoClimate(tado,
                         name, zone_id, data_id,
                         min_temp,
                         max_temp,
                         device_type,
                         is_manual_temperature)

    tado.add_sensor(data_id, {
        'id': zone_id,
        'zone': zone,
        'name': name,
        'climate': device
    })

    return device


class TadoClimate(ClimateDevice):
    """Representation of a tado climate device."""

    def __init__(self, store, zone_name, zone_id, data_id,
                 min_temp, max_temp, device_type, is_manual_temperature,
                 tolerance=0.3):
        """Initialize of Tado climate device."""
        self._store = store
        self._data_id = data_id

        self.zone_name = zone_name
        self.zone_id = zone_id

        self._device_type = device_type

        self._active = False
        self._device_is_active = False

        self._unit = TEMP_CELSIUS
        self._cur_temp = None
        self._cur_humidity = None
        self._is_away = False
        self._min_temp = min_temp
        self._max_temp = max_temp
        self._target_temp = None
        self._is_manual_temperature = is_manual_temperature
        self._tolerance = tolerance
        self._mode = None
        self._current_fan = CONST_MODE_OFF
        self._current_operation = CONST_MODE_SMART_SCHEDULE
        self._overlay_mode = CONST_MODE_SMART_SCHEDULE

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def name(self):
        """Return the name of the device."""
        return self.zone_name

    @property
    def current_humidity(self):
        """Return the current humidity."""
        return self._cur_humidity

    @property
    def current_temperature(self):
        """Return the sensor temperature."""
        return self._cur_temp

    @property
    def current_operation(self):
        """Return current readable operation mode."""
        if self._current_operation in OPERATION_MANUAL:
            if self._mode == CONST_MODE_COOL:
                return OPERATION_MANUAL_COOL.get(self._current_operation)
            if self._device_type == "HOT_WATER" and \
                    not self._is_manual_temperature:
                return OPERATION_MANUAL_HOT_WATER_ON.get(
                    self._current_operation)
            return OPERATION_MANUAL.get(self._current_operation)
        return OPERATION_LIST.get(self._current_operation)

    @property
    def operation_list(self):
        """Return the list of available operation modes (readable)."""
        operations = list(OPERATION_LIST.values())
        if CONST_MODE_COOL in self._min_temp:
            operations.extend(list(OPERATION_MANUAL_COOL.values()))
        elif CONST_MODE_HEAT in self._min_temp:
            operations.extend(list(OPERATION_MANUAL.values()))
        elif self._device_type == "HOT_WATER" and \
                not self._is_manual_temperature:
            operations.extend(list(OPERATION_MANUAL_HOT_WATER_ON.values()))
        return operations

    @property
    def current_fan_mode(self):
        """Return the fan setting."""
        if self._device_type == "AIR_CONDITIONING":
            return FAN_MODES_LIST.get(self._current_fan)
        return None

    @property
    def fan_list(self):
        """List of available fan modes."""
        if self._device_type == "AIR_CONDITIONING":
            return list(FAN_MODES_LIST.values())
        return None

    @property
    def temperature_unit(self):
        """Return the unit of measurement used by the platform."""
        return self._unit

    @property
    def is_away_mode_on(self):
        """Return true if away mode is on."""
        return self._is_away

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return PRECISION_TENTHS

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temp

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        self._current_operation = CONST_OVERLAY_TADO_MODE
        self._overlay_mode = None
        self._target_temp = temperature
        self._control_heating()

    # pylint: disable=arguments-differ
    def set_operation_mode(self, readable_operation_mode):
        """Set new operation mode."""
        operation_mode = CONST_MODE_SMART_SCHEDULE
        mode = None
        for operation, readable in OPERATION_LIST.items():
            if readable == readable_operation_mode:
                operation_mode = operation
                break
        for operation, readable in OPERATION_MANUAL_COOL.items():
            if readable == readable_operation_mode:
                operation_mode = operation
                mode = CONST_MODE_COOL
                break
        for operation, readable in OPERATION_MANUAL.items():
            if readable == readable_operation_mode:
                operation_mode = operation
                mode = CONST_MODE_HEAT
                break

        self._current_operation = operation_mode
        self._overlay_mode = None
        self._mode = mode
        self._control_heating()

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        temperature = DEFAULT_MIN_TEMP

        if self._mode in self._min_temp:
            temperature = self._min_temp[self._mode]

        return convert_temperature(temperature, self._unit,
                                   self.hass.config.units.temperature_unit)

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        temperature = DEFAULT_MAX_TEMP

        if self._mode in self._max_temp:
            temperature = self._max_temp[self._mode]

        return convert_temperature(temperature, self._unit,
                                   self.hass.config.units.temperature_unit)

    def update(self):
        """Update the state of this climate device."""
        self._store.update()

        data = self._store.get_data(self._data_id)

        if data is None:
            _LOGGER.debug("Received no data for zone %s", self.zone_name)
            return

        if 'sensorDataPoints' in data:
            sensor_data = data['sensorDataPoints']

            unit = TEMP_CELSIUS

            if 'insideTemperature' in sensor_data:
                temperature = float(
                    sensor_data['insideTemperature']['celsius'])
                self._cur_temp = self.hass.config.units.temperature(
                    temperature, unit)

            if 'humidity' in sensor_data:
                humidity = float(
                    sensor_data['humidity']['percentage'])
                self._cur_humidity = humidity

            # temperature setting will not exist when device is off
            if 'temperature' in data['setting'] and \
                    data['setting']['temperature'] is not None:
                setting = float(
                    data['setting']['temperature']['celsius'])
                self._target_temp = self.hass.config.units.temperature(
                    setting, unit)

        if 'tadoMode' in data:
            mode = data['tadoMode']
            self._is_away = mode == 'AWAY'

        if 'setting' in data:
            power = data['setting']['power']
            if power == 'OFF':
                self._current_operation = CONST_MODE_OFF
                self._current_fan = CONST_MODE_OFF
                # There is no overlay, the mode will always be
                # "SMART_SCHEDULE"
                self._overlay_mode = CONST_MODE_SMART_SCHEDULE
                self._device_is_active = False
            else:
                self._device_is_active = True

        overlay = False
        overlay_data = None
        termination = CONST_MODE_SMART_SCHEDULE
        mode = CONST_MODE_HEAT
        fan_speed = CONST_MODE_OFF

        if 'overlay' in data:
            overlay_data = data['overlay']
            overlay = overlay_data is not None

        if overlay:
            termination = overlay_data['termination']['type']

            if 'setting' in overlay_data:
                setting_data = overlay_data['setting']
                setting = setting_data is not None

            if setting:
                if 'mode' in setting_data:
                    mode = setting_data['mode']

                if 'fanSpeed' in setting_data:
                    fan_speed = setting_data['fanSpeed']

        if self._device_is_active:
            # If you set mode manually to off, there will be an overlay
            # and a termination, but we want to see the mode "OFF"
            self._overlay_mode = termination
            self._current_operation = termination

        self._mode = mode
        self._current_fan = fan_speed

    def _control_heating(self):
        """Send new target temperature to mytado."""
        if not self._active and None not in (
                self._cur_temp, self._target_temp):
            self._active = True
            _LOGGER.info("Obtained current and target temperature. "
                         "Tado thermostat active")

        if not self._active and not self._device_type == "HOT_WATER" or \
                self._current_operation == self._overlay_mode:
            return

        if self._current_operation == CONST_MODE_SMART_SCHEDULE:
            _LOGGER.info("Switching mytado.com to SCHEDULE (default) "
                         "for zone %s", self.zone_name)
            self._store.reset_zone_overlay(self.zone_id)
            self._overlay_mode = self._current_operation
            return

        if self._current_operation == CONST_MODE_OFF:
            _LOGGER.info("Switching mytado.com to OFF for zone %s",
                         self.zone_name)
            self._store.set_zone_overlay(self.zone_id, self._device_type,
                                         CONST_OVERLAY_MANUAL,
                                         None, None, None,
                                         "OFF")
            self._overlay_mode = self._current_operation
            return

        _LOGGER.info("Switching mytado.com to %s mode for zone %s",
                     self._current_operation, self.zone_name)

        self._store.set_zone_overlay(self.zone_id,
                                     self._device_type,
                                     self._current_operation,
                                     self._target_temp,
                                     None,
                                     self._mode,
                                     "ON")

        self._overlay_mode = self._current_operation

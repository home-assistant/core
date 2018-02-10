"""
Tado component to create a climate device for each zone.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.tado/
"""
import logging

from homeassistant.const import (PRECISION_TENTHS, TEMP_CELSIUS)
from homeassistant.components.climate import (
    ClimateDevice, SUPPORT_TARGET_TEMPERATURE, SUPPORT_OPERATION_MODE)
from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.components.tado import DATA_TADO

_LOGGER = logging.getLogger(__name__)

CONST_MODE_SMART_SCHEDULE = 'SMART_SCHEDULE'  # Default mytado mode
CONST_MODE_OFF = 'OFF'  # Switch off heating in a zone

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

OPERATION_LIST = {
    CONST_OVERLAY_MANUAL: 'Manual',
    CONST_OVERLAY_TIMER: 'Timer',
    CONST_OVERLAY_TADO_MODE: 'Tado mode',
    CONST_MODE_SMART_SCHEDULE: 'Smart schedule',
    CONST_MODE_OFF: 'Off',
}

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_OPERATION_MODE


def setup_platform(hass, config, add_devices, discovery_info=None):
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
        add_devices(climate_devices, True)


def create_climate_device(tado, hass, zone, name, zone_id):
    """Create a Tado climate device."""
    capabilities = tado.get_capabilities(zone_id)

    unit = TEMP_CELSIUS
    ac_mode = capabilities['type'] == 'AIR_CONDITIONING'

    if ac_mode:
        temperatures = capabilities['HEAT']['temperatures']
    elif 'temperatures' in capabilities:
        temperatures = capabilities['temperatures']
    else:
        _LOGGER.debug("Received zone %s has no temperature; not adding", name)
        return

    min_temp = float(temperatures['celsius']['min'])
    max_temp = float(temperatures['celsius']['max'])

    data_id = 'zone {} {}'.format(name, zone_id)
    device = TadoClimate(tado,
                         name, zone_id, data_id,
                         hass.config.units.temperature(min_temp, unit),
                         hass.config.units.temperature(max_temp, unit),
                         ac_mode)

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
                 min_temp, max_temp, ac_mode,
                 tolerance=0.3):
        """Initialize of Tado climate device."""
        self._store = store
        self._data_id = data_id

        self.zone_name = zone_name
        self.zone_id = zone_id

        self.ac_mode = ac_mode

        self._active = False
        self._device_is_active = False

        self._unit = TEMP_CELSIUS
        self._cur_temp = None
        self._cur_humidity = None
        self._is_away = False
        self._min_temp = min_temp
        self._max_temp = max_temp
        self._target_temp = None
        self._tolerance = tolerance
        self._cooling = False

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
        if self._cooling:
            return "Cooling"
        return OPERATION_LIST.get(self._current_operation)

    @property
    def operation_list(self):
        """Return the list of available operation modes (readable)."""
        return list(OPERATION_LIST.values())

    @property
    def current_fan_mode(self):
        """Return the fan setting."""
        if self.ac_mode:
            return FAN_MODES_LIST.get(self._current_fan)
        return None

    @property
    def fan_list(self):
        """List of available fan modes."""
        if self.ac_mode:
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

    def set_operation_mode(self, readable_operation_mode):
        """Set new operation mode."""
        operation_mode = CONST_MODE_SMART_SCHEDULE

        for mode, readable in OPERATION_LIST.items():
            if readable == readable_operation_mode:
                operation_mode = mode
                break

        self._current_operation = operation_mode
        self._overlay_mode = None
        self._control_heating()

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        if self._min_temp:
            return self._min_temp
        # get default temp from super class
        return super().min_temp

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        if self._max_temp:
            return self._max_temp
        #  Get default temp from super class
        return super().max_temp

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
        cooling = False
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
                    cooling = setting_data['mode'] == 'COOL'

                if 'fanSpeed' in setting_data:
                    fan_speed = setting_data['fanSpeed']

        if self._device_is_active:
            # If you set mode manually to off, there will be an overlay
            # and a termination, but we want to see the mode "OFF"
            self._overlay_mode = termination
            self._current_operation = termination

        self._cooling = cooling
        self._current_fan = fan_speed

    def _control_heating(self):
        """Send new target temperature to mytado."""
        if not self._active and None not in (
                self._cur_temp, self._target_temp):
            self._active = True
            _LOGGER.info("Obtained current and target temperature. "
                         "Tado thermostat active")

        if not self._active or self._current_operation == self._overlay_mode:
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
            self._store.set_zone_overlay(self.zone_id, CONST_OVERLAY_MANUAL)
            self._overlay_mode = self._current_operation
            return

        _LOGGER.info("Switching mytado.com to %s mode for zone %s",
                     self._current_operation, self.zone_name)
        self._store.set_zone_overlay(
            self.zone_id, self._current_operation, self._target_temp)

        self._overlay_mode = self._current_operation

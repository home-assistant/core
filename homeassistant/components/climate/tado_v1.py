"""tado component to create a climate device for each zone."""

import logging

from homeassistant.const import TEMP_CELSIUS
from homeassistant.helpers.event import track_state_change

from homeassistant.components.climate import (
    ClimateDevice)
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT, ATTR_TEMPERATURE)

CONST_MODE_SMART_SCHEDULE = "SMART_SCHEDULE"  # Default mytado mode
CONST_MODE_OFF = "OFF"  # Switch off heating in a zone

# When we change the temperature setting, we need an overlay mode
# wait until tado changes the mode automatic
CONST_OVERLAY_TADO_MODE = "TADO_MODE"
# the user has change the temperature or mode manually
CONST_OVERLAY_MANUAL = "MANUAL"
# the temperature will be reset after a timespan
CONST_OVERLAY_TIMER = "TIMER"


# will be used when changing temperature
CONST_DEFAULT_OPERATION_MODE = CONST_OVERLAY_TADO_MODE
# will be used when switching to CONST_MODE_OFF
CONST_DEFAULT_OFF_MODE = CONST_OVERLAY_MANUAL

# DOMAIN = 'tado_v1'

_LOGGER = logging.getLogger(__name__)
SENSOR_TYPES = ['temperature', 'humidity', 'tado mode', 'power', 'overlay']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the climate platform."""
    # get the PyTado object from the hub component
    tado = hass.data['Mytado']

    try:
        zones = tado.getZones()
    except RuntimeError:
        _LOGGER.error("Unable to get zone info from mytado")
        return False

    tado_data = TadoData(tado)

    climate_devices = []
    for zone in zones:
        climate_devices.append(tado_data.create_climate_device(hass,
                                                               zone['name'],
                                                               zone['id']))

    if len(climate_devices) > 0:
        add_devices(climate_devices)
        tado_data.activate_tracking(hass)
        return True
    else:
        return False


class TadoClimate(ClimateDevice):
    """Representation of a tado climate device."""

    def __init__(self, tado, zone_name, zone_id,
                 min_temp, max_temp, target_temp, ac_mode,
                 tolerance=0.3):
        """Initialization of TadoClimate device."""
        self._tado = tado
        self.zone_name = zone_name
        self.zone_id = zone_id

        self.ac_mode = ac_mode

        self._active = False
        self._device_is_active = False

        self._cur_temp = None
        self._cur_humidity = None
        self._is_away = False
        self._min_temp = min_temp
        self._max_temp = max_temp
        self._target_temp = target_temp
        self._tolerance = tolerance
        self._unit = TEMP_CELSIUS

        self._operation_list = [CONST_OVERLAY_MANUAL, CONST_OVERLAY_TIMER,
                                CONST_OVERLAY_TADO_MODE,
                                CONST_MODE_SMART_SCHEDULE, CONST_MODE_OFF]
        self._current_operation = CONST_MODE_SMART_SCHEDULE
        self._overlay_mode = self._current_operation

    @property
    def should_poll(self):
        """
        No Polling needed for tado climate device.

        because it reuses sensors
        """
        return False

    @property
    def name(self):
        """Return the name of the sensor."""
        return self.zone_name

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def state(self):
        """
        Return the current temperature as the state.

        instead of operation_mode.
        """
        return self._cur_temp

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
        """Return current operation ie. heat, cool, idle."""
        return self._current_operation

    @property
    def operation_list(self):
        """List of available operation modes."""
        return self._operation_list

    @property
    def is_away_mode_on(self):
        """Return true if away mode is on."""
        return self._is_away

    @property
    def _is_device_active(self):
        """If the toggleable device is currently active."""
        return self._device_is_active

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temp

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        self._current_operation = CONST_DEFAULT_OPERATION_MODE
        self._overlay_mode = None
        self._target_temp = temperature
        self._control_heating()
        self.update_ha_state()

    def set_operation_mode(self, operation_mode):
        """Set new target temperature."""
        self._current_operation = operation_mode
        self._overlay_mode = None
        self._control_heating()
        self.update_ha_state()

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        # pylint: disable=no-member
        if self._min_temp:
            return self._min_temp
        else:
            # get default temp from super class
            return ClimateDevice.min_temp.fget(self)

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        #  pylint: disable=no-member
        if self._max_temp:
            return self._max_temp
        else:
            #  Get default temp from super class
            return ClimateDevice.max_temp.fget(self)

    def sensor_changed(self, entity_id, old_state, new_state):
        #  pylint: disable=W0613
        """Called when a depending sensor changes."""
        if new_state is None or new_state.state is None:
            return

        self.update_state(entity_id, new_state, True)

    def update_state(self, entity_type, state, update_ha):
        """Update the internal state."""
        if state.state == "unknown":
            return

        _LOGGER.info("%s changed to %s", entity_type, state.state)

        try:
            if entity_type.endswith("temperature"):
                unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)

                self._cur_temp = self.hass.config.units.temperature(
                    float(state.state), unit)

                self._target_temp = self.hass.config.units.temperature(
                    float(state.attributes.get("setting")), unit)

            elif entity_type.endswith("humidity"):
                self._cur_humidity = float(state.state)

            elif entity_type.endswith("tado mode"):
                self._is_away = state.state == "AWAY"

            elif entity_type.endswith("power"):
                if state.state == "OFF":
                    self._current_operation = CONST_MODE_OFF
                    self._device_is_active = False
                else:
                    self._device_is_active = True

            elif entity_type.endswith("overlay"):
                #  if you set mode manualy to off, there will be an overlay
                #  and a termination, but we want to see the mode "OFF"
                overlay = state.state
                termination = state.attributes.get("termination")

                if overlay == "True" and self._device_is_active:
                    #  there is an overlay the device is on
                    self._overlay_mode = termination
                    self._current_operation = termination
                elif overlay == "False":
                    #  there is no overlay, the mode will always be
                    #  "SMART_SCHEDULE"
                    self._overlay_mode = CONST_MODE_SMART_SCHEDULE
                    self._current_operation = CONST_MODE_SMART_SCHEDULE

            if update_ha:
                self.schedule_update_ha_state()

        except ValueError:
            _LOGGER.error("Unable to update from sensor: %s", entity_type)

    def _control_heating(self):
        """Send new target temperature to mytado."""
        if not self._active and None not in (self._cur_temp,
                                             self._target_temp):
            self._active = True
            _LOGGER.info('Obtained current and target temperature. '
                         'tado thermostat active.')

        if not self._active or self._current_operation == self._overlay_mode:
            return

        if self._current_operation == CONST_MODE_SMART_SCHEDULE:
            _LOGGER.info('Switching mytado.com to SCHEDULE (default) '
                         'for zone %s', self.zone_name)
            self._tado.resetZoneOverlay(self.zone_id)
            self._overlay_mode = self._current_operation
            return

        if self._current_operation == CONST_MODE_OFF:
            _LOGGER.info('Switching mytado.com to OFF for zone %s',
                         self.zone_name)
            self._tado.setZoneOverlay(self.zone_id, CONST_DEFAULT_OFF_MODE)
            self._overlay_mode = self._current_operation
            return

        _LOGGER.info("Switching mytado.com to %s mode for zone %s",
                     self._current_operation, self.zone_name)
        self._tado.setZoneOverlay(self.zone_id,
                                  self._current_operation,
                                  self._target_temp)

        self._overlay_mode = self._current_operation


class TadoData(object):
    """Tado data object to control the tado functionality."""

    def __init__(self, tado):
        """Initialization of class TadoData."""
        self._tado = tado
        self._tracking_active = False

        self.sensors = []

    def create_climate_device(self, hass, name, tado_id):
        """Create a climate device."""
        capabilities = self._tado.getCapabilities(tado_id)

        min_temp = float(capabilities["temperatures"]["celsius"]["min"])
        max_temp = float(capabilities["temperatures"]["celsius"]["max"])
        target_temp = 21
        ac_mode = capabilities["type"] != "HEATING"

        device_id = 'climate {} {}'.format(name, tado_id)
        device = TadoClimate(self._tado, name, tado_id,
                             min_temp, max_temp, target_temp, ac_mode)
        sensor = {
            "id": device_id,
            "device": device,
            "sensors": []
        }

        self.sensors.append(sensor)

        for sensor_type in SENSOR_TYPES:
            entity_id = 'sensor.{} {}'.format(name, sensor_type)
            entity_id = entity_id.lower().replace(" ", "_")

            sensor["sensors"].append(entity_id)

            sensor_state = hass.states.get(entity_id)
            if sensor_state:
                device.update_state(sensor_type, sensor_state, False)

        return device

    def activate_tracking(self, hass):
        """Activate tracking of dependend sensors."""
        if self._tracking_active is False:
            for data in self.sensors:
                for entity_id in data["sensors"]:
                    track_state_change(hass, entity_id,
                                       data["device"].sensor_changed)
                    _LOGGER.info("activated state tracking for %s.", entity_id)

        self._tracking_active = True

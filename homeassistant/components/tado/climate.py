"""Support for Tado to create a climate device for each zone."""
import logging

from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_HEAT,
    FAN_HIGH,
    FAN_LOW,
    FAN_MIDDLE,
    FAN_OFF,
    HVAC_MODE_AUTO,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    PRESET_AWAY,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_TENTHS, TEMP_CELSIUS
from homeassistant.util.temperature import convert as convert_temperature

from . import DATA_TADO

_LOGGER = logging.getLogger(__name__)

CONST_MODE_SMART_SCHEDULE = "SMART_SCHEDULE"  # Default mytado mode
CONST_MODE_OFF = "OFF"  # Switch off heating in a zone

# When we change the temperature setting, we need an overlay mode
# wait until tado changes the mode automatic
CONST_OVERLAY_TADO_MODE = "TADO_MODE"
# the user has change the temperature or mode manually
CONST_OVERLAY_MANUAL = "MANUAL"
# the temperature will be reset after a timespan
CONST_OVERLAY_TIMER = "TIMER"

CONST_MODE_FAN_HIGH = "HIGH"
CONST_MODE_FAN_MIDDLE = "MIDDLE"
CONST_MODE_FAN_LOW = "LOW"

FAN_MAP_TADO = {"HIGH": FAN_HIGH, "MIDDLE": FAN_MIDDLE, "LOW": FAN_LOW}

HVAC_MAP_TADO = {
    "MANUAL": HVAC_MODE_HEAT,
    "TIMER": HVAC_MODE_AUTO,
    "TADO_MODE": HVAC_MODE_AUTO,
    "SMART_SCHEDULE": HVAC_MODE_AUTO,
    "OFF": HVAC_MODE_OFF,
}

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE
SUPPORT_HVAC = [HVAC_MODE_HEAT, HVAC_MODE_AUTO, HVAC_MODE_OFF]
SUPPORT_FAN = [FAN_HIGH, FAN_MIDDLE, FAN_HIGH, FAN_OFF]
SUPPORT_PRESET = [PRESET_AWAY]


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
        device = create_climate_device(tado, hass, zone, zone["name"], zone["id"])
        if not device:
            continue
        climate_devices.append(device)

    if climate_devices:
        add_entities(climate_devices, True)


def create_climate_device(tado, hass, zone, name, zone_id):
    """Create a Tado climate device."""
    capabilities = tado.get_capabilities(zone_id)

    unit = TEMP_CELSIUS
    ac_mode = capabilities["type"] == "AIR_CONDITIONING"

    if ac_mode:
        temperatures = capabilities["HEAT"]["temperatures"]
    elif "temperatures" in capabilities:
        temperatures = capabilities["temperatures"]
    else:
        _LOGGER.debug("Received zone %s has no temperature; not adding", name)
        return

    min_temp = float(temperatures["celsius"]["min"])
    max_temp = float(temperatures["celsius"]["max"])
    step = temperatures["celsius"].get("step", PRECISION_TENTHS)

    data_id = "zone {} {}".format(name, zone_id)
    device = TadoClimate(
        tado,
        name,
        zone_id,
        data_id,
        hass.config.units.temperature(min_temp, unit),
        hass.config.units.temperature(max_temp, unit),
        step,
        ac_mode,
    )

    tado.add_sensor(
        data_id, {"id": zone_id, "zone": zone, "name": name, "climate": device}
    )

    return device


class TadoClimate(ClimateDevice):
    """Representation of a tado climate device."""

    def __init__(
        self,
        store,
        zone_name,
        zone_id,
        data_id,
        min_temp,
        max_temp,
        step,
        ac_mode,
        tolerance=0.3,
    ):
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
        self._step = step
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
    def hvac_mode(self):
        """Return hvac operation ie. heat, cool mode.

        Need to be one of HVAC_MODE_*.
        """
        return HVAC_MAP_TADO.get(self._current_operation)

    @property
    def hvac_modes(self):
        """Return the list of available hvac operation modes.

        Need to be a subset of HVAC_MODES.
        """
        return SUPPORT_HVAC

    @property
    def hvac_action(self):
        """Return the current running hvac operation if supported.

        Need to be one of CURRENT_HVAC_*.
        """
        if self._cooling:
            return CURRENT_HVAC_COOL
        return CURRENT_HVAC_HEAT

    @property
    def fan_mode(self):
        """Return the fan setting."""
        if self.ac_mode:
            return FAN_MAP_TADO.get(self._current_fan)
        return None

    @property
    def fan_modes(self):
        """List of available fan modes."""
        if self.ac_mode:
            return SUPPORT_FAN
        return None

    @property
    def preset_mode(self):
        """Return the current preset mode, e.g., home, away, temp."""
        if self._is_away:
            return PRESET_AWAY
        return None

    @property
    def preset_modes(self):
        """Return a list of available preset modes."""
        return SUPPORT_PRESET

    @property
    def temperature_unit(self):
        """Return the unit of measurement used by the platform."""
        return self._unit

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return self._step

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

    def set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        mode = None

        if hvac_mode == HVAC_MODE_OFF:
            mode = CONST_MODE_OFF
        elif hvac_mode == HVAC_MODE_AUTO:
            mode = CONST_MODE_SMART_SCHEDULE
        elif hvac_mode == HVAC_MODE_HEAT:
            mode = CONST_OVERLAY_MANUAL

        self._current_operation = mode
        self._overlay_mode = None
        self._control_heating()

    def set_preset_mode(self, preset_mode):
        """Set new preset mode."""
        pass

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return convert_temperature(
            self._min_temp, self._unit, self.hass.config.units.temperature_unit
        )

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return convert_temperature(
            self._max_temp, self._unit, self.hass.config.units.temperature_unit
        )

    def update(self):
        """Update the state of this climate device."""
        self._store.update()

        data = self._store.get_data(self._data_id)

        if data is None:
            _LOGGER.debug("Received no data for zone %s", self.zone_name)
            return

        if "sensorDataPoints" in data:
            sensor_data = data["sensorDataPoints"]

            unit = TEMP_CELSIUS

            if "insideTemperature" in sensor_data:
                temperature = float(sensor_data["insideTemperature"]["celsius"])
                self._cur_temp = self.hass.config.units.temperature(temperature, unit)

            if "humidity" in sensor_data:
                humidity = float(sensor_data["humidity"]["percentage"])
                self._cur_humidity = humidity

            # temperature setting will not exist when device is off
            if (
                "temperature" in data["setting"]
                and data["setting"]["temperature"] is not None
            ):
                setting = float(data["setting"]["temperature"]["celsius"])
                self._target_temp = self.hass.config.units.temperature(setting, unit)

        if "tadoMode" in data:
            mode = data["tadoMode"]
            self._is_away = mode == "AWAY"

        if "setting" in data:
            power = data["setting"]["power"]
            if power == "OFF":
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

        if "overlay" in data:
            overlay_data = data["overlay"]
            overlay = overlay_data is not None

        if overlay:
            termination = overlay_data["termination"]["type"]

            if "setting" in overlay_data:
                setting_data = overlay_data["setting"]
                setting = setting_data is not None

            if setting:
                if "mode" in setting_data:
                    cooling = setting_data["mode"] == "COOL"

                if "fanSpeed" in setting_data:
                    fan_speed = setting_data["fanSpeed"]

        if self._device_is_active:
            # If you set mode manually to off, there will be an overlay
            # and a termination, but we want to see the mode "OFF"
            self._overlay_mode = termination
            self._current_operation = termination

        self._cooling = cooling
        self._current_fan = fan_speed

    def _control_heating(self):
        """Send new target temperature to mytado."""
        if not self._active and None not in (self._cur_temp, self._target_temp):
            self._active = True
            _LOGGER.info(
                "Obtained current and target temperature. " "Tado thermostat active"
            )

        if self._current_operation == CONST_MODE_SMART_SCHEDULE:
            _LOGGER.info(
                "Switching mytado.com to SCHEDULE (default) " "for zone %s",
                self.zone_name,
            )
            self._store.reset_zone_overlay(self.zone_id)
            self._overlay_mode = self._current_operation
            return

        if self._current_operation == CONST_MODE_OFF:
            _LOGGER.info("Switching mytado.com to OFF for zone %s", self.zone_name)
            self._store.set_zone_off(self.zone_id, CONST_OVERLAY_MANUAL)
            self._overlay_mode = self._current_operation
            return

        _LOGGER.info(
            "Switching mytado.com to %s mode for zone %s",
            self._current_operation,
            self.zone_name,
        )
        self._store.set_zone_overlay(
            self.zone_id, self._current_operation, self._target_temp
        )

        self._overlay_mode = self._current_operation

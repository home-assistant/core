"""
Support for Tado hot water zones.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/water_heater/tado/
"""
import logging

from homeassistant.components.water_heater import (
    SUPPORT_OPERATION_MODE,
    SUPPORT_TARGET_TEMPERATURE,
    WaterHeaterDevice,
)
from homeassistant.const import STATE_OFF, STATE_ON, TEMP_CELSIUS, ATTR_TEMPERATURE
from homeassistant.components.tado import DATA_TADO

_LOGGER = logging.getLogger(__name__)

CONST_MODE_SMART_SCHEDULE = "SMART_SCHEDULE"
CONST_MODE_OFF = "OFF"
CONST_OVERLAY_TADO_MODE = "TADO_MODE"

SUPPORT_FLAGS_HEATER = SUPPORT_OPERATION_MODE


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Tado water heater platform."""
    tado = hass.data[DATA_TADO]

    try:
        zones = tado.get_zones()
    except RuntimeError:
        _LOGGER.error("Unable to get zone info from mytado")
        return

    water_heater_devices = []
    for zone in zones:
        if zone["type"] == "HOT_WATER":
            device = create_water_heater_device(
                tado, hass, zone, zone["name"], zone["id"]
            )
            if not device:
                continue
            water_heater_devices.append(device)

    if water_heater_devices:
        add_entities(water_heater_devices, True)


def create_water_heater_device(tado, hass, zone, name, zone_id):
    """Create a Tado water heater device."""
    data_id = "zone {} {}".format(name, zone_id)
    capabilities = tado.get_capabilities(zone_id)
    supports_temperature_control = capabilities["canSetTemperature"]
    min_temp = max_temp = None

    if supports_temperature_control and "temperatures" in capabilities:
        temperatures = capabilities["temperatures"]

        min_temp = float(temperatures["celsius"]["min"])
        max_temp = float(temperatures["celsius"]["max"])

    device = TadoWaterHeater(
        tado, name, zone_id, data_id, supports_temperature_control, min_temp, max_temp
    )

    tado.add_sensor(
        data_id, {"id": zone_id, "zone": zone, "name": name, "climate": device}
    )

    return device


class TadoWaterHeater(WaterHeaterDevice):
    """Representation of a Tado water heater."""

    def __init__(
        self,
        store,
        zone_name,
        zone_id,
        data_id,
        supports_temperature_control,
        min_temp,
        max_temp,
    ):
        """Initialize of Tado water heater device."""
        self._store = store
        self._data_id = data_id

        self.zone_name = zone_name
        self.zone_id = zone_id

        self._active = False
        self._device_is_active = False

        self._supports_temperature_control = supports_temperature_control
        self._min_temperature = min_temp
        self._max_temperature = max_temp

        self._supported_features = SUPPORT_FLAGS_HEATER

        if self._supports_temperature_control:
            self._supported_features |= SUPPORT_TARGET_TEMPERATURE

        self._target_temperature = None

        self._is_away = False

        self._current_operation = CONST_MODE_SMART_SCHEDULE
        self._overlay_mode = CONST_MODE_SMART_SCHEDULE

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._supported_features

    @property
    def name(self):
        """Return the name of the device."""
        return self.zone_name

    @property
    def current_operation(self):
        """Return current readable operation mode."""
        return STATE_ON if self._device_is_active else STATE_OFF

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def is_away_mode_on(self):
        """Return true if away mode is on."""
        return self._is_away

    @property
    def operation_list(self):
        """Return the list of available operation modes (readable)."""
        return [STATE_OFF, STATE_ON]

    @property
    def temperature_unit(self):
        """Return the unit of measurement used by the platform."""
        return TEMP_CELSIUS

    def set_operation_mode(self, operation_mode):
        """Set new operation mode."""
        self._device_is_active = operation_mode == STATE_ON
        self._overlay_mode = CONST_OVERLAY_TADO_MODE
        self._control_heater()

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if not self._supports_temperature_control or temperature is None:
            return

        self._current_operation = CONST_OVERLAY_TADO_MODE
        self._overlay_mode = None
        self._target_temperature = temperature
        self._control_heater()

    def update(self):
        """Update the state of the water_heater device."""
        self._store.update()

        data = self._store.get_data(self._data_id)

        if data is None:
            _LOGGER.debug("Received no data for zone %s", self.zone_name)
            return

        if "tadoMode" in data:
            mode = data["tadoMode"]
            self._is_away = mode == "AWAY"

        if "setting" in data:
            power = data["setting"]["power"]
            if power == "OFF":
                self._current_operation = CONST_MODE_OFF
                # There is no overlay, the mode will always be
                # "SMART_SCHEDULE"
                self._overlay_mode = CONST_MODE_SMART_SCHEDULE
                self._device_is_active = False
            else:
                self._device_is_active = True

        # temperature setting will not exist when device is off
        if (
            "temperature" in data["setting"]
            and data["setting"]["temperature"] is not None
        ):
            setting = float(data["setting"]["temperature"]["celsius"])
            self._target_temperature = self.hass.config.units.temperature(
                setting, TEMP_CELSIUS
            )

        overlay = False
        overlay_data = None
        termination = CONST_MODE_SMART_SCHEDULE

        if "overlay" in data:
            overlay_data = data["overlay"]
            overlay = overlay_data is not None

        if overlay:
            termination = overlay_data["termination"]["type"]

        if self._device_is_active:
            # If you set mode manually to off, there will be an overlay
            # and a termination, but we want to see the mode "OFF"
            self._overlay_mode = termination
            self._current_operation = termination

    def _control_heater(self):
        """Send new target temperature to mytado."""
        _LOGGER.info(
            "Switching mytado.com to %s mode for zone %s",
            self._device_is_active,
            self.zone_name,
        )
        if self._device_is_active:
            self._store.set_zone_overlay(
                self.zone_id,
                self._overlay_mode,
                self._target_temperature,
                device_type="HOT_WATER",
            )
        else:
            self._store.set_zone_off(
                self.zone_id, self._overlay_mode, device_type="HOT_WATER"
            )

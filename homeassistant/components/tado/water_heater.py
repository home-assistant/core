"""Support for Tado hot water zones."""
import logging

from homeassistant.components.water_heater import (
    SUPPORT_OPERATION_MODE,
    SUPPORT_TARGET_TEMPERATURE,
    WaterHeaterDevice,
)
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import DOMAIN, SIGNAL_TADO_UPDATE_RECEIVED
from .const import (
    CONST_MODE_OFF,
    CONST_MODE_SMART_SCHEDULE,
    CONST_OVERLAY_MANUAL,
    CONST_OVERLAY_TADO_MODE,
    CONST_OVERLAY_TIMER,
    DATA,
    TYPE_HOT_WATER,
)

_LOGGER = logging.getLogger(__name__)

MODE_AUTO = "auto"
MODE_HEAT = "heat"
MODE_OFF = "off"

OPERATION_MODES = [MODE_AUTO, MODE_HEAT, MODE_OFF]

WATER_HEATER_MAP_TADO = {
    CONST_OVERLAY_MANUAL: MODE_HEAT,
    CONST_OVERLAY_TIMER: MODE_HEAT,
    CONST_OVERLAY_TADO_MODE: MODE_HEAT,
    CONST_MODE_SMART_SCHEDULE: MODE_AUTO,
    CONST_MODE_OFF: MODE_OFF,
}

SUPPORT_FLAGS_HEATER = SUPPORT_OPERATION_MODE


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Tado water heater platform."""
    if discovery_info is None:
        return

    api_list = hass.data[DOMAIN][DATA]
    entities = []

    for tado in api_list:
        for zone in tado.zones:
            if zone["type"] in [TYPE_HOT_WATER]:
                entity = create_water_heater_entity(tado, zone["name"], zone["id"])
                entities.append(entity)

    if entities:
        add_entities(entities, True)


def create_water_heater_entity(tado, name: str, zone_id: int):
    """Create a Tado water heater device."""
    capabilities = tado.get_capabilities(zone_id)
    supports_temperature_control = capabilities["canSetTemperature"]

    if supports_temperature_control and "temperatures" in capabilities:
        temperatures = capabilities["temperatures"]
        min_temp = float(temperatures["celsius"]["min"])
        max_temp = float(temperatures["celsius"]["max"])
    else:
        min_temp = None
        max_temp = None

    entity = TadoWaterHeater(
        tado, name, zone_id, supports_temperature_control, min_temp, max_temp
    )

    return entity


class TadoWaterHeater(WaterHeaterDevice):
    """Representation of a Tado water heater."""

    def __init__(
        self,
        tado,
        zone_name,
        zone_id,
        supports_temperature_control,
        min_temp,
        max_temp,
    ):
        """Initialize of Tado water heater entity."""
        self._tado = tado

        self.zone_name = zone_name
        self.zone_id = zone_id
        self._unique_id = f"{zone_id} {tado.device_id}"

        self._device_is_active = False
        self._is_away = False

        self._supports_temperature_control = supports_temperature_control
        self._min_temperature = min_temp
        self._max_temperature = max_temp

        self._target_temp = None

        self._supported_features = SUPPORT_FLAGS_HEATER
        if self._supports_temperature_control:
            self._supported_features |= SUPPORT_TARGET_TEMPERATURE

        if tado.fallback:
            # Fallback to Smart Schedule at next Schedule switch
            self._default_overlay = CONST_OVERLAY_TADO_MODE
        else:
            # Don't fallback to Smart Schedule, but keep in manual mode
            self._default_overlay = CONST_OVERLAY_MANUAL

        self._current_operation = CONST_MODE_SMART_SCHEDULE
        self._overlay_mode = CONST_MODE_SMART_SCHEDULE

    async def async_added_to_hass(self):
        """Register for sensor updates."""

        @callback
        def async_update_callback():
            """Schedule an entity update."""
            self.async_schedule_update_ha_state(True)

        async_dispatcher_connect(
            self.hass,
            SIGNAL_TADO_UPDATE_RECEIVED.format("zone", self.zone_id),
            async_update_callback,
        )

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._supported_features

    @property
    def name(self):
        """Return the name of the entity."""
        return self.zone_name

    @property
    def unique_id(self):
        """Return the unique id."""
        return self._unique_id

    @property
    def should_poll(self) -> bool:
        """Do not poll."""
        return False

    @property
    def current_operation(self):
        """Return current readable operation mode."""
        return WATER_HEATER_MAP_TADO.get(self._current_operation)

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temp

    @property
    def is_away_mode_on(self):
        """Return true if away mode is on."""
        return self._is_away

    @property
    def operation_list(self):
        """Return the list of available operation modes (readable)."""
        return OPERATION_MODES

    @property
    def temperature_unit(self):
        """Return the unit of measurement used by the platform."""
        return TEMP_CELSIUS

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return self._min_temperature

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return self._max_temperature

    def set_operation_mode(self, operation_mode):
        """Set new operation mode."""
        mode = None

        if operation_mode == MODE_OFF:
            mode = CONST_MODE_OFF
        elif operation_mode == MODE_AUTO:
            mode = CONST_MODE_SMART_SCHEDULE
        elif operation_mode == MODE_HEAT:
            mode = self._default_overlay

        self._current_operation = mode
        self._overlay_mode = None

        # Set a target temperature if we don't have any
        if mode == CONST_OVERLAY_TADO_MODE and self._target_temp is None:
            self._target_temp = self.min_temp

        self._control_heater()

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if not self._supports_temperature_control or temperature is None:
            return

        self._current_operation = self._default_overlay
        self._overlay_mode = None
        self._target_temp = temperature
        self._control_heater()

    def update(self):
        """Handle update callbacks."""
        _LOGGER.debug("Updating water_heater platform for zone %d", self.zone_id)
        data = self._tado.data["zone"][self.zone_id]

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
            self._target_temp = setting

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
        """Send new target temperature."""
        if self._current_operation == CONST_MODE_SMART_SCHEDULE:
            _LOGGER.debug(
                "Switching to SMART_SCHEDULE for zone %s (%d)",
                self.zone_name,
                self.zone_id,
            )
            self._tado.reset_zone_overlay(self.zone_id)
            self._overlay_mode = self._current_operation
            return

        if self._current_operation == CONST_MODE_OFF:
            _LOGGER.debug(
                "Switching to OFF for zone %s (%d)", self.zone_name, self.zone_id
            )
            self._tado.set_zone_off(self.zone_id, CONST_OVERLAY_MANUAL, TYPE_HOT_WATER)
            self._overlay_mode = self._current_operation
            return

        _LOGGER.debug(
            "Switching to %s for zone %s (%d) with temperature %s",
            self._current_operation,
            self.zone_name,
            self.zone_id,
            self._target_temp,
        )
        self._tado.set_zone_overlay(
            self.zone_id,
            self._current_operation,
            self._target_temp,
            None,
            TYPE_HOT_WATER,
        )
        self._overlay_mode = self._current_operation

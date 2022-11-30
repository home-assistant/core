"""Class to hold all air purifier accessories."""
import logging

from pyhap.const import CATEGORY_AIR_PURIFIER

from homeassistant.const import STATE_ON
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_state_change_event

from .accessories import TYPES
from .const import (
    CHAR_ACTIVE,
    CHAR_AIR_QUALITY,
    CHAR_CURRENT_AIR_PURIFIER_STATE,
    CHAR_CURRENT_HUMIDITY,
    CHAR_CURRENT_TEMPERATURE,
    CHAR_NAME,
    CHAR_PM25_DENSITY,
    CHAR_TARGET_AIR_PURIFIER_STATE,
    CONF_LINKED_HUMIDITY_SENSOR,
    CONF_LINKED_PM25_SENSOR,
    CONF_LINKED_TEMPERATURE_SENSOR,
    SERV_AIR_PURIFIER,
    SERV_AIR_QUALITY_SENSOR,
    SERV_HUMIDITY_SENSOR,
    SERV_TEMPERATURE_SENSOR,
)
from .type_fans import ATTR_PRESET_MODE, CHAR_ROTATION_SPEED, Fan
from .util import cleanup_name_for_homekit, density_to_air_quality

_LOGGER = logging.getLogger(__name__)

CURRENT_STATE_INACTIVE = 0
CURRENT_STATE_IDLE = 1
CURRENT_STATE_PURIFYING_AIR = 2
TARGET_STATE_MANUAL = 0
TARGET_STATE_AUTO = 1


@TYPES.register("AirPurifier")
class AirPurifier(Fan):
    """Generate an AirPurifier accessory for an air purifier entity.

    Currently supports, in addition to Fan properties:
    temperature; humidity; PM2.5; auto mode.
    """

    def __init__(self, *args):
        """Initialize a new AirPurifier accessory object."""
        super().__init__(*args, category=CATEGORY_AIR_PURIFIER)
        self.auto_preset = next(
            filter(lambda x: "auto" == x.lower(), self.preset_modes), None
        )

    def create_services(self):
        """Create and configure the primary service for this accessory."""
        self.chars.append(CHAR_ACTIVE)
        self.chars.append(CHAR_CURRENT_AIR_PURIFIER_STATE)
        self.chars.append(CHAR_TARGET_AIR_PURIFIER_STATE)
        serv_air_purifier = self.add_preload_service(SERV_AIR_PURIFIER, self.chars)
        self.set_primary_service(serv_air_purifier)

        self.char_active = serv_air_purifier.configure_char(CHAR_ACTIVE, value=0)

        self.preset_mode_chars = {}
        self.char_current_humidity = None
        self.char_pm25_density = None
        self.char_current_temperature = None

        self.char_target_air_purifier_state = serv_air_purifier.configure_char(
            CHAR_TARGET_AIR_PURIFIER_STATE,
            value=0,
        )

        self.char_current_air_purifier_state = serv_air_purifier.configure_char(
            CHAR_CURRENT_AIR_PURIFIER_STATE,
            value=0,
        )

        self.linked_humidity_sensor = self.config.get(CONF_LINKED_HUMIDITY_SENSOR)
        if self.linked_humidity_sensor:
            humidity_serv = self.add_preload_service(SERV_HUMIDITY_SENSOR, CHAR_NAME)
            serv_air_purifier.add_linked_service(humidity_serv)
            humidity_serv.configure_char(
                CHAR_NAME,
                value=cleanup_name_for_homekit(f"{self.display_name} Humidity"),
            )
            self.char_current_humidity = humidity_serv.configure_char(
                CHAR_CURRENT_HUMIDITY, value=0
            )

            humidity_state = self.hass.states.get(self.linked_humidity_sensor)
            if humidity_state:
                self._async_update_current_humidity(humidity_state)

        self.linked_pm25_sensor = self.config.get(CONF_LINKED_PM25_SENSOR)
        if self.linked_pm25_sensor:
            pm25_serv = self.add_preload_service(
                SERV_AIR_QUALITY_SENSOR,
                [CHAR_AIR_QUALITY, CHAR_NAME, CHAR_PM25_DENSITY],
            )
            serv_air_purifier.add_linked_service(pm25_serv)
            pm25_serv.configure_char(
                CHAR_NAME, value=cleanup_name_for_homekit(f"{self.display_name} PM2.5")
            )
            self.char_pm25_density = pm25_serv.configure_char(
                CHAR_PM25_DENSITY, value=0
            )

            self.char_air_quality = pm25_serv.configure_char(CHAR_AIR_QUALITY)

            pm25_state = self.hass.states.get(self.linked_pm25_sensor)
            if pm25_state:
                self._async_update_current_pm25(pm25_state)

        self.linked_temperature_sensor = self.config.get(CONF_LINKED_TEMPERATURE_SENSOR)
        if self.linked_temperature_sensor:
            temperature_serv = self.add_preload_service(
                SERV_TEMPERATURE_SENSOR, [CHAR_NAME, CHAR_CURRENT_TEMPERATURE]
            )
            serv_air_purifier.add_linked_service(temperature_serv)
            temperature_serv.configure_char(
                CHAR_NAME,
                value=cleanup_name_for_homekit(f"{self.display_name} Temperature"),
            )
            self.char_current_temperature = temperature_serv.configure_char(
                CHAR_CURRENT_TEMPERATURE, value=0
            )

            temperature_state = self.hass.states.get(self.linked_temperature_sensor)
            if temperature_state:
                self._async_update_current_temperature(temperature_state)

        return serv_air_purifier

    async def run(self):
        """Handle accessory driver started event.

        Run inside the Home Assistant event loop.
        """
        if self.linked_humidity_sensor:
            self._subscriptions.append(
                async_track_state_change_event(
                    self.hass,
                    [self.linked_humidity_sensor],
                    self.async_update_current_humidity_event,
                )
            )

        if self.linked_pm25_sensor:
            self._subscriptions.append(
                async_track_state_change_event(
                    self.hass,
                    [self.linked_pm25_sensor],
                    self.async_update_current_pm25_event,
                )
            )

        if self.linked_temperature_sensor:
            self._subscriptions.append(
                async_track_state_change_event(
                    self.hass,
                    [self.linked_temperature_sensor],
                    self.async_update_current_temperature_event,
                )
            )

        await super().run()

    @callback
    def async_update_current_humidity_event(self, event):
        """Handle state change event listener callback."""
        self._async_update_current_humidity(event.data.get("new_state"))

    @callback
    def _async_update_current_humidity(self, new_state):
        """Handle linked humidity sensor state change to update HomeKit value."""
        if new_state is None:
            _LOGGER.error(
                "%s: Unable to update from linked humidity sensor %s: the entity state is None",
                self.entity_id,
                self.linked_humidity_sensor,
            )
            return
        try:
            current_humidity = float(new_state.state)
            if self.char_current_humidity.value != current_humidity:
                _LOGGER.debug(
                    "%s: Linked humidity sensor %s changed to %d",
                    self.entity_id,
                    self.linked_humidity_sensor,
                    current_humidity,
                )
                self.char_current_humidity.set_value(current_humidity)
        except ValueError as ex:
            _LOGGER.debug(
                "%s: Unable to update from linked humidity sensor %s: %s",
                self.entity_id,
                self.linked_humidity_sensor,
                ex,
            )

    @callback
    def async_update_current_pm25_event(self, event):
        """Handle state change event listener callback."""
        self._async_update_current_pm25(event.data.get("new_state"))

    @callback
    def _async_update_current_pm25(self, new_state):
        """Handle linked pm25 sensor state change to update HomeKit value."""
        if new_state is None:
            _LOGGER.error(
                "%s: Unable to update from linked pm25 sensor %s: the entity state is None",
                self.entity_id,
                self.linked_pm25_sensor,
            )
            return
        try:
            current_pm25 = float(new_state.state)
            if self.char_pm25_density.value != current_pm25:
                _LOGGER.debug(
                    "%s: Linked pm25 sensor %s changed to %d",
                    self.entity_id,
                    self.linked_pm25_sensor,
                    current_pm25,
                )
                self.char_pm25_density.set_value(current_pm25)
                air_quality = density_to_air_quality(current_pm25)
                self.char_air_quality.set_value(air_quality)
                _LOGGER.debug("%s: Set air_quality to %d", self.entity_id, air_quality)
        except ValueError as ex:
            _LOGGER.debug(
                "%s: Unable to update from linked pm25 sensor %s: %s",
                self.entity_id,
                self.linked_pm25_sensor,
                ex,
            )

    @callback
    def async_update_current_temperature_event(self, event):
        """Handle state change event listener callback."""
        self._async_update_current_temperature(event.data.get("new_state"))

    @callback
    def _async_update_current_temperature(self, new_state):
        """Handle linked temperature sensor state change to update HomeKit value."""
        if new_state is None:
            _LOGGER.error(
                "%s: Unable to update from linked temperature sensor %s: the entity state is None",
                self.entity_id,
                self.linked_temperature_sensor,
            )
            return
        try:
            current_temperature = float(new_state.state)
            if self.char_current_temperature.value != current_temperature:
                _LOGGER.debug(
                    "%s: Linked temperature sensor %s changed to %d",
                    self.entity_id,
                    self.linked_temperature_sensor,
                    current_temperature,
                )
                self.char_current_temperature.set_value(current_temperature)
        except ValueError as ex:
            _LOGGER.debug(
                "%s: Unable to update from linked temperature sensor %s: %s",
                self.entity_id,
                self.linked_temperature_sensor,
                ex,
            )

    @callback
    def async_update_state(self, new_state):
        """Update fan after state change."""
        super().async_update_state(new_state)
        # Handle State
        state = new_state.state

        if self.char_current_air_purifier_state is not None:
            self.char_current_air_purifier_state.set_value(
                CURRENT_STATE_PURIFYING_AIR
                if state == STATE_ON
                else CURRENT_STATE_INACTIVE
            )

        # Automatic mode is represented in HASS by a preset called Auto or auto
        attributes = new_state.attributes
        current_preset_mode = attributes.get(ATTR_PRESET_MODE)
        if current_preset_mode is not None:
            self.char_target_air_purifier_state.set_value(
                TARGET_STATE_AUTO
                if "auto" == current_preset_mode.lower()
                else TARGET_STATE_MANUAL
            )

    def set_chars(self, char_values):
        """Handle automatic mode after state change."""
        super().set_chars(char_values)
        if (
            CHAR_TARGET_AIR_PURIFIER_STATE in char_values
            and self.auto_preset is not None
        ):
            if char_values[CHAR_TARGET_AIR_PURIFIER_STATE] == TARGET_STATE_AUTO:
                super().set_preset_mode(True, self.auto_preset)
            else:
                super().set_chars({CHAR_ROTATION_SPEED: self.char_speed.get_value()})

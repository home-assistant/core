"""Class to hold all air purifier accessories."""
import logging

from pyhap.const import CATEGORY_AIR_PURIFIER

from homeassistant.components.fan import (
    ATTR_DIRECTION,
    ATTR_OSCILLATING,
    ATTR_PERCENTAGE,
    ATTR_PERCENTAGE_STEP,
    ATTR_PRESET_MODE,
    ATTR_PRESET_MODES,
    DIRECTION_FORWARD,
    DIRECTION_REVERSE,
    DOMAIN,
    SERVICE_OSCILLATE,
    SERVICE_SET_DIRECTION,
    SERVICE_SET_PERCENTAGE,
    SERVICE_SET_PRESET_MODE,
    FanEntityFeature,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_state_change_event

from .accessories import TYPES, HomeAccessory
from .const import (
    CHAR_ACTIVE,
    CHAR_AIR_QUALITY,
    CHAR_CURRENT_AIR_PURIFIER_STATE,
    CHAR_CURRENT_HUMIDITY,
    CHAR_CURRENT_TEMPERATURE,
    CHAR_NAME,
    CHAR_PM25_DENSITY,
    CHAR_ROTATION_DIRECTION,
    CHAR_ROTATION_SPEED,
    CHAR_SWING_MODE,
    CHAR_TARGET_AIR_PURIFIER_STATE,
    CONF_LINKED_HUMIDITY_SENSOR,
    CONF_LINKED_PM25_SENSOR,
    CONF_LINKED_TEMPERATURE_SENSOR,
    PROP_MIN_STEP,
    SERV_AIR_PURIFIER,
    SERV_AIR_QUALITY_SENSOR,
    SERV_HUMIDITY_SENSOR,
    SERV_TEMPERATURE_SENSOR,
)
from .util import cleanup_name_for_homekit, density_to_air_quality

_LOGGER = logging.getLogger(__name__)

CURRENT_STATE_INACTIVE = 0
CURRENT_STATE_IDLE = 1
CURRENT_STATE_PURIFYING_AIR = 2


@TYPES.register("AirPurifier")
class AirPurifier(HomeAccessory):
    """Generate an AirPurifier accessory for an air purifier entity.

    Currently supports: state, speed, oscillate, direction.
    """

    def __init__(self, *args):
        """Initialize a new AirPurifier accessory object."""
        super().__init__(*args, category=CATEGORY_AIR_PURIFIER)
        self.chars = [
            CHAR_ACTIVE,
            CHAR_CURRENT_AIR_PURIFIER_STATE,
            CHAR_TARGET_AIR_PURIFIER_STATE,
        ]
        state = self.hass.states.get(self.entity_id)

        features = state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
        percentage_step = state.attributes.get(ATTR_PERCENTAGE_STEP, 1)
        self.preset_modes = state.attributes.get(ATTR_PRESET_MODES)

        if features & FanEntityFeature.DIRECTION:
            self.chars.append(CHAR_ROTATION_DIRECTION)
        if features & FanEntityFeature.OSCILLATE:
            self.chars.append(CHAR_SWING_MODE)
        if features & FanEntityFeature.SET_SPEED:
            self.chars.append(CHAR_ROTATION_SPEED)

        serv_air_purifier = self.add_preload_service(SERV_AIR_PURIFIER, self.chars)
        self.set_primary_service(serv_air_purifier)

        self.char_active = serv_air_purifier.configure_char(CHAR_ACTIVE, value=0)

        self.char_direction = None
        self.char_speed = None
        self.char_swing = None
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

        if CHAR_ROTATION_DIRECTION in self.chars:
            self.char_direction = serv_air_purifier.configure_char(
                CHAR_ROTATION_DIRECTION, value=0
            )

        if CHAR_ROTATION_SPEED in self.chars:
            # Initial value is set to 100 because 0 is a special value (off). 100 is
            # an arbitrary non-zero value. It is updated immediately by async_update_state
            # to set to the correct initial value.
            self.char_speed = serv_air_purifier.configure_char(
                CHAR_ROTATION_SPEED,
                value=100,
                properties={PROP_MIN_STEP: percentage_step},
            )

        if CHAR_SWING_MODE in self.chars:
            self.char_swing = serv_air_purifier.configure_char(CHAR_SWING_MODE, value=0)
        self.async_update_state(state)
        serv_air_purifier.setter_callback = self._set_chars

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

    def _set_chars(self, char_values):
        if CHAR_ACTIVE in char_values:
            if char_values[CHAR_ACTIVE]:
                # If the device supports set speed we
                # do not want to turn on as it will take
                # the fan to 100% than to the desired speed.
                #
                # Setting the speed will take care of turning
                # on the fan if FanEntityFeature.SET_SPEED is set.
                if not self.char_speed or CHAR_ROTATION_SPEED not in char_values:
                    self.set_state(1)
            else:
                # Its off, nothing more to do as setting the
                # other chars will likely turn it back on which
                # is what we want to avoid
                self.set_state(0)
                return

        if CHAR_SWING_MODE in char_values:
            self.set_oscillating(char_values[CHAR_SWING_MODE])
        if CHAR_ROTATION_DIRECTION in char_values:
            self.set_direction(char_values[CHAR_ROTATION_DIRECTION])

        # We always do this LAST to ensure they
        # get the speed they asked for
        if CHAR_ROTATION_SPEED in char_values:
            self.set_percentage(char_values[CHAR_ROTATION_SPEED])

    def set_single_preset_mode(self, value):
        """Set auto call came from HomeKit."""
        params = {ATTR_ENTITY_ID: self.entity_id}
        if value:
            _LOGGER.debug(
                "%s: Set auto to 1 (%s)", self.entity_id, self.preset_modes[0]
            )
            params[ATTR_PRESET_MODE] = self.preset_modes[0]
            self.async_call_service(DOMAIN, SERVICE_SET_PRESET_MODE, params)
        else:
            current_state = self.hass.states.get(self.entity_id)
            percentage = current_state.attributes.get(ATTR_PERCENTAGE) or 50
            params[ATTR_PERCENTAGE] = percentage
            _LOGGER.debug("%s: Set auto to 0", self.entity_id)
            self.async_call_service(DOMAIN, SERVICE_TURN_ON, params)

    def set_preset_mode(self, value, preset_mode):
        """Set preset_mode if call came from HomeKit."""
        _LOGGER.debug(
            "%s: Set preset_mode %s to %d", self.entity_id, preset_mode, value
        )
        params = {ATTR_ENTITY_ID: self.entity_id}
        if value:
            params[ATTR_PRESET_MODE] = preset_mode
            self.async_call_service(DOMAIN, SERVICE_SET_PRESET_MODE, params)
        else:
            self.async_call_service(DOMAIN, SERVICE_TURN_ON, params)

    def set_state(self, value):
        """Set state if call came from HomeKit."""
        _LOGGER.debug("%s: Set state to %d", self.entity_id, value)
        service = SERVICE_TURN_ON if value == 1 else SERVICE_TURN_OFF
        params = {ATTR_ENTITY_ID: self.entity_id}
        self.async_call_service(DOMAIN, service, params)

    def set_direction(self, value):
        """Set state if call came from HomeKit."""
        _LOGGER.debug("%s: Set direction to %d", self.entity_id, value)
        direction = DIRECTION_REVERSE if value == 1 else DIRECTION_FORWARD
        params = {ATTR_ENTITY_ID: self.entity_id, ATTR_DIRECTION: direction}
        self.async_call_service(DOMAIN, SERVICE_SET_DIRECTION, params, direction)

    def set_oscillating(self, value):
        """Set state if call came from HomeKit."""
        _LOGGER.debug("%s: Set oscillating to %d", self.entity_id, value)
        oscillating = value == 1
        params = {ATTR_ENTITY_ID: self.entity_id, ATTR_OSCILLATING: oscillating}
        self.async_call_service(DOMAIN, SERVICE_OSCILLATE, params, oscillating)

    def set_percentage(self, value):
        """Set state if call came from HomeKit."""
        _LOGGER.debug("%s: Set speed to %d", self.entity_id, value)
        params = {ATTR_ENTITY_ID: self.entity_id, ATTR_PERCENTAGE: value}
        self.async_call_service(DOMAIN, SERVICE_SET_PERCENTAGE, params, value)

    @callback
    def async_update_state(self, new_state):
        """Update fan after state change."""
        # Handle State
        state = new_state.state
        attributes = new_state.attributes
        if state in (STATE_ON, STATE_OFF):
            self._state = 1 if state == STATE_ON else 0
            self.char_active.set_value(self._state)

        if self.char_current_air_purifier_state is not None:
            self.char_current_air_purifier_state.set_value(
                CURRENT_STATE_PURIFYING_AIR
                if state == STATE_ON
                else CURRENT_STATE_INACTIVE
            )

        if self.char_target_air_purifier_state is not None:
            # Handle single preset mode
            self.char_target_air_purifier_state.set_value(self._state)
            return

        # Handle Direction
        if self.char_direction is not None:
            direction = new_state.attributes.get(ATTR_DIRECTION)
            if direction in (DIRECTION_FORWARD, DIRECTION_REVERSE):
                hk_direction = 1 if direction == DIRECTION_REVERSE else 0
                self.char_direction.set_value(hk_direction)

        # Handle Speed
        if self.char_speed is not None and state != STATE_OFF:
            # We do not change the homekit speed when turning off
            # as it will clear the restore state
            percentage = attributes.get(ATTR_PERCENTAGE)
            # If the homeassistant component reports its speed as the first entry
            # in its speed list but is not off, the hk_speed_value is 0. But 0
            # is a special value in homekit. When you turn on a homekit accessory
            # it will try to restore the last rotation speed state which will be
            # the last value saved by char_speed.set_value. But if it is set to
            # 0, HomeKit will update the rotation speed to 100 as it thinks 0 is
            # off.
            #
            # Therefore, if the hk_speed_value is 0 and the device is still on,
            # the rotation speed is mapped to 1 otherwise the update is ignored
            # in order to avoid this incorrect behavior.
            if percentage == 0 and state == STATE_ON:
                percentage = max(1, self.char_speed.properties[PROP_MIN_STEP])
            if percentage is not None:
                self.char_speed.set_value(percentage)

        # Handle Oscillating
        if self.char_swing is not None:
            oscillating = attributes.get(ATTR_OSCILLATING)
            if isinstance(oscillating, bool):
                hk_oscillating = 1 if oscillating else 0
                self.char_swing.set_value(hk_oscillating)

        current_preset_mode = attributes.get(ATTR_PRESET_MODE)

        # Handle multiple preset modes
        for preset_mode, char in self.preset_mode_chars.items():
            hk_value = 1 if preset_mode == current_preset_mode else 0
            char.set_value(hk_value)

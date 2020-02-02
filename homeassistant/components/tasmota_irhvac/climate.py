"""Adds support for generic thermostat units."""
import asyncio
import logging
import json
import voluptuous as vol
from homeassistant.components.climate import PLATFORM_SCHEMA, ClimateDevice
from homeassistant.components import mqtt
from homeassistant.core import DOMAIN as HA_DOMAIN, callback
from homeassistant.helpers import condition
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import (
    async_track_state_change,
    async_track_time_interval,
)
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    ATTR_AREA_ID,
    ATTR_AWAY_MODE,
    ATTR_ENTITY_ID,
    ATTR_HVAC_MODES,
    ATTR_CURRENT_TEMPERATURE,
    ATTR_MIN_TEMP,
    ATTR_MAX_TEMP,
    ATTR_TARGET_TEMP_STEP,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ATTR_CURRENT_HUMIDITY,
    ATTR_HUMIDITY,
    ATTR_MIN_HUMIDITY,
    ATTR_MAX_HUMIDITY,
    ATTR_FAN_MODE,
    ATTR_FAN_MODES,
    ATTR_HVAC_ACTIONS,
    ATTR_OPERATION_MODE,
    ATTR_OPERATION_LIST,
    ATTR_PRESET_MODE,
    ATTR_PRESET_MODES,
    ATTR_SWING_MODE,
    ATTR_SWING_MODES,
    ATTR_TEMPERATURE,
    ATTR_AUX_HEAT,
    CURRENT_HVAC_OFF,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_DRY,
    CURRENT_HVAC_IDLE,
    CURRENT_HVAC_FAN,
    CURRENT_HVAC_AUTO,
    FAN_ON,
    FAN_OFF,
    FAN_AUTO,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_HIGH,
    FAN_MIDDLE,
    FAN_FOCUS,
    FAN_DIFFUSE,
    HVAC_FAN_MIN,
    HVAC_FAN_MEDIUM,
    HVAC_FAN_MAX,
    HVAC_FAN_AUTO,
    HVAC_FAN_MAX_HIGH,
    HVAC_FAN_AUTO_MAX,
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    HVAC_MODE_DRY,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_AUTO_FAN,
    HVAC_MODE_FAN_AUTO,
    HVAC_MODES,
    SUPPORT_AWAY_MODE,
    SUPPORT_AUX_HEAT,
    SUPPORT_FAN_MODE,
    SUPPORT_PRESET_MODE,
    SUPPORT_SWING_MODE,
    SUPPORT_OPERATION_MODE,
    SUPPORT_TARGET_HUMIDITY,
    SUPPORT_TARGET_TEMPERATURE, 
    SUPPORT_TARGET_TEMPERATURE_RANGE,
    PRESET_AWAY,
    PRESET_NONE,
    CONF_NAME,
    PRECISION_HALVES,
    PRECISION_TENTHS,
    PRECISION_WHOLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_SET_PRESET_MODE,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
    STATE_HEAT,
    STATE_COOL,
    STATE_IDLE,
    STATE_AUTO,
    STATE_MANUAL,
    STATE_DRY,
    STATE_FAN_ONLY,
    STATE_ECO,
    SWING_OFF,
    SWING_BOTH,
    SWING_VERTICAL,
    SWING_HORIZONTAL,
    EVENT_HOMEASSISTANT_START,
    CONF_SCAN_INTERVAL,
    CONF_ENTITY_NAMESPACE,
    CONF_PLATFORM,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT
    )

_LOGGER = logging.getLogger(__name__)
SUPPORT_FLAGS = (SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE | SUPPORT_SWING_MODE | SUPPORT_PRESET_MODE)

DEFAULT_NAME = 'IR AirConditioner'
DEFAULT_STATE_TOPIC = 'state'
DEFAULT_COMMAND_TOPIC = 'topic'
DEFAULT_PROTOCOL = 'ELECTRA_AC'
DEFAULT_TARGET_TEMP = 26
DEFAULT_MIN_TEMP = 16
DEFAULT_MAX_TEMP = 32
DEFAULT_PRECISION = 1
DEFAULT_AWAY_TEMP = 24
DEFAULT_MODES_LIST = [HVAC_MODE_COOL, HVAC_MODE_HEAT, HVAC_MODE_DRY, HVAC_MODE_AUTO_FAN, HVAC_MODE_FAN_AUTO]
DEFAULT_FAN_LIST = [HVAC_FAN_AUTO_MAX, HVAC_FAN_MAX_HIGH, HVAC_FAN_MEDIUM, HVAC_FAN_MIN]
DEFAULT_SWING_LIST = [SWING_OFF, SWING_VERTICAL]
DEFAULT_INITIAL_OPERATION_MODE = STATE_OFF
DEFAULT_CONF_QUIET = "off"
DEFAULT_CONF_TURBO = "off"
DEFAULT_CONF_ECONO = "off"
DEFAULT_CONF_MODEL = "-1"
DEFAULT_CONF_CELSIUS = "on"
DEFAULT_CONF_LIGHT = "off"
DEFAULT_CONF_FILTER = "off"
DEFAULT_CONF_CLEAN = "off"
DEFAULT_CONF_BEEP = "off"
DEFAULT_CONF_SLEEP = "-1"

CONF_PROTOCOL = 'protocol'
CONF_COMMAND_TOPIC = 'command_topic'
CONF_STATE_TOPIC = 'state_topic'
CONF_TEMP_SENSOR = 'temperature_sensor'
CONF_MIN_TEMP = 'min_temp'
CONF_MAX_TEMP = 'max_temp'
CONF_TARGET_TEMP = 'target_temp'
CONF_INITIAL_OPERATION_MODE = 'initial_operation_mode'
CONF_AWAY_TEMP = 'away_temp'
CONF_PRECISION = 'precision'
CONF_MODES_LIST = 'supported_modes'
CONF_FAN_LIST = 'supported_fan_speeds'
CONF_SWING_LIST = 'supported_swing_list'
CONF_QUIET = "default_quiet_mode"
CONF_TURBO = "default_turbo_mode"
CONF_ECONO = "default_econo_mode"
CONF_MODEL = "hvac_model"
CONF_CELSIUS = "celsius_mode"
CONF_LIGHT = "default_light_mode"
CONF_FILTER = "default_filter_mode"
CONF_CLEAN = "default_clean_mode"
CONF_BEEP = "default_beep_mode"
CONF_SLEEP = "default_sleep_mode"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_PROTOCOL, default=DEFAULT_PROTOCOL): cv.string,
        vol.Required(CONF_COMMAND_TOPIC, default=DEFAULT_COMMAND_TOPIC): mqtt.valid_publish_topic,
        vol.Required(CONF_TEMP_SENSOR): cv.entity_id,
        vol.Optional(CONF_STATE_TOPIC, default=DEFAULT_STATE_TOPIC): mqtt.valid_subscribe_topic,
        vol.Optional(CONF_MAX_TEMP, default=DEFAULT_MAX_TEMP): vol.Coerce(float),
        vol.Optional(CONF_MIN_TEMP, default=DEFAULT_MIN_TEMP): vol.Coerce(float),
        vol.Optional(CONF_TARGET_TEMP, default=DEFAULT_TARGET_TEMP): vol.Coerce(float),
        vol.Optional(CONF_INITIAL_OPERATION_MODE, default=DEFAULT_INITIAL_OPERATION_MODE):
            vol.In([STATE_HEAT, STATE_COOL, STATE_AUTO, STATE_DRY, STATE_FAN_ONLY, STATE_OFF]),
        vol.Optional(CONF_AWAY_TEMP, default=DEFAULT_AWAY_TEMP): vol.Coerce(float),
        vol.Optional(CONF_PRECISION, default=DEFAULT_PRECISION): vol.In([PRECISION_TENTHS, PRECISION_HALVES, PRECISION_WHOLE]),
        vol.Optional(CONF_MODES_LIST, default=DEFAULT_MODES_LIST): vol.All(cv.ensure_list, [vol.In(HVAC_MODES)]),
        vol.Optional(CONF_FAN_LIST, default=DEFAULT_FAN_LIST): vol.All(cv.ensure_list, [vol.In([FAN_ON, FAN_OFF, FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH, FAN_MIDDLE, FAN_FOCUS, FAN_DIFFUSE, HVAC_FAN_MIN,HVAC_FAN_MEDIUM, HVAC_FAN_MAX, HVAC_FAN_AUTO, HVAC_FAN_MAX_HIGH, HVAC_FAN_AUTO_MAX])]),
        vol.Optional(CONF_SWING_LIST, default=DEFAULT_SWING_LIST): vol.All(cv.ensure_list, [vol.In([SWING_OFF, SWING_BOTH, SWING_VERTICAL, SWING_HORIZONTAL])]),
        vol.Optional(CONF_QUIET, default=DEFAULT_CONF_QUIET): cv.string,
        vol.Optional(CONF_TURBO, default=DEFAULT_CONF_TURBO): cv.string,
        vol.Optional(CONF_ECONO, default=DEFAULT_CONF_ECONO): cv.string,
        vol.Optional(CONF_MODEL, default=DEFAULT_CONF_MODEL): cv.string,
        vol.Optional(CONF_CELSIUS, default=DEFAULT_CONF_CELSIUS): cv.string,
        vol.Optional(CONF_LIGHT, default=DEFAULT_CONF_LIGHT): cv.string,
        vol.Optional(CONF_FILTER, default=DEFAULT_CONF_FILTER): cv.string,
        vol.Optional(CONF_CLEAN, default=DEFAULT_CONF_CLEAN): cv.string,
        vol.Optional(CONF_BEEP, default=DEFAULT_CONF_BEEP): cv.string,
        vol.Optional(CONF_SLEEP, default=DEFAULT_CONF_SLEEP): cv.string,
    }
)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the generic thermostat platform."""
    name = config.get(CONF_NAME)
    topic = config.get(CONF_COMMAND_TOPIC)
    protocol = config.get(CONF_PROTOCOL)
    sensor_entity_id = config.get(CONF_TEMP_SENSOR)
    state_topic = config.get(CONF_STATE_TOPIC)
    min_temp = config.get(CONF_MIN_TEMP)
    max_temp = config.get(CONF_MAX_TEMP)
    target_temp = config.get(CONF_TARGET_TEMP)
    initial_operation_mode = config.get(CONF_INITIAL_OPERATION_MODE)
    away_temp = config.get(CONF_AWAY_TEMP)
    precision = config.get(CONF_PRECISION)
    modes_list = config.get(CONF_MODES_LIST)
    fan_list = config.get(CONF_FAN_LIST)
    swing_list = config.get(CONF_SWING_LIST)
    quiet = config.get(CONF_QUIET)
    turbo = config.get(CONF_TURBO)
    econo = config.get(CONF_ECONO)
    model = config.get(CONF_MODEL)
    celsius = config.get(CONF_CELSIUS)
    light = config.get(CONF_LIGHT)
    filterr = config.get(CONF_FILTER)
    clean = config.get(CONF_CLEAN)
    beep = config.get(CONF_BEEP)
    sleep = config.get(CONF_SLEEP)

    async_add_entities(
        [
            TasmotaIrhvac(
                hass,
                topic,
                protocol,
                name,
                sensor_entity_id,
                state_topic,
                min_temp,
                max_temp,
                target_temp,
                initial_operation_mode,
                away_temp,
                precision,
                modes_list,
                fan_list,
                swing_list,
                quiet,
                turbo,
                econo,
                model,
                celsius,
                light,
                filterr,
                clean,
                beep,
                sleep
            )
        ]
    )


class TasmotaIrhvac(ClimateDevice, RestoreEntity):
    """Representation of a Generic Thermostat device."""

    def __init__(
        self,
        hass,
        topic,
        protocol,
        name,
        sensor_entity_id,
        state_topic,
        min_temp,
        max_temp,
        target_temp,
        initial_operation_mode,
        away_temp,
        precision,
        modes_list,
        fan_list,
        swing_list,
        quiet,
        turbo,
        econo,
        model,
        celsius,
        light,
        filterr,
        clean,
        beep,
        sleep,
    ):
        """Initialize the thermostat."""
        self.topic = topic
        self.hass = hass
        self._protocol = protocol
        self._name = name
        self.sensor_entity_id = sensor_entity_id
        self.state_topic = state_topic
        self._hvac_mode = initial_operation_mode
        self._saved_target_temp = target_temp or away_temp
        self._temp_precision = precision
        self._hvac_list = modes_list
        self._fan_list = fan_list
        self._fan_mode = fan_list[0]
        self._swing_list = swing_list
        self._swing_mode = swing_list[0]
        self._enabled = False
        self.power_mode = STATE_OFF
        if initial_operation_mode is not STATE_OFF:
            self.power_mode = STATE_ON
            self._enabled = True
        self._active = False
        self._cur_temp = None
        self._min_temp = min_temp
        self._max_temp = max_temp
        self._target_temp = target_temp
        self._unit = hass.config.units.temperature_unit
        self._support_flags = SUPPORT_FLAGS
        if away_temp is not None:
            self._support_flags = SUPPORT_FLAGS | SUPPORT_PRESET_MODE
        self._away_temp = away_temp
        self._is_away = False
        self._modes_list = modes_list
        self._fan_list = fan_list
        self._swing_list = swing_list
        self._quiet = quiet
        self._turbo = turbo
        self._econo = econo
        self._model = model
        self._celsius = celsius
        self._light = light
        self._filterr = filterr
        self._clean = clean
        self._beep = beep
        self._sleep = sleep
        self._sub_state = None

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()
        # Add listener
        async_track_state_change(
            self.hass, self.sensor_entity_id, self._async_sensor_changed
        )
        await self._subscribe_topics()

        @callback
        def _async_startup(event):
            """Init on startup."""
            sensor_state = self.hass.states.get(self.sensor_entity_id)
            if sensor_state and sensor_state.state != STATE_UNKNOWN:
                self._async_update_temp(sensor_state)

        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, _async_startup)

        # Check If we have an old state
        old_state = await self.async_get_last_state()
        if old_state is not None:
            # If we have no initial temperature, restore
            if old_state.attributes.get(ATTR_TEMPERATURE) is not None:
                self._target_temp = float(old_state.attributes[ATTR_TEMPERATURE])
            if old_state.attributes.get(ATTR_PRESET_MODE) == PRESET_AWAY:
                self._is_away = True
            if not self._hvac_mode and old_state.state:
                self._hvac_mode = old_state.state
                self._enabled = self._hvac_mode != STATE_OFF
        else:
            # No previous state, try and restore defaults
            if self._target_temp is None:
                self._target_temp = 26.0
            _LOGGER.warning(
                "No previously saved temperature, setting to %s", self._target_temp
            )
        # Set default state to off
        if not self._hvac_mode:
            self._hvac_mode = HVAC_MODE_OFF

    async def _subscribe_topics(self):
        """(Re)Subscribe to topics."""

        @callback
        def state_message_received(msg):
            """Handle new MQTT state messages."""
            json_payload = json.loads(msg.payload)
            _LOGGER.debug(json_payload)
            if 'IrReceived' not in json_payload:
                return
            if 'IRHVAC' not in json_payload['IrReceived']:
                return

            payload = json_payload['IrReceived']['IRHVAC']
            _LOGGER.debug(payload)
            if payload['Vendor'] == self._protocol and str(payload['Model']) == self._model:
                _LOGGER.debug("we have a match")
                self.power_mode = payload['Power'].lower()
                self._hvac_mode = payload['Mode'].lower()
                self._target_temp = payload['Temp']
                self._celsius = payload['Celsius'].lower()

                if payload['SwingV'].lower() == STATE_AUTO and payload['SwingH'].lower() == STATE_AUTO:
                    if SWING_BOTH in self._swing_list:
                        self._swing_mode = SWING_BOTH
                    elif SWING_VERTICAL in self._swing_list:
                        self._swing_mode = SWING_VERTICAL
                    elif SWING_HORIZONTAL in self._swing_list:
                        self._swing_mode = SWING_HORIZONTAL
                    else:
                        self._swing_mode = SWING_OFF
                elif payload['SwingV'].lower() == STATE_AUTO and SWING_VERTICAL in self._swing_list:
                    self._swing_mode = SWING_VERTICAL
                elif payload['SwingH'].lower() == STATE_AUTO and SWING_HORIZONTAL in self._swing_list:
                    self._swing_mode = SWING_HORIZONTAL
                else:
                    self._swing_mode = SWING_OFF

                fan_mode= payload['FanSpeed'].lower()
                #ELECTRA_AC fan modes fix
                if HVAC_FAN_MAX_HIGH in self._fan_list and HVAC_FAN_AUTO_MAX in self._fan_list:
                    if fan_mode == HVAC_FAN_MAX:
                        self._fan_mode = FAN_HIGH
                    elif fan_mode == HVAC_FAN_AUTO:
                        self._fan_mode = HVAC_FAN_MAX
                    else:
                        self._fan_mode = fan_mode
                else:
                    self._fan_mode = fan_mode
                _LOGGER.debug(self._fan_mode)
                # Set default state to off
                if self.power_mode == STATE_OFF:
                    self._enabled = False
                else:
                    self._enabled = True

                # Update HA UI and State
                self.schedule_update_ha_state()

        self._sub_state = await mqtt.subscription.async_subscribe_topics(
            self.hass, self._sub_state,
            {CONF_STATE_TOPIC: {'topic': self.state_topic,
            'msg_callback': state_message_received, 'qos': 1}})

    async def async_will_remove_from_hass(self):
        """Unsubscribe when removed."""
        self._sub_state = await mqtt.subscription.async_unsubscribe_topics(self.hass, self._sub_state)

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def name(self):
        """Return the name of the thermostat."""
        return self._name

    @property
    def precision(self):
        """Return the precision of the system."""
        if self._temp_precision is not None:
            return self._temp_precision
        return super().precision

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def current_temperature(self):
        """Return the sensor temperature."""
        return self._cur_temp

    @property
    def hvac_mode(self):
        """Return current operation."""
        return self._hvac_mode

    @property
    def hvac_action(self):
        """Return the current running hvac operation if supported.
        Need to be one of CURRENT_HVAC_*.
        """
        return self._hvac_mode

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temp

    @property
    def hvac_modes(self):
        """List of available operation modes."""
        return self._hvac_list

    @property
    def preset_mode(self):
        """Return the current preset mode, e.g., home, away, temp."""
        return PRESET_AWAY if self._is_away else PRESET_NONE

    @property
    def preset_modes(self):
        """Return a list of available preset modes or PRESET_NONE if _away_temp is undefined."""
        return [PRESET_NONE, PRESET_AWAY] if self._away_temp else PRESET_NONE

    @property
    def fan_mode(self):
        """Return the list of available fan modes.
        Requires SUPPORT_FAN_MODE.
        """
        return self._fan_mode

    @property
    def fan_modes(self):
        """Return the list of available fan modes.
        Requires SUPPORT_FAN_MODE.
        """
        #tweek for some ELECTRA_AC devices
        if HVAC_FAN_MAX_HIGH in self._fan_list and HVAC_FAN_AUTO_MAX in self._fan_list:
            new_fan_list = []
            for val in self._fan_list:
                if val == HVAC_FAN_MAX_HIGH:
                    new_fan_list.append(FAN_HIGH)
                elif val == HVAC_FAN_AUTO_MAX:
                    new_fan_list.append(HVAC_FAN_MAX)
                else:
                    new_fan_list.append(val)
            return new_fan_list
        return self._fan_list

    @property
    def swing_mode(self):
        """Return the swing setting.
        Requires SUPPORT_SWING_MODE.
        """
        return self._swing_mode

    @property
    def swing_modes(self):
        """Return the list of available swing modes.
        Requires SUPPORT_SWING_MODE.
        """
        return self._swing_list

    async def async_set_hvac_mode(self, hvac_mode):
        """Set hvac mode."""
        if hvac_mode not in self._hvac_list or hvac_mode == HVAC_MODE_OFF:
            self._hvac_mode = HVAC_MODE_OFF
            self._enabled = False
            self.power_mode = STATE_OFF
        else:
            self._hvac_mode = hvac_mode
            self._enabled = True
            self.power_mode = STATE_ON
        # Ensure we update the current operation after changing the mode
        self.schedule_update_ha_state()
        await self.hass.async_add_executor_job(self.send_ir)

    async def async_turn_on(self):
        """Turn thermostat on."""
        self.power_mode = STATE_ON
        await self.async_update_ha_state()
        await self.hass.async_add_executor_job(self.send_ir)

    async def async_turn_off(self):
        """Turn thermostat off."""
        self._hvac_mode = STATE_OFF
        self.power_mode = STATE_OFF
        await self.async_update_ha_state()
        await self.hass.async_add_executor_job(self.send_ir)

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        self._target_temp = temperature
        self.power_mode = STATE_ON
        await self.hass.async_add_executor_job(self.send_ir)
        await self.async_update_ha_state()

    async def async_set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        if fan_mode not in self._fan_list:
            _LOGGER.error("Invalid swing mode selected. Got '" + fan_mode + "'. Allowed modes are:")
            _LOGGER.error(self._fan_list)
            return
        self._fan_mode = fan_mode
        self.power_mode = STATE_ON
        await self.hass.async_add_executor_job(self.send_ir)
        await self.async_update_ha_state()

    async def async_set_swing_mode(self, swing_mode):
        """Set new target swing operation."""
        if swing_mode not in self._swing_list:
            _LOGGER.error("Invalid swing mode selected. Got '" + swing_mode + "'. Allowed modes are:")
            _LOGGER.error(self.swing_list)
            return
        self._swing_mode = swing_mode
        self.power_mode = STATE_ON
        await self.hass.async_add_executor_job(self.send_ir)
        await self.async_update_ha_state()

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

        # Get default temp from super class
        return super().max_temp

    async def _async_sensor_changed(self, entity_id, old_state, new_state):
        """Handle temperature changes."""
        if new_state is None:
            return

        self._async_update_temp(new_state)
        await self.async_update_ha_state()

    @callback
    def _async_update_temp(self, state):
        """Update thermostat with latest state from sensor."""
        try:
            self._cur_temp = float(state.state)
        except ValueError as ex:
            _LOGGER.error("Unable to update from sensor: %s", ex)

    @property
    def _is_device_active(self):
        """If the toggleable device is currently active."""
        # return self.hass.states.is_state(self.heater_entity_id, STATE_ON)
        return self.power_mode == STATE_ON 

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._support_flags

    # def set_preset_mode(self, preset_mode):
    #     """Set new preset mode."""
    #     if preset_mode == PRESET_AWAY and not self._is_away:
    #         self._is_away = True
    #         self._saved_target_temp = self._target_temp
    #         self._target_temp = self._away_temp
    #     elif preset_mode == PRESET_NONE and self._is_away:
    #         self._is_away = False
    #         self._target_temp = self._saved_target_temp
    #     await self.hass.async_add_executor_job(self.send_ir)
    #     await self.async_update_ha_state()

    async def async_set_preset_mode(self, preset_mode):
        """Set new preset mode.
        This method must be run in the event loop and returns a coroutine.
        """
        if preset_mode == PRESET_AWAY and not self._is_away:
            self._is_away = True
            self._saved_target_temp = self._target_temp
            self._target_temp = self._away_temp
        elif preset_mode == PRESET_NONE and self._is_away:
            self._is_away = False
            self._target_temp = self._saved_target_temp
        await self.hass.async_add_executor_job(self.send_ir)
        await self.async_update_ha_state()

    def send_ir(self):
        curr_operation = self._hvac_mode
        fan_speed = self.fan_mode
        #tweek for some ELECTRA_AC devices
        if HVAC_FAN_MAX_HIGH in self._fan_list and HVAC_FAN_AUTO_MAX in self._fan_list:
            if self.fan_mode == FAN_HIGH:
                fan_speed = HVAC_FAN_MAX
            if self.fan_mode == HVAC_FAN_MAX:
                fan_speed = HVAC_FAN_AUTO

        #Set the swing mode - default off
        swing_h = STATE_OFF
        swing_v = STATE_OFF
        if self.swing_mode == SWING_BOTH:
            swing_h = STATE_AUTO
            swing_v = STATE_AUTO
        elif self.swing_mode == SWING_HORIZONTAL:
            swing_h = STATE_AUTO
        elif self.swing_mode == SWING_VERTICAL:
            swing_v = STATE_AUTO
        #Poplate the payload
        payload = '{"Vendor":"' + self._protocol +'","Model":' + self._model + ', "Power":"' + self.power_mode + '","Mode":"' + curr_operation + '","Celsius":"' + self._celsius + '","Temp":' + str(self._target_temp) + ',"FanSpeed":"' + fan_speed + '","SwingV":"' + swing_v + '","SwingH":"' + swing_h + '", "Quiet":"' + self._quiet + '","Turbo":"' + self._turbo + '","Econo":"' + self._econo + '","Light":"' + self._light + '","Filter":"' + self._filterr + '","Clean":"' + self._clean + '","Beep":"' + self._beep + '","Sleep":' + self._sleep + '}'
        #Publish mqtt message
        mqtt.async_publish(self.hass,self.topic,payload)
"""
A climate platform that adds support for Midea air conditioning units.

For more details about this platform, please refer to the documentation
https://github.com/mac-zhou/midea-ac-py

This is still early work in progress
"""
import logging

import voluptuous as vol
from datetime import timedelta

import homeassistant.helpers.config_validation as cv
from homeassistant.components.climate import PLATFORM_SCHEMA
try:
    from homeassistant.components.climate import ClimateEntity
except ImportError:
    from homeassistant.components.climate import ClimateDevice as ClimateEntity
from homeassistant.components.climate.const import (
    SUPPORT_TARGET_TEMPERATURE, SUPPORT_FAN_MODE, SUPPORT_SWING_MODE,
    SUPPORT_PRESET_MODE, PRESET_NONE, PRESET_ECO, PRESET_BOOST)
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, TEMP_CELSIUS, TEMP_FAHRENHEIT, \
    ATTR_TEMPERATURE

from homeassistant.helpers.restore_state import RestoreEntity

_LOGGER = logging.getLogger(__name__)

CONF_TYPE = 'type'
CONF_HOST = 'host'
CONF_ID = 'id'
CONF_TOKEN = 'token'
CONF_K1 = 'k1'
CONF_PORT = 'port'
CONF_PROMPT_TONE = 'prompt_tone'
CONF_TEMP_STEP = 'temp_step'
CONF_INCLUDE_OFF_AS_STATE = 'include_off_as_state'
CONF_USE_FAN_ONLY_WORKAROUND = 'use_fan_only_workaround'
CONF_KEEP_LAST_KNOWN_ONLINE_STATE = 'keep_last_known_online_state'

SCAN_INTERVAL = timedelta(seconds=15)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_ID): cv.string,
    vol.Optional(CONF_TOKEN, default=""): cv.string,
    vol.Optional(CONF_K1, default=""): cv.string,
    vol.Optional(CONF_PORT, default=6444): vol.Coerce(int),
    vol.Optional(CONF_TYPE, default=0xac): vol.Coerce(int),
    vol.Optional(CONF_PROMPT_TONE, default=True): vol.Coerce(bool),
    vol.Optional(CONF_TEMP_STEP, default=1.0): vol.Coerce(float),
    vol.Optional(CONF_INCLUDE_OFF_AS_STATE, default=True): vol.Coerce(bool),
    vol.Optional(CONF_USE_FAN_ONLY_WORKAROUND, default=False): vol.Coerce(bool),
    vol.Optional(CONF_KEEP_LAST_KNOWN_ONLINE_STATE, default=False): vol.Coerce(bool)
})

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE \
                | SUPPORT_SWING_MODE | SUPPORT_PRESET_MODE


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the Midea lan service and query appliances."""

    from msmart.device import air_conditioning as ac

    device_ip = config.get(CONF_HOST)
    device_id = config.get(CONF_ID)
    device_token = config.get(CONF_TOKEN)
    device_k1 = config.get(CONF_K1)
    device_port = config.get(CONF_PORT)
    prompt_tone = config.get(CONF_PROMPT_TONE)
    temp_step = config.get(CONF_TEMP_STEP)
    include_off_as_state = config.get(CONF_INCLUDE_OFF_AS_STATE)
    use_fan_only_workaround = config.get(CONF_USE_FAN_ONLY_WORKAROUND)
    keep_last_known_online_state = config.get(CONF_KEEP_LAST_KNOWN_ONLINE_STATE)

    device = ac(device_ip, int(device_id), device_port)
    device._type = config.get(CONF_TYPE)
    if device_token and device_k1:
        # device.authenticate(device_k1, device_token)
        device._protocol_version = 3
        device._token = bytearray.fromhex(device_token)
        device._key = bytearray.fromhex(device_k1)
        device._lan_service._token = device._token
        device._lan_service._key = device._key
        
    # device = client.setup()
    device.prompt_tone = prompt_tone
    device.keep_last_known_online_state = keep_last_known_online_state
    entities = []
    entities.append(MideaClimateACDevice(
            hass, device, temp_step, include_off_as_state,
            use_fan_only_workaround))

    async_add_entities(entities)


class MideaClimateACDevice(ClimateEntity, RestoreEntity):
    """Representation of a Midea climate AC device."""

    def __init__(self, hass, device, temp_step: float,
                 include_off_as_state: bool, use_fan_only_workaround: bool):
        """Initialize the climate device."""
        from msmart.device import air_conditioning as ac

        self._operation_list = ac.operational_mode_enum.list()
        self._fan_list = ac.fan_speed_enum.list()
        self._swing_list = ac.swing_mode_enum.list()
        if include_off_as_state:
            self._operation_list.append("off")
        self._support_flags = SUPPORT_FLAGS
        # the LED display on the AC should use the same unit as that in homeassistant
        device.fahrenheit_unit = (hass.config.units.temperature_unit == TEMP_FAHRENHEIT)
        self._device = device
        self._unit_of_measurement = TEMP_CELSIUS
        self._target_temperature_step = temp_step
        self._include_off_as_state = include_off_as_state
        self._use_fan_only_workaround = use_fan_only_workaround

        self.hass = hass
        self._old_state = None
        self._changed = False

    async def apply_changes(self):
        if not self._changed:
            return
        await self.hass.async_add_executor_job(self._device.apply)
        self._old_state = None
        await self.async_update_ha_state()
        self._changed = False

    async def async_update(self):
        """Retrieve latest state from the appliance if no changes made,
        otherwise update the remote device state."""
        if self._changed:
            await self.hass.async_add_executor_job(self._device.apply)
            self._changed = False
        elif not self._use_fan_only_workaround:
            self._old_state = None
            await self.hass.async_add_executor_job(self._device.refresh)

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()
        self._old_state = await self.async_get_last_state()

    @property
    def state_attributes(self):
        attrs = super().state_attributes
        attrs["outdoor_temperature"] = self._device.outdoor_temperature

        return attrs

    @property
    def available(self):
        """Checks if the appliance is available for commands."""
        return self._device.online

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._support_flags

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return self._target_temperature_step

    @property
    def hvac_modes(self):
        """Return the list of available operation modes."""
        return self._operation_list

    @property
    def fan_modes(self):
        """Return the list of available fan modes."""
        return self._fan_list

    @property
    def swing_modes(self):
        """List of available swing modes."""
        return self._swing_list

    @property
    def assumed_state(self):
        """Assume state rather than refresh to workaround fan_only bug."""
        return self._use_fan_only_workaround

    @property
    def should_poll(self):
        """Poll the appliance for changes, there is no notification capability in the Midea API"""
        return not self._use_fan_only_workaround

    @property
    def unique_id(self):
        return self._device.id

    @property
    def name(self):
        """Return the name of the climate device."""
        return "midea_{:2x}_{}".format(self._device._type, self._device.id)

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def current_temperature(self):
        """Return the current temperature."""
        if self._old_state is not None:
            return self._old_state.attributes.get('current_temperature')

        return self._device.indoor_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        if self._old_state is not None and 'temperature' in self._old_state.attributes:
            self._device.target_temperature = self._old_state.attributes['temperature']
            return self._old_state.attributes['temperature']

        return self._device.target_temperature

    @property
    def hvac_mode(self):
        """Return current operation ie. heat, cool, idle."""
        if self._old_state is not None:
            from msmart.device import air_conditioning as ac
            self._device.power_state = self._include_off_as_state and self._old_state.state != 'off'
            if self._old_state.state in ac.operational_mode_enum.list():
                self._device.operational_mode = ac.operational_mode_enum[self._old_state.state]
            return self._old_state.state

        if self._include_off_as_state and not self._device.power_state:
            return "off"
        return self._device.operational_mode.name

    @property
    def fan_mode(self):
        """Return the fan setting."""
        if self._old_state is not None and 'fan_mode' in self._old_state.attributes:
            from msmart.device import air_conditioning as ac
            self._device.fan_speed = ac.fan_speed_enum[self._old_state.attributes['fan_mode']]
            return self._old_state.attributes['fan_mode']

        return self._device.fan_speed.name

    @property
    def swing_mode(self):
        """Return the swing setting."""
        if self._old_state is not None and 'swing_mode' in self._old_state.attributes:
            from msmart.device import air_conditioning as ac
            self._device.swing_mode = ac.swing_mode_enum[self._old_state.attributes['swing_mode']]
            return self._old_state.attributes['swing_mode']

        return self._device.swing_mode.name

    @property
    def is_on(self):
        """Return true if the device is on."""
        return self._device.power_state

    async def async_set_temperature(self, **kwargs):
        """Set new target temperatures."""
        if kwargs.get(ATTR_TEMPERATURE) is not None:
            # grab temperature from front end UI
            temp = kwargs.get(ATTR_TEMPERATURE)

            # round temperature to nearest .5
            temp = round(temp * 2) / 2

            # send temperature to unit
            self._device.target_temperature = temp
            self._changed = True
            await self.apply_changes()

    async def async_set_swing_mode(self, swing_mode):
        """Set swing mode."""
        from msmart.device import air_conditioning as ac
        self._device.swing_mode = ac.swing_mode_enum[swing_mode]
        self._changed = True
        await self.apply_changes()

    async def async_set_fan_mode(self, fan_mode):
        """Set fan mode."""
        from msmart.device import air_conditioning as ac
        self._device.fan_speed = ac.fan_speed_enum[fan_mode]
        self._changed = True
        await self.apply_changes()

    async def async_set_hvac_mode(self, hvac_mode):
        """Set hvac mode."""
        from msmart.device import air_conditioning as ac
        if self._include_off_as_state and hvac_mode == "off":
            self._device.power_state = False
        else:
            if self._include_off_as_state:
                self._device.power_state = True
            self._device.operational_mode = ac.operational_mode_enum[hvac_mode]
        self._changed = True
        await self.apply_changes()

    async def async_set_preset_mode(self, preset_mode: str):
        if preset_mode == PRESET_NONE:
            self._device.eco_mode = False
            self._device.turbo_mode = False
        elif preset_mode == PRESET_BOOST:
            self._device.eco_mode = False
            self._device.turbo_mode = True
        elif preset_mode == PRESET_ECO:
            self._device.turbo_mode = False
            self._device.eco_mode = True

        self._changed = True
        await self.apply_changes()

    @property
    def preset_modes(self):
        return [PRESET_NONE, PRESET_ECO, PRESET_BOOST]

    @property
    def preset_mode(self):
        if self._old_state is not None and 'preset_mode' in self._old_state.attributes:
            preset_mode = self._old_state.attributes['preset_mode']
            if preset_mode == PRESET_ECO:
                self._device.eco_mode = True
                self._device.turbo_mode = False
            elif preset_mode == PRESET_BOOST:
                self._device.turbo_mode = True
                self._device.eco_mode = False

            return preset_mode

        if self._device.eco_mode:
            return PRESET_ECO
        elif self._device.turbo_mode:
            return PRESET_BOOST
        else:
            return PRESET_NONE

    async def async_turn_on(self):
        """Turn on."""
        self._device.power_state = True
        self._changed = True
        await self.apply_changes()

    async def async_turn_off(self):
        """Turn off."""
        self._device.power_state = False
        self._changed = True
        await self.apply_changes()

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return 17

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return 30

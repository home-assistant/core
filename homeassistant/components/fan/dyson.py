"""Support for Dyson Pure Cool link fan.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/fan.dyson/
"""
import asyncio
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.dyson import DYSON_DEVICES
from homeassistant.components.fan import (
    DOMAIN, SUPPORT_OSCILLATE, SUPPORT_SET_SPEED, FanEntity)
from homeassistant.const import CONF_ENTITY_ID

_LOGGER = logging.getLogger(__name__)

CONF_NIGHT_MODE = 'night_mode'

ATTR_IS_NIGHT_MODE = 'is_night_mode'
ATTR_IS_AUTO_MODE = 'is_auto_mode'

DEPENDENCIES = ['dyson']
DYSON_FAN_DEVICES = 'dyson_fan_devices'

SERVICE_SET_NIGHT_MODE = 'dyson_set_night_mode'

DYSON_SET_NIGHT_MODE_SCHEMA = vol.Schema({
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
    vol.Required(CONF_NIGHT_MODE): cv.boolean,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Dyson fan components."""
    from libpurecoollink.dyson_pure_cool_link import DysonPureCoolLink

    _LOGGER.debug("Creating new Dyson fans")
    if DYSON_FAN_DEVICES not in hass.data:
        hass.data[DYSON_FAN_DEVICES] = []

    # Get Dyson Devices from parent component
    for device in [d for d in hass.data[DYSON_DEVICES] if
                   isinstance(d, DysonPureCoolLink)]:
        dyson_entity = DysonPureCoolLinkDevice(hass, device)
        hass.data[DYSON_FAN_DEVICES].append(dyson_entity)

    add_entities(hass.data[DYSON_FAN_DEVICES])

    def service_handle(service):
        """Handle the Dyson services."""
        entity_id = service.data.get(CONF_ENTITY_ID)
        night_mode = service.data.get(CONF_NIGHT_MODE)
        fan_device = next([fan for fan in hass.data[DYSON_FAN_DEVICES] if
                           fan.entity_id == entity_id].__iter__(), None)
        if fan_device is None:
            _LOGGER.warning("Unable to find Dyson fan device %s",
                            str(entity_id))
            return

        if service.service == SERVICE_SET_NIGHT_MODE:
            fan_device.night_mode(night_mode)

    # Register dyson service(s)
    hass.services.register(
        DOMAIN, SERVICE_SET_NIGHT_MODE, service_handle,
        schema=DYSON_SET_NIGHT_MODE_SCHEMA)


class DysonPureCoolLinkDevice(FanEntity):
    """Representation of a Dyson fan."""

    def __init__(self, hass, device):
        """Initialize the fan."""
        _LOGGER.debug("Creating device %s", device.name)
        self.hass = hass
        self._device = device

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Call when entity is added to hass."""
        self.hass.async_add_job(
            self._device.add_message_listener, self.on_message)

    def on_message(self, message):
        """Call when new messages received from the fan."""
        from libpurecoollink.dyson_pure_state import DysonPureCoolState

        if isinstance(message, DysonPureCoolState):
            _LOGGER.debug("Message received for fan device %s: %s", self.name,
                          message)
            self.schedule_update_ha_state()

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the display name of this fan."""
        return self._device.name

    def set_speed(self, speed: str) -> None:
        """Set the speed of the fan. Never called ??."""
        from libpurecoollink.const import FanSpeed, FanMode

        _LOGGER.debug("Set fan speed to: %s", speed)

        if speed == FanSpeed.FAN_SPEED_AUTO.value:
            self._device.set_configuration(fan_mode=FanMode.AUTO)
        else:
            fan_speed = FanSpeed('{0:04d}'.format(int(speed)))
            self._device.set_configuration(
                fan_mode=FanMode.FAN, fan_speed=fan_speed)

    def turn_on(self, speed: str = None, **kwargs) -> None:
        """Turn on the fan."""
        from libpurecoollink.const import FanSpeed, FanMode

        _LOGGER.debug("Turn on fan %s with speed %s", self.name, speed)
        if speed:
            if speed == FanSpeed.FAN_SPEED_AUTO.value:
                self._device.set_configuration(fan_mode=FanMode.AUTO)
            else:
                fan_speed = FanSpeed('{0:04d}'.format(int(speed)))
                self._device.set_configuration(
                    fan_mode=FanMode.FAN, fan_speed=fan_speed)
        else:
            # Speed not set, just turn on
            self._device.set_configuration(fan_mode=FanMode.FAN)

    def turn_off(self, **kwargs) -> None:
        """Turn off the fan."""
        from libpurecoollink.const import FanMode

        _LOGGER.debug("Turn off fan %s", self.name)
        self._device.set_configuration(fan_mode=FanMode.OFF)

    def oscillate(self, oscillating: bool) -> None:
        """Turn on/off oscillating."""
        from libpurecoollink.const import Oscillation

        _LOGGER.debug("Turn oscillation %s for device %s", oscillating,
                      self.name)

        if oscillating:
            self._device.set_configuration(
                oscillation=Oscillation.OSCILLATION_ON)
        else:
            self._device.set_configuration(
                oscillation=Oscillation.OSCILLATION_OFF)

    @property
    def oscillating(self):
        """Return the oscillation state."""
        return self._device.state and self._device.state.oscillation == "ON"

    @property
    def is_on(self):
        """Return true if the entity is on."""
        if self._device.state:
            return self._device.state.fan_mode == "FAN"
        return False

    @property
    def speed(self) -> str:
        """Return the current speed."""
        from libpurecoollink.const import FanSpeed

        if self._device.state:
            if self._device.state.speed == FanSpeed.FAN_SPEED_AUTO.value:
                return self._device.state.speed
            return int(self._device.state.speed)
        return None

    @property
    def current_direction(self):
        """Return direction of the fan [forward, reverse]."""
        return None

    @property
    def is_night_mode(self):
        """Return Night mode."""
        return self._device.state.night_mode == "ON"

    def night_mode(self, night_mode: bool) -> None:
        """Turn fan in night mode."""
        from libpurecoollink.const import NightMode

        _LOGGER.debug("Set %s night mode %s", self.name, night_mode)
        if night_mode:
            self._device.set_configuration(night_mode=NightMode.NIGHT_MODE_ON)
        else:
            self._device.set_configuration(night_mode=NightMode.NIGHT_MODE_OFF)

    @property
    def is_auto_mode(self):
        """Return auto mode."""
        return self._device.state.fan_mode == "AUTO"

    def auto_mode(self, auto_mode: bool) -> None:
        """Turn fan in auto mode."""
        from libpurecoollink.const import FanMode

        _LOGGER.debug("Set %s auto mode %s", self.name, auto_mode)
        if auto_mode:
            self._device.set_configuration(fan_mode=FanMode.AUTO)
        else:
            self._device.set_configuration(fan_mode=FanMode.FAN)

    @property
    def speed_list(self) -> list:
        """Get the list of available speeds."""
        from libpurecoollink.const import FanSpeed

        supported_speeds = [
            FanSpeed.FAN_SPEED_AUTO.value,
            int(FanSpeed.FAN_SPEED_1.value),
            int(FanSpeed.FAN_SPEED_2.value),
            int(FanSpeed.FAN_SPEED_3.value),
            int(FanSpeed.FAN_SPEED_4.value),
            int(FanSpeed.FAN_SPEED_5.value),
            int(FanSpeed.FAN_SPEED_6.value),
            int(FanSpeed.FAN_SPEED_7.value),
            int(FanSpeed.FAN_SPEED_8.value),
            int(FanSpeed.FAN_SPEED_9.value),
            int(FanSpeed.FAN_SPEED_10.value),
        ]

        return supported_speeds

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORT_OSCILLATE | SUPPORT_SET_SPEED

    @property
    def device_state_attributes(self) -> dict:
        """Return optional state attributes."""
        return {
            ATTR_IS_NIGHT_MODE: self.is_night_mode,
            ATTR_IS_AUTO_MODE: self.is_auto_mode
            }

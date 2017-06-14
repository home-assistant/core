"""Support for Dyson Pure Cool link fan."""
import logging
import asyncio
from os import path
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.components.fan import (FanEntity, SUPPORT_OSCILLATE,
                                          SUPPORT_SET_SPEED,
                                          DOMAIN)
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.components.dyson import DYSON_DEVICES
from homeassistant.config import load_yaml_config_file

DEPENDENCIES = ['dyson']

_LOGGER = logging.getLogger(__name__)


DYSON_FAN_DEVICES = "dyson_fan_devices"
SERVICE_SET_NIGHT_MODE = 'dyson_set_night_mode'

DYSON_SET_NIGHT_MODE_SCHEMA = vol.Schema({
    vol.Required('entity_id'): cv.entity_id,
    vol.Required('night_mode'): cv.boolean
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Dyson fan components."""
    _LOGGER.info("Creating new Dyson fans")
    if DYSON_FAN_DEVICES not in hass.data:
        hass.data[DYSON_FAN_DEVICES] = []

    # Get Dyson Devices from parent component
    for device in hass.data[DYSON_DEVICES]:
        dyson_entity = DysonPureCoolLinkDevice(hass, device)
        hass.data[DYSON_FAN_DEVICES].append(dyson_entity)

    add_devices(hass.data[DYSON_FAN_DEVICES])

    descriptions = load_yaml_config_file(
        path.join(path.dirname(__file__), 'services.yaml'))

    def service_handle(service):
        """Handle dyson services."""
        entity_id = service.data.get('entity_id')
        night_mode = service.data.get('night_mode')
        fan_device = next([fan for fan in hass.data[DYSON_FAN_DEVICES] if
                           fan.entity_id == entity_id].__iter__(), None)
        if fan_device is None:
            _LOGGER.warning("Unable to find Dyson fan device %s",
                            str(entity_id))
            return

        if service.service == SERVICE_SET_NIGHT_MODE:
            fan_device.night_mode(night_mode)

    # Register dyson service(s)
    hass.services.register(DOMAIN, SERVICE_SET_NIGHT_MODE,
                           service_handle,
                           descriptions.get(SERVICE_SET_NIGHT_MODE),
                           schema=DYSON_SET_NIGHT_MODE_SCHEMA)


class DysonPureCoolLinkDevice(FanEntity):
    """Representation of a Dyson fan."""

    def __init__(self, hass, device):
        """Initialize the fan."""
        _LOGGER.info("Creating device %s", device.name)
        self.hass = hass
        self._device = device

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Callback when entity is added to hass."""
        self.hass.async_add_job(
            self._device.add_message_listener(self.on_message))

    def on_message(self, message):
        """Called when new messages received from the fan."""
        _LOGGER.debug(
            "Message received for fan device %s : %s", self.name, message)
        self.schedule_update_ha_state()

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the display name of this fan."""
        return self._device.name

    def set_speed(self: ToggleEntity, speed: str) -> None:
        """Set the speed of the fan. Never called ??."""
        _LOGGER.debug("Set fan speed to: " + speed)
        from libpurecoollink.const import FanSpeed, FanMode
        if speed == FanSpeed.FAN_SPEED_AUTO.value:
            self._device.set_configuration(fan_mode=FanMode.AUTO)
        else:
            fan_speed = FanSpeed('{0:04d}'.format(int(speed)))
            self._device.set_configuration(fan_mode=FanMode.FAN,
                                           fan_speed=fan_speed)

    def turn_on(self: ToggleEntity, speed: str=None, **kwargs) -> None:
        """Turn on the fan."""
        _LOGGER.debug("Turn on fan %s with speed %s", self.name, speed)
        from libpurecoollink.const import FanSpeed, FanMode
        if speed:
            if speed == FanSpeed.FAN_SPEED_AUTO.value:
                self._device.set_configuration(fan_mode=FanMode.AUTO)
            else:
                fan_speed = FanSpeed('{0:04d}'.format(int(speed)))
                self._device.set_configuration(fan_mode=FanMode.FAN,
                                               fan_speed=fan_speed)
        else:
            # Speed not set, just turn on
            self._device.set_configuration(fan_mode=FanMode.FAN)

    def turn_off(self: ToggleEntity, **kwargs) -> None:
        """Turn off the fan."""
        _LOGGER.debug("Turn off fan %s", self.name)
        from libpurecoollink.const import FanMode
        self._device.set_configuration(fan_mode=FanMode.OFF)

    def oscillate(self: ToggleEntity, oscillating: bool) -> None:
        """Turn on/off oscillating."""
        _LOGGER.debug("Turn oscillation %s for device %s", oscillating,
                      self.name)
        from libpurecoollink.const import Oscillation

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
            return self._device.state.fan_state == "FAN"
        return False

    @property
    def speed(self) -> str:
        """Return the current speed."""
        if self._device.state:
            from libpurecoollink.const import FanSpeed
            if self._device.state.speed == FanSpeed.FAN_SPEED_AUTO.value:
                return self._device.state.speed
            else:
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

    def night_mode(self: ToggleEntity, night_mode: bool) -> None:
        """Turn fan in night mode."""
        _LOGGER.debug("Set %s night mode %s", self.name, night_mode)
        from libpurecoollink.const import NightMode
        if night_mode:
            self._device.set_configuration(night_mode=NightMode.NIGHT_MODE_ON)
        else:
            self._device.set_configuration(night_mode=NightMode.NIGHT_MODE_OFF)

    @property
    def is_auto_mode(self):
        """Return auto mode."""
        return self._device.state.fan_mode == "AUTO"

    def auto_mode(self: ToggleEntity, auto_mode: bool) -> None:
        """Turn fan in auto mode."""
        _LOGGER.debug("Set %s auto mode %s", self.name, auto_mode)
        from libpurecoollink.const import FanMode
        if auto_mode:
            self._device.set_configuration(fan_mode=FanMode.AUTO)
        else:
            self._device.set_configuration(fan_mode=FanMode.FAN)

    @property
    def speed_list(self: ToggleEntity) -> list:
        """Get the list of available speeds."""
        from libpurecoollink.const import FanSpeed
        supported_speeds = [FanSpeed.FAN_SPEED_AUTO.value,
                            int(FanSpeed.FAN_SPEED_1.value),
                            int(FanSpeed.FAN_SPEED_2.value),
                            int(FanSpeed.FAN_SPEED_3.value),
                            int(FanSpeed.FAN_SPEED_4.value),
                            int(FanSpeed.FAN_SPEED_5.value),
                            int(FanSpeed.FAN_SPEED_6.value),
                            int(FanSpeed.FAN_SPEED_7.value),
                            int(FanSpeed.FAN_SPEED_8.value),
                            int(FanSpeed.FAN_SPEED_9.value),
                            int(FanSpeed.FAN_SPEED_10.value)]

        return supported_speeds

    @property
    def supported_features(self: ToggleEntity) -> int:
        """Flag supported features."""
        return SUPPORT_OSCILLATE | SUPPORT_SET_SPEED

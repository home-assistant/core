"""Support for Dyson Pure Cool link fan."""
import logging
from homeassistant.components.fan import (FanEntity,
                                          SUPPORT_OSCILLATE, SUPPORT_SET_SPEED)
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.components.dyson import DYSON_DEVICES

DEPENDENCIES = ['dyson']
REQUIREMENTS = ['libpurecoollink==0.1.5']

_LOGGER = logging.getLogger(__name__)

NIGHT_MODE = 'NIGHT_MODE'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Dyson fan components."""
    _LOGGER.info("Creating new Dyson fans")
    devices = []
    # Get Dyson Devices from parent component
    for device in hass.data[DYSON_DEVICES]:
        devices.append(DysonPureCoolLinkDevice(hass, device))
    add_devices(devices)


class DysonPureCoolLinkDevice(FanEntity):
    """Representation of a Dyson fan."""

    def on_message(self, message):
        """Called when new messages received from the fan."""
        _LOGGER.debug("Message received for fan device %s : %s", self.name,
                      message)
        if self.hass and self.entity_id:
            self.schedule_update_ha_state()

    def __init__(self, hass, device):
        """Initialize the fan."""
        _LOGGER.info("Creating device %s", device.name)
        self.hass = hass
        self._device = device
        self._device.add_message_listener(self.on_message)

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
        from libpurecoollink.const import FanSpeed, FanMode, NightMode
        fan_speed = FanSpeed(speed)
        self._device.set_configuration(fan_mode=FanMode.FAN,
                                       night_mode=NightMode.NIGHT_MODE_OFF,
                                       fan_speed=fan_speed)

    def turn_on(self: ToggleEntity, speed: str=None, **kwargs) -> None:
        """Turn on the fan."""
        _LOGGER.debug("Turn on fan %s with speed %s", self.name, speed)
        from libpurecoollink.const import FanSpeed, FanMode, NightMode
        if speed:
            # Turn on fan with specified speed
            if speed == NIGHT_MODE:
                night_mode = NightMode.NIGHT_MODE_ON
                self._device.set_configuration(fan_mode=FanMode.AUTO,
                                               night_mode=night_mode)
            else:
                fan_speed = FanSpeed(speed)
                night_mode = NightMode.NIGHT_MODE_OFF
                if fan_speed == FanSpeed.FAN_SPEED_AUTO:
                    self._device.set_configuration(fan_mode=FanMode.AUTO,
                                                   night_mode=night_mode)
                else:
                    self._device.set_configuration(fan_mode=FanMode.FAN,
                                                   night_mode=night_mode,
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
            return self._device.state.fan_mode in ['FAN', 'AUTO']
        return False

    @property
    def speed(self) -> str:
        """Return the current speed."""
        if self._device.state:
            if self._device.state.night_mode == 'ON':
                return NIGHT_MODE
            else:
                return self._device.state.speed
        return None

    @property
    def current_direction(self):
        """Return direction of the fan [forward, reverse]."""
        return None

    @property
    def speed_list(self: ToggleEntity) -> list:
        """Get the list of available speeds."""
        from libpurecoollink.const import FanSpeed
        supported_speeds = [FanSpeed.FAN_SPEED_AUTO.value, NIGHT_MODE,
                            FanSpeed.FAN_SPEED_1.value,
                            FanSpeed.FAN_SPEED_2.value,
                            FanSpeed.FAN_SPEED_3.value,
                            FanSpeed.FAN_SPEED_4.value,
                            FanSpeed.FAN_SPEED_5.value,
                            FanSpeed.FAN_SPEED_6.value,
                            FanSpeed.FAN_SPEED_7.value,
                            FanSpeed.FAN_SPEED_8.value,
                            FanSpeed.FAN_SPEED_9.value,
                            FanSpeed.FAN_SPEED_10.value]

        return supported_speeds

    @property
    def supported_features(self: ToggleEntity) -> int:
        """Flag supported features."""
        return SUPPORT_OSCILLATE | SUPPORT_SET_SPEED

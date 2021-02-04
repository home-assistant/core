"""Support for the Dyson 360 eye vacuum cleaner robot."""
import logging

from libpurecool.const import Dyson360EyeMode, PowerMode
from libpurecool.dyson_360_eye import Dyson360Eye

from homeassistant.components.vacuum import (
    SUPPORT_BATTERY,
    SUPPORT_FAN_SPEED,
    SUPPORT_PAUSE,
    SUPPORT_RETURN_HOME,
    SUPPORT_STATUS,
    SUPPORT_STOP,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    VacuumEntity,
)
from homeassistant.helpers.icon import icon_for_battery_level

from . import DYSON_DEVICES, DysonEntity

_LOGGER = logging.getLogger(__name__)

ATTR_CLEAN_ID = "clean_id"
ATTR_FULL_CLEAN_TYPE = "full_clean_type"
ATTR_POSITION = "position"

DYSON_360_EYE_DEVICES = "dyson_360_eye_devices"

SUPPORT_DYSON = (
    SUPPORT_TURN_ON
    | SUPPORT_TURN_OFF
    | SUPPORT_PAUSE
    | SUPPORT_RETURN_HOME
    | SUPPORT_FAN_SPEED
    | SUPPORT_STATUS
    | SUPPORT_BATTERY
    | SUPPORT_STOP
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Dyson 360 Eye robot vacuum platform."""
    _LOGGER.debug("Creating new Dyson 360 Eye robot vacuum")
    if DYSON_360_EYE_DEVICES not in hass.data:
        hass.data[DYSON_360_EYE_DEVICES] = []

    # Get Dyson Devices from parent component
    for device in [d for d in hass.data[DYSON_DEVICES] if isinstance(d, Dyson360Eye)]:
        dyson_entity = Dyson360EyeDevice(device)
        hass.data[DYSON_360_EYE_DEVICES].append(dyson_entity)

    add_entities(hass.data[DYSON_360_EYE_DEVICES])
    return True


class Dyson360EyeDevice(DysonEntity, VacuumEntity):
    """Dyson 360 Eye robot vacuum device."""

    def __init__(self, device):
        """Dyson 360 Eye robot vacuum device."""
        super().__init__(device, None)

    @property
    def status(self):
        """Return the status of the vacuum cleaner."""
        dyson_labels = {
            Dyson360EyeMode.INACTIVE_CHARGING: "Stopped - Charging",
            Dyson360EyeMode.INACTIVE_CHARGED: "Stopped - Charged",
            Dyson360EyeMode.FULL_CLEAN_PAUSED: "Paused",
            Dyson360EyeMode.FULL_CLEAN_RUNNING: "Cleaning",
            Dyson360EyeMode.FULL_CLEAN_ABORTED: "Returning home",
            Dyson360EyeMode.FULL_CLEAN_INITIATED: "Start cleaning",
            Dyson360EyeMode.FAULT_USER_RECOVERABLE: "Error - device blocked",
            Dyson360EyeMode.FAULT_REPLACE_ON_DOCK: "Error - Replace device on dock",
            Dyson360EyeMode.FULL_CLEAN_FINISHED: "Finished",
            Dyson360EyeMode.FULL_CLEAN_NEEDS_CHARGE: "Need charging",
        }
        return dyson_labels.get(self._device.state.state, self._device.state.state)

    @property
    def battery_level(self):
        """Return the battery level of the vacuum cleaner."""
        return self._device.state.battery_level

    @property
    def fan_speed(self):
        """Return the fan speed of the vacuum cleaner."""
        speed_labels = {PowerMode.MAX: "Max", PowerMode.QUIET: "Quiet"}
        return speed_labels[self._device.state.power_mode]

    @property
    def fan_speed_list(self):
        """Get the list of available fan speed steps of the vacuum cleaner."""
        return ["Quiet", "Max"]

    @property
    def device_state_attributes(self):
        """Return the specific state attributes of this vacuum cleaner."""
        return {ATTR_POSITION: str(self._device.state.position)}

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        return self._device.state.state in [
            Dyson360EyeMode.FULL_CLEAN_INITIATED,
            Dyson360EyeMode.FULL_CLEAN_ABORTED,
            Dyson360EyeMode.FULL_CLEAN_RUNNING,
        ]

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return True

    @property
    def supported_features(self):
        """Flag vacuum cleaner robot features that are supported."""
        return SUPPORT_DYSON

    @property
    def battery_icon(self):
        """Return the battery icon for the vacuum cleaner."""
        charging = self._device.state.state in [Dyson360EyeMode.INACTIVE_CHARGING]
        return icon_for_battery_level(
            battery_level=self.battery_level, charging=charging
        )

    def turn_on(self, **kwargs):
        """Turn the vacuum on."""
        _LOGGER.debug("Turn on device %s", self.name)
        if self._device.state.state in [Dyson360EyeMode.FULL_CLEAN_PAUSED]:
            self._device.resume()
        else:
            self._device.start()

    def turn_off(self, **kwargs):
        """Turn the vacuum off and return to home."""
        _LOGGER.debug("Turn off device %s", self.name)
        self._device.pause()

    def stop(self, **kwargs):
        """Stop the vacuum cleaner."""
        _LOGGER.debug("Stop device %s", self.name)
        self._device.pause()

    def set_fan_speed(self, fan_speed, **kwargs):
        """Set fan speed."""
        _LOGGER.debug("Set fan speed %s on device %s", fan_speed, self.name)
        power_modes = {"Quiet": PowerMode.QUIET, "Max": PowerMode.MAX}
        self._device.set_power_mode(power_modes[fan_speed])

    def start_pause(self, **kwargs):
        """Start, pause or resume the cleaning task."""
        if self._device.state.state in [Dyson360EyeMode.FULL_CLEAN_PAUSED]:
            _LOGGER.debug("Resume device %s", self.name)
            self._device.resume()
        elif self._device.state.state in [
            Dyson360EyeMode.INACTIVE_CHARGED,
            Dyson360EyeMode.INACTIVE_CHARGING,
        ]:
            _LOGGER.debug("Start device %s", self.name)
            self._device.start()
        else:
            _LOGGER.debug("Pause device %s", self.name)
            self._device.pause()

    def return_to_base(self, **kwargs):
        """Set the vacuum cleaner to return to the dock."""
        _LOGGER.debug("Return to base device %s", self.name)
        self._device.abort()

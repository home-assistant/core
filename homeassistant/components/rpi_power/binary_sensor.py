"""
A sensor platform which detects underruns and capped status from the official Raspberry Pi Kernel.

Minimal Kernel needed is 4.14+
"""
import logging
import os

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_PROBLEM,
    BinarySensorEntity,
)

_LOGGER = logging.getLogger(__name__)

SYSFILE = "/sys/devices/platform/soc/soc:firmware/get_throttled"

DESCRIPTION_WORKING = "Everything is working as intended."
DESCRIPTION_UNDER_VOLTAGE = "Under-voltage was detected, consider getting a uninterruptible power supply for your Raspberry Pi."
DESCRIPTION_LIMITED = "Your Raspberry Pi is limited due to a bad powersupply, replace the power supply cable or power supply itself."
DESCRIPTION_THROTTLED = "The Raspberry Pi is throttled due to a bad power supply this can lead to corruption and instability, please replace your changer and cables."
DESCRIPTION_OVERHEATING = (
    "Your Raspberry Pi is overheating, consider getting a fan or heat sinks."
)
DESCRIPTION_UNKNOWN = "There is a problem with your power supply or system."
DESCRIPTIONS = {
    "0": DESCRIPTION_WORKING,
    "1000": DESCRIPTION_UNDER_VOLTAGE,
    "2000": DESCRIPTION_LIMITED,
    "3000": DESCRIPTION_LIMITED,
    "4000": DESCRIPTION_THROTTLED,
    "5000": DESCRIPTION_THROTTLED,
    "8000": DESCRIPTION_OVERHEATING,
}


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the sensor platform."""

    exist = os.path.isfile(SYSFILE)
    if exist:
        add_entities([RaspberryChargerBinarySensor()], True)
    else:
        _LOGGER.critical(
            "Can't find the system class needed for this component, make sure that your kernel is recent and the hardware is supported."
        )


class RaspberryChargerBinarySensor(BinarySensorEntity):
    """Binary sensor representing the rpi power status."""

    def __init__(self):
        """Initialize the binary sensor."""
        self._state = None
        self._last_state = (
            "0"  # Assume no problem to avoid log at startup without problem
        )
        self._is_on = None
        self._description = None

    def update(self):
        """Update the state."""
        throttled = open(SYSFILE).read()[:-1]
        throttled = throttled[:4]
        self._state = throttled
        self._is_on = self._state != "0"
        try:
            self._description = DESCRIPTIONS[self._state]
        except KeyError:
            self._description = DESCRIPTION_UNKNOWN

        # Log the problem when state changed
        if self._state != self._last_state:
            _LOGGER.warning(self._description)
            self._last_state = self._state

    @property
    def name(self):
        """Return the name of the sensor."""
        return "RPi Power status"

    @property
    def is_on(self):
        """Return if there is a problem detected."""
        return self._is_on

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return "mdi:raspberry-pi"

    @property
    def device_state_attributes(self):
        """Return the attribute(s) of the sensor."""
        return {
            "state": self._state,
            "description": self._description,
        }

    @property
    def device_class(self):
        """Return the class of this device."""
        return DEVICE_CLASS_PROBLEM

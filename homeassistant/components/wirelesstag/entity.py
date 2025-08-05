"""Support for Wireless Sensor Tags."""

import logging

from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    ATTR_VOLTAGE,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfElectricPotential,
)
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)


# Strength of signal in dBm
ATTR_TAG_SIGNAL_STRENGTH = "signal_strength"
# Indicates if tag is out of range or not
ATTR_TAG_OUT_OF_RANGE = "out_of_range"
# Number in percents from max power of tag receiver
ATTR_TAG_POWER_CONSUMPTION = "power_consumption"


class WirelessTagBaseSensor(Entity):
    """Base class for HA implementation for Wireless Sensor Tag."""

    def __init__(self, api, tag):
        """Initialize a base sensor for Wireless Sensor Tag platform."""
        self._api = api
        self._tag = tag
        self._uuid = self._tag.uuid
        self.tag_id = self._tag.tag_id
        self.tag_manager_mac = self._tag.tag_manager_mac
        self._name = self._tag.name
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def principal_value(self):
        """Return base value.

        Subclasses need override based on type of sensor.
        """
        return 0

    def updated_state_value(self):
        """Return formatted value.

        The default implementation formats principal value.
        """
        return self.decorate_value(self.principal_value)

    def decorate_value(self, value):
        """Decorate input value to be well presented for end user."""
        return f"{value:.1f}"

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._tag.is_alive

    def update(self) -> None:
        """Update state."""
        if not self.should_poll:
            return

        updated_tags = self._api.load_tags()
        if (updated_tag := updated_tags[self._uuid]) is None:
            _LOGGER.error('Unable to update tag: "%s"', self.name)
            return

        self._tag = updated_tag
        self._state = self.updated_state_value()

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_BATTERY_LEVEL: int(self._tag.battery_remaining * 100),
            ATTR_VOLTAGE: (
                f"{self._tag.battery_volts:.2f}{UnitOfElectricPotential.VOLT}"
            ),
            ATTR_TAG_SIGNAL_STRENGTH: (
                f"{self._tag.signal_strength}{SIGNAL_STRENGTH_DECIBELS_MILLIWATT}"
            ),
            ATTR_TAG_OUT_OF_RANGE: not self._tag.is_in_range,
            ATTR_TAG_POWER_CONSUMPTION: (
                f"{self._tag.power_consumption:.2f}{PERCENTAGE}"
            ),
        }

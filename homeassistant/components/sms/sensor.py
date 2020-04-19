"""Support for SMS dongle sensor."""
import logging

import gammu  # pylint: disable=import-error, no-member
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, DEVICE_CLASS_SIGNAL_STRENGTH
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "GSM Signal"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string}
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the GSM Signal Sensor sensor."""
    name = config.get(CONF_NAME)
    gateway = hass.data[DOMAIN]
    add_entities(
        [GSMSignalSensor(hass, gateway, name,)], True,
    )


class GSMSignalSensor(Entity):
    """Implementation of a GSM Signal sensor."""

    def __init__(
        self, hass, gateway, name,
    ):
        """Initialize the GSM Signal sensor."""
        self._hass = hass
        self._gateway = gateway
        self._name = name
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return "dB"

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return DEVICE_CLASS_SIGNAL_STRENGTH

    @property
    def available(self):
        """Return if the sensor data are available."""
        return self._state is not None

    @property
    def state(self):
        """Return the state of the device."""
        return self._state["SignalStrength"]

    @property
    def force_update(self):
        """Force update."""
        try:
            self._state = self._gateway.GetSignalQuality()
        except gammu.GSMError as exc:  # pylint: disable=no-member
            _LOGGER.error("Failed to read signal quality: %s", exc)

    def update(self):
        """Get the latest data from the modem."""
        try:
            self._state = self._gateway.GetSignalQuality()
        except gammu.GSMError as exc:  # pylint: disable=no-member
            _LOGGER.error("Failed to read signal quality: %s", exc)

    @property
    def device_state_attributes(self):
        """Return the sensor attributes."""
        return self._state

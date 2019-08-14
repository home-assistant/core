"""
Platform that has ais binary sensors.
"""
from homeassistant.components.binary_sensor import BinarySensorDevice


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the AIS binary sensor platform."""
    add_devices([
        AisMicSensor('ais_remote_mic_test', False, 'sound'),
        AisButonSensor('ais_remote_button_test', True, 'sound'),
    ])


class AisMicSensor(BinarySensorDevice):
    """representation of a Microphone binary sensor."""

    def __init__(self, name, state, device_class):
        """Initialize the microphone sensor."""
        self._name = name
        self._state = state
        self._sensor_type = device_class

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return self._sensor_type

    @property
    def should_poll(self):
        """No polling needed for a demo binary sensor."""
        return False

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return self._name

    @property
    def icon(self):
        """Return the icon of the binary sensor."""
        # microphone-off
        # return 'mdi:text-to-speech-off'
        return 'mdi:microphone'

    @property
    def friendly_name(self):
        """Return the friendly_name of the binary sensor."""
        return 'Mikrofon w pilocie'

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._state


class AisButonSensor(BinarySensorDevice):
    """representation of a Button sensor."""

    def __init__(self, name, state, device_class):
        """Initialize the microphone sensor."""
        self._name = name
        self._state = state
        self._sensor_type = device_class

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return self._sensor_type

    @property
    def should_poll(self):
        """No polling needed for a demo binary sensor."""
        return False

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return self._name

    @property
    def icon(self):
        """Return the icon of the binary sensor."""
        # microphone-off
        # return 'mdi:text-to-speech-off'
        return 'mdi:microphone'

    @property
    def friendly_name(self):
        """Return the friendly_name of the binary sensor."""
        return 'Mikrofon w pilocie'

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._state

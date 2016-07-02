"""Support for monitoring energy usage using the DTE energy bridge."""
import logging

from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

ICON = 'mdi:flash'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the DTE energy bridge sensor."""
    ip_address = config.get('ip')
    if not ip_address:
        _LOGGER.error(
            "Configuration Error"
            "'ip' of the DTE energy bridge is required")
        return None
    dev = [DteEnergyBridgeSensor(ip_address)]
    add_devices(dev)


# pylint: disable=too-many-instance-attributes
class DteEnergyBridgeSensor(Entity):
    """Implementation of an DTE Energy Bridge sensor."""

    def __init__(self, ip_address):
        """Initialize the sensor."""
        self._url = "http://{}/instantaneousdemand".format(ip_address)
        self._name = "Current Energy Usage"
        self._unit_of_measurement = "kW"
        self._state = None

    @property
    def name(self):
        """Return the name of th sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    def update(self):
        """Get the energy usage data from the DTE energy bridge."""
        import requests

        try:
            response = requests.get(self._url, timeout=5)
        except (requests.exceptions.RequestException, ValueError):
            _LOGGER.warning(
                'Could not update status for DTE Energy Bridge (%s)',
                self._name)
            return

        if response.status_code != 200:
            _LOGGER.warning(
                'Invalid status_code from DTE Energy Bridge: %s (%s)',
                response.status_code, self._name)
            return

        response_split = response.text.split()

        if len(response_split) != 2:
            _LOGGER.warning(
                'Invalid response from DTE Energy Bridge: "%s" (%s)',
                response.text, self._name)
            return

        self._state = float(response_split[0])

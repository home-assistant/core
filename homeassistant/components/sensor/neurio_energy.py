"""
Support for monitoring  an neurio hub.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.neurio_energy/
"""
import logging

import requests.exceptions

from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['neurio==0.2.10']

_LOGGER = logging.getLogger(__name__)

ICON = 'mdi:flash'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Neurio sensor."""
    api_key = config.get("api_key")
    api_secret = config.get("api_secret")
    sensor_id = config.get("sensor_id")
    if not api_key and not api_secret:
        _LOGGER.error(
            "Configuration Error"
            "Please make sure you have configured your api key and api secret")
        return None
    if not sensor_id:
        import neurio
        neurio_tp = neurio.TokenProvider(key=api_key, secret=api_secret)
        neurio_client = neurio.Client(token_provider=neurio_tp)
        user_info = neurio_client.get_user_information()
        _LOGGER.warning('Sensor ID auto-detected, set api_sensor_id: "%s"',
                        user_info["locations"][0]["sensors"][0]["sensorId"])
        sensor_id = user_info["locations"][0]["sensors"][0]["sensorId"]
    dev = []
    dev.append(NeurioEnergy(api_key, api_secret, sensor_id))
    add_devices(dev)


# pylint: disable=too-many-instance-attributes
class NeurioEnergy(Entity):
    """Implementation of an Neurio energy."""

    # pylint: disable=too-many-arguments
    def __init__(self, api_key, api_secret, sensor_id):
        """Initialize the sensor."""
        self._name = "Energy Usage"
        self.api_key = api_key
        self.api_secret = api_secret
        self.sensor_id = sensor_id
        self._state = None
        self._unit_of_measurement = "W"

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
        """Get the Neurio monitor data from the web service."""
        import neurio
        try:
            neurio_tp = neurio.TokenProvider(key=self.api_key,
                                             secret=self.api_secret)
            neurio_client = neurio.Client(token_provider=neurio_tp)
            sample = neurio_client.get_samples_live_last(
                sensor_id=self.sensor_id)
            self._state = sample['consumptionPower']
        except (requests.exceptions.RequestException, ValueError):
            _LOGGER.warning('Could not update status for %s', self.name)

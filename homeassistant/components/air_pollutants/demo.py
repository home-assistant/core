"""
Demo platform that offers fake air pollutants data.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/demo/
"""
from homeassistant.components.air_pollutants import AirPollutantsEntity
from homeassistant.const import (TEMP_CELSIUS, TEMP_FAHRENHEIT, CONF_H)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Air Pollutants."""
    add_entities([
        DemoAirPollutants('Home', 14, 23, 100, 12, TEMP_CELSIUS),
        DemoAirPollutants('Office', 4, 16, None, 4.8, TEMP_FAHRENHEIT)
    ])


class DemoAirPollutants(AirPollutantsEntity):
    """Representation of Air Pollutants data."""

    def __init__(self, name, pm_2_5, pm_10, n2o, temp, temperature_unit):
        """Initialize the Demo Air Pollutants."""
        self._name = name
        self._pm_2_5 = pm_2_5
        self._pm_10 = pm_10
        self._n2o = n2o
        self._temperature_unit = temperature_unit
        self._temperature = temp

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {}'.format('Demo Air Pollutants', self._name)

    @property
    def should_poll(self):
        """No polling needed for Demo Air Pollutants."""
        return False

    @property
    def temperature(self):
        """Return the temperature."""
        return self._temperature

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._temperature_unit

    @property
    def particulate_matter_2_5(self):
        """Return the particulate matter 2.5 level."""
        return self._pm_2_5

    @property
    def particulate_matter_10(self):
        """Return the particulate matter 10 level."""
        return self._pm_10

    @property
    def nitrogen_oxide(self):
        """Return the nitrogen oxide (N2O) level."""
        return self._n2o

    @property
    def attribution(self):
        """Return the attribution."""
        return 'Powered by Home Assistant'

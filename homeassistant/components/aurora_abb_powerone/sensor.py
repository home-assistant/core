"""Support for Aurora ABB PowerOne Solar Photvoltaic (PV) inverter."""

import logging
import voluptuous as vol

from aurorapy.client import AuroraSerialClient

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_ADDRESS, CONF_NAME, DEVICE_CLASS_POWER, POWER_WATT)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

CONF_COMPORT = 'rs485'
DEFAULT_ADDRESS = 2
TEST_MODE = False                      # For testing code when no sunlight.

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_COMPORT): cv.string,
    vol.Optional(CONF_ADDRESS, default=DEFAULT_ADDRESS): cv.positive_int,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Aurora ABB PowerOne device."""
    devices = []
    _LOGGER.debug("Setting up AuroraABBPowerone")
    comport = config.get(CONF_COMPORT)
    name = config.get(CONF_NAME, "Solar PV")
    address = config.get(CONF_ADDRESS, 1)

    _LOGGER.debug("Intitialising com port=%s address=%s", comport, address)
    client = AuroraSerialClient(address, comport, parity='N', timeout=1)

    devices.append(AuroraABBSolarPVMonitorSensor(client, name, 'Power'))
    add_devices(devices, True)


class AuroraABBSolarPVMonitorSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, client, name, typename):
        """Initialize the sensor."""
        self._name = name + " " + typename
        self.client = client
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return POWER_WATT

    @property
    def device_class(self):
        """Return the device class."""
        return DEVICE_CLASS_POWER

    def update(self):
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        from aurorapy.client import AuroraError

        try:
            if TEST_MODE:    # For testing the code at night
                import random
                power_watts = random.randint(1, 3601)
            else:
                self.client.connect()
                # Read ADC channel 3 (grid power output)
                power_watts = self.client.measure(3, True)
                self.client.close()
            self._state = round(power_watts, 1)
            # _LOGGER.debug("Got reading %fW" % self._state)
        except AuroraError as error:
            # aurorapy does not have different exceptions (yet) for dealing
            # with timeout vs other comms errors.
            # This means the (normal) situation of no response during darkness
            # raises an exception.
            # aurorapy (gitlab) pull request merged 29/5/2019. When >0.2.6 is
            # released, this could be modified to :
            # except AuroraTimeoutError as e:
            # Workaround: look at the text of the exception
            if "No response after" in str(error):
                _LOGGER.debug("No response from inverter (could be dark)")
            else:
                # print("Exception!!: {}".format(str(e)))
                raise error
            self._state = None
        finally:
            if self.client.serline.isOpen():
                self.client.close()

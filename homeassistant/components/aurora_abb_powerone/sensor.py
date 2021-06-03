"""Support for Aurora ABB PowerOne Solar Photvoltaic (PV) inverter."""

import logging

from aurorapy.client import AuroraError, AuroraSerialClient
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_DEVICE,
    CONF_NAME,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_TEMPERATURE,
    POWER_WATT,
    TEMP_CELSIUS,
)
from homeassistant.exceptions import InvalidStateError
import homeassistant.helpers.config_validation as cv

from .aurora_device import AuroraDevice
from .const import (
    ATTR_DEVICE_NAME,
    ATTR_FIRMWARE,
    ATTR_MODEL,
    ATTR_SERIAL_NUMBER,
    DEFAULT_ADDRESS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_DEVICE): cv.string,
        vol.Optional(CONF_ADDRESS, default=DEFAULT_ADDRESS): cv.positive_int,
        vol.Optional(CONF_NAME, default="Solar PV"): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up single sensor based on configuration.yaml (DEPRECATED)."""
    devices = []
    comport = config[CONF_DEVICE]
    address = config.get(CONF_ADDRESS, DEFAULT_ADDRESS)
    name = config.get(CONF_NAME, "Solar PV")
    _LOGGER.warning(
        "DEPRECATED: setting up %s via configuration.yaml will "
        "soon be unsupported.  Please remove the entries from your "
        "configuration.yaml file and then set up the integration via the UI",
        DOMAIN,
    )
    _LOGGER.debug("Intitialising com port=%s address=%s", comport, address)
    client = AuroraSerialClient(address, comport, parity="N", timeout=1)

    data = {
        ATTR_DEVICE_NAME: name,
        ATTR_SERIAL_NUMBER: None,
        ATTR_FIRMWARE: None,
        ATTR_MODEL: None,
    }
    devices.append(AuroraSensor(client, data, "Power Output", "instantaneouspower"))
    add_entities(devices, True)


async def async_setup_entry(hass, config_entry, async_add_entities) -> None:
    """Set up aurora_abb_powerone sensor based on a config entry."""
    entities = []

    sensortypes = [
        {"parameter": "instantaneouspower", "name": "Power Output"},
        {"parameter": "temperature", "name": "Temperature"},
    ]
    client = hass.data[DOMAIN][config_entry.unique_id]
    data = config_entry.data

    for sens in sensortypes:
        entities.append(AuroraSensor(client, data, sens["name"], sens["parameter"]))

    _LOGGER.debug("async_setup_entry adding %d entities", len(entities))
    async_add_entities(entities, True)


class AuroraSensor(AuroraDevice):
    """Representation of a Sensor on a Aurora ABB PowerOne Solar inverter."""

    availableprev = True

    def __init__(self, client: AuroraSerialClient, data, name, typename):
        """Initialize the sensor."""
        self._state = None
        super().__init__(client, data)

        if typename == "instantaneouspower":
            self.type = typename
            self.units = POWER_WATT
            self._device_class = DEVICE_CLASS_POWER
        elif typename == "temperature":
            self.type = typename
            self.units = TEMP_CELSIUS
            self._device_class = DEVICE_CLASS_TEMPERATURE
        else:
            raise InvalidStateError(f"Unrecognised typename '{typename}'")
        self._name = f"{name}"

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
        return self.units

    @property
    def device_class(self):
        """Return the device class."""
        return self._device_class

    @property
    def available(self):
        """Return True if entity is available."""
        return self._state is not None

    def update(self):
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        try:
            availableprev = self.available
            self.client.connect()
            if self.type == "instantaneouspower":
                # read ADC channel 3 (grid power output)
                power_watts = self.client.measure(3, True)
                self._state = round(power_watts, 1)
            elif self.type == "temperature":
                temperature_c = self.client.measure(21)
                self._state = round(temperature_c, 1)
        except AuroraError as error:
            self._state = None
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
                raise error
        finally:
            if self.available != availableprev:
                if self.available:
                    _LOGGER.info("Communication with %s back online", self._name)
                else:
                    _LOGGER.warning(
                        "Communication with %s lost",
                        self._name,
                    )
            if self.client.serline.isOpen():
                self.client.close()

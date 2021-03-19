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
import homeassistant.helpers.config_validation as cv

from .aurora_device import AuroraDevice
from .const import ATTR_SERIAL_NUMBER, DEFAULT_ADDRESS, DOMAIN

_LOGGER = logging.getLogger(__name__)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_DEVICE): cv.string,
        vol.Optional(CONF_ADDRESS, default=DEFAULT_ADDRESS): cv.positive_int,
        vol.Optional(CONF_NAME, default="Solar PV"): cv.string,
    }
)


def setup_platform(hass, config: dict, add_entities, discovery_info=None):
    """Set up single sensor based on configuration.yaml (DEPRECATED)."""
    devices = []
    comport = config[CONF_DEVICE]
    address = config.get(CONF_ADDRESS, DEFAULT_ADDRESS)
    name = config.get(CONF_NAME, "Solar PV")
    _LOGGER.warning(
        "DEPRECATED: setting up %s via configuration.yaml will "
        "soon be unsupported.  Please remove the entries from your "
        "configuration.yaml file and the set up the integration via the UI",
        DOMAIN,
    )
    _LOGGER.debug("Intitialising com port=%s address=%s", comport, address)
    client = AuroraSerialClient(address, comport, parity="N", timeout=1)

    config.data = {"device_name": name}
    config.entry_id = "undefined_entry_id"
    devices.append(AuroraSensor(client, config, "Power", "instantaneouspower"))
    add_entities(devices, True)


async def async_setup_entry(hass, config, async_add_entities) -> None:
    """Set up aurora_abb_powerone sensor based on a config entry."""
    entities = []
    client = hass.data[DOMAIN][config.entry_id]["client"]
    serialnum = config.data[ATTR_SERIAL_NUMBER]
    for sensor in hass.data[DOMAIN][config.entry_id]["devices"][serialnum]["sensor"]:
        if sensor["parameter"] == "temperature":
            entities.append(AuroraSensor(client, config, sensor["name"], "temperature"))
        elif sensor["parameter"] == "instantaneouspower":
            entities.append(
                AuroraSensor(client, config, sensor["name"], "instantaneouspower")
            )
        else:
            _LOGGER.error("Unrecognised sensor parameter '%s'", sensor["parameter"])
    _LOGGER.debug("async_setup_entry adding %d entities", len(entities))
    async_add_entities(entities, True)


class AuroraSensor(AuroraDevice):
    """Representation of a Sensor on a Aurora ABB PowerOne Solar inverter."""

    availableprev = True

    def __init__(self, client: AuroraSerialClient, config_entry, name, typename):
        """Initialize the sensor."""
        self._state = None
        super().__init__(client, config_entry)

        if typename == "instantaneouspower":
            self.type = typename
            self.units = POWER_WATT
            self._device_class = DEVICE_CLASS_POWER
        elif typename == "temperature":
            self.type = typename
            self.units = TEMP_CELSIUS
            self._device_class = DEVICE_CLASS_TEMPERATURE
        else:
            _LOGGER.warning("Unrecognised typename '%s'", typename)
        if self.type:
            self._name = f"{self.device_name} {name}"

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Get a unique ID for this device."""
        return f"{self.serialnum}_{self.type}"

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

    def update(self):
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        try:
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
            self._available = bool(self._state is not None)
            if self._available != self.availableprev:
                if self._available:
                    _LOGGER.info("Communication with %s back online", self._name)
                else:
                    _LOGGER.warning(
                        "Communication with %s lost",
                        self._name,
                    )
            self.availableprev = self._available
            if self.client.serline.isOpen():
                self.client.close()

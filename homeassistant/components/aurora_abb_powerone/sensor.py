"""Support for Aurora ABB PowerOne Solar Photvoltaic (PV) inverter."""

import logging

from aurorapy.client import AuroraError, AuroraSerialClient

from .aurora_device import AuroraDevice
from .const import DOMAIN

from homeassistant.const import (  # CONF_ADDRESS,; CONF_DEVICE,; CONF_NAME,
    DEVICE_CLASS_POWER,
    POWER_WATT,
    TEMP_CELSIUS,
)


# import voluptuous as vol


# import homeassistant.helpers.config_validation as cv


# from .const import DOMAIN, DEFAULT_ADDRESS, DEFAULT_NAME


_LOGGER = logging.getLogger(__name__)

# PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
#     {
#         vol.Required(CONF_DEVICE): cv.string,
#         vol.Optional(CONF_ADDRESS, default=DEFAULT_ADDRESS): cv.positive_int,
#         vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
#     }
# )


async def async_setup_entry(hass, config, async_add_entities) -> None:
    """Set up aurora_abb_powerone sensor based on a config entry."""
    print(f"async setup entry={config}")
    entities = []
    client = hass.data[DOMAIN][config.entry_id]["client"]

    # sensor.type = instantaneouspower, temperature, etc.
    for sensor in hass.data[DOMAIN][config.entry_id]["devices"]["sensor"]:
        print(f"sensor = {sensor}")
        if sensor["parameter"] == "temperature":
            entities.append(AuroraSensor(sensor, client, config, "temperature"))
        elif sensor["parameter"] == "instantaneouspower":
            entities.append(AuroraSensor(sensor, client, config, "instantaneouspower"))
        else:
            _LOGGER.error(f"Unrecognised sensor parameter '{sensor['parameter']}''")
    print(f"adding {len(entities)} entities")
    async_add_entities(entities, True)


# def setup_platform(hass, config, add_entities, discovery_info=None):
#     """Set up the Aurora ABB PowerOne device."""
#     print("sync setup entry={}".format(config))
#     entities = []
#     comport = config[CONF_DEVICE]
#     address = config[CONF_ADDRESS]
#     name = config[CONF_NAME]

#     _LOGGER.debug("Intitialising com port=%s address=%s", comport, address)
#     client = AuroraSerialClient(address, comport, parity="N", timeout=1)
#     for device in hass.data[AURORA_DOMAIN][config_entry.entry_id]["devices"]["sensor"]:
#         if device.type == "temperature":
#             entities.append(AuroraSensor(device, client, config, "temperature"))
#         elif device.type == "instantaneouspower":
#             entities.append(AuroraSensor(device, client, config, "instantaneouspower"))
#     add_entities(entities, True)


class AuroraSensor(AuroraDevice):
    """Representation of a Sensor."""

    def __init__(
        self, device_params, client: AuroraSerialClient, config_entry, typename
    ):
        """Initialize the sensor."""
        self._state = None
        if typename == "instantaneouspower":
            self.type = typename
            self.units = POWER_WATT
        elif typename == "temperature":
            self.type = typename
            self.units = TEMP_CELSIUS
        super().__init__(device_params, client, config_entry)

        if self.type:
            self._name = f"Aurora ABB PV Inverter {device_params['name']}"

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
        return DEVICE_CLASS_POWER

    # async io update not supported yet.
    #
    # async def async_update(self):
    #     _LOGGER.debug("Updating sensor (async): %s", self._name)
    #     try:
    #         await self.client.connect()
    #         if self.type == "instantaneouspower":
    #             # read ADC channel 3 (grid power output)
    #             power_watts = await self.client.measure(3, True)
    #             self._state = round(power_watts, 1)
    #         elif self.type == "temperature":
    #             temperature_c = await self.client.measure(21)
    #             self._state = round(power_watts, 1)
    #     except AuroraError as error:
    #         # aurorapy does not have different exceptions (yet) for dealing
    #         # with timeout vs other comms errors.
    #         # This means the (normal) situation of no response during darkness
    #         # raises an exception.
    #         # aurorapy (gitlab) pull request merged 29/5/2019. When >0.2.6 is
    #         # released, this could be modified to :
    #         # except AuroraTimeoutError as e:
    #         # Workaround: look at the text of the exception
    #         if "No response after" in str(error):
    #             _LOGGER.debug("No response from inverter (could be dark)")
    #         else:
    #             # print("Exception!!: {}".format(str(e)))
    #             raise error
    #         self._state = None
    #     finally:
    #         if self.client.serline.isOpen():
    #             await self.client.close()

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
            self._attr_state = None
        finally:
            if self.client.serline.isOpen():
                self.client.close()

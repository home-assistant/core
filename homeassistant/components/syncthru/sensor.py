"""Support for Samsung Printers with SyncThru web interface."""

import logging

from pysyncthru import SyncThru
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_RESOURCE, UNIT_PERCENTAGE
from homeassistant.helpers import aiohttp_client
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Samsung Printer"
COLORS = ["black", "cyan", "magenta", "yellow"]
DRUM_COLORS = COLORS
TONER_COLORS = COLORS
TRAYS = range(1, 6)
OUTPUT_TRAYS = range(0, 6)
DEFAULT_MONITORED_CONDITIONS = []
DEFAULT_MONITORED_CONDITIONS.extend([f"toner_{key}" for key in TONER_COLORS])
DEFAULT_MONITORED_CONDITIONS.extend([f"drum_{key}" for key in DRUM_COLORS])
DEFAULT_MONITORED_CONDITIONS.extend([f"tray_{key}" for key in TRAYS])
DEFAULT_MONITORED_CONDITIONS.extend([f"output_tray_{key}" for key in OUTPUT_TRAYS])

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_RESOURCE): cv.url,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the SyncThru component."""

    if discovery_info is not None:
        _LOGGER.info(
            "Discovered a new Samsung Printer at %s", discovery_info.get(CONF_HOST)
        )
        host = discovery_info.get(CONF_HOST)
        name = discovery_info.get(CONF_NAME, DEFAULT_NAME)
        # Main device, always added
    else:
        host = config.get(CONF_RESOURCE)
        name = config.get(CONF_NAME)
    # always pass through all of the obtained information
    monitored = DEFAULT_MONITORED_CONDITIONS

    session = aiohttp_client.async_get_clientsession(hass)

    printer = SyncThru(host, session)
    # Test if the discovered device actually is a syncthru printer
    # and fetch the available toner/drum/etc
    try:
        # No error is thrown when the device is off
        # (only after user added it manually)
        # therefore additional catches are inside the Sensor below
        await printer.update()
        supp_toner = printer.toner_status(filter_supported=True)
        supp_drum = printer.drum_status(filter_supported=True)
        supp_tray = printer.input_tray_status(filter_supported=True)
        supp_output_tray = printer.output_tray_status()
    except ValueError:
        # if an exception is thrown, printer does not support syncthru
        # and should not be set up
        # If the printer was discovered automatically, no warning or error
        # should be issued and printer should not be set up
        if discovery_info is not None:
            _LOGGER.info("Samsung printer at %s does not support SyncThru", host)
            return
        # Otherwise, emulate printer that supports everything
        supp_toner = TONER_COLORS
        supp_drum = DRUM_COLORS
        supp_tray = TRAYS
        supp_output_tray = OUTPUT_TRAYS

    devices = [SyncThruMainSensor(printer, name)]

    for key in supp_toner:
        if f"toner_{key}" in monitored:
            devices.append(SyncThruTonerSensor(printer, name, key))
    for key in supp_drum:
        if f"drum_{key}" in monitored:
            devices.append(SyncThruDrumSensor(printer, name, key))
    for key in supp_tray:
        if f"tray_{key}" in monitored:
            devices.append(SyncThruInputTraySensor(printer, name, key))
    for key in supp_output_tray:
        if f"output_tray_{key}" in monitored:
            devices.append(SyncThruOutputTraySensor(printer, name, key))

    async_add_entities(devices, True)


class SyncThruSensor(Entity):
    """Implementation of an abstract Samsung Printer sensor platform."""

    def __init__(self, syncthru, name):
        """Initialize the sensor."""
        self.syncthru = syncthru
        self._attributes = {}
        self._state = None
        self._name = name
        self._icon = "mdi:printer"
        self._unit_of_measurement = None
        self._id_suffix = ""

    @property
    def unique_id(self):
        """Return unique ID for the sensor."""
        serial = self.syncthru.serial_number()
        return serial + self._id_suffix if serial else super().unique_id

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def icon(self):
        """Return the icon of the device."""
        return self._icon

    @property
    def unit_of_measurement(self):
        """Return the unit of measuremnt."""
        return self._unit_of_measurement

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return self._attributes


class SyncThruMainSensor(SyncThruSensor):
    """Implementation of the main sensor, conducting the actual polling."""

    def __init__(self, syncthru, name):
        """Initialize the sensor."""
        super().__init__(syncthru, name)
        self._id_suffix = "_main"
        self._active = True

    async def async_update(self):
        """Get the latest data from SyncThru and update the state."""
        if not self._active:
            return
        try:
            await self.syncthru.update()
        except ValueError:
            # if an exception is thrown, printer does not support syncthru
            _LOGGER.warning(
                "Configured printer at %s does not support SyncThru. "
                "Consider changing your configuration",
                self.syncthru.url,
            )
            self._active = False
        self._state = self.syncthru.device_status()


class SyncThruTonerSensor(SyncThruSensor):
    """Implementation of a Samsung Printer toner sensor platform."""

    def __init__(self, syncthru, name, color):
        """Initialize the sensor."""
        super().__init__(syncthru, name)
        self._name = f"{name} Toner {color}"
        self._color = color
        self._unit_of_measurement = UNIT_PERCENTAGE
        self._id_suffix = f"_toner_{color}"

    def update(self):
        """Get the latest data from SyncThru and update the state."""
        # Data fetching is taken care of through the Main sensor

        if self.syncthru.is_online():
            self._attributes = self.syncthru.toner_status().get(self._color, {})
            self._state = self._attributes.get("remaining")


class SyncThruDrumSensor(SyncThruSensor):
    """Implementation of a Samsung Printer toner sensor platform."""

    def __init__(self, syncthru, name, color):
        """Initialize the sensor."""
        super().__init__(syncthru, name)
        self._name = f"{name} Drum {color}"
        self._color = color
        self._unit_of_measurement = UNIT_PERCENTAGE
        self._id_suffix = f"_drum_{color}"

    def update(self):
        """Get the latest data from SyncThru and update the state."""
        # Data fetching is taken care of through the Main sensor

        if self.syncthru.is_online():
            self._attributes = self.syncthru.drum_status().get(self._color, {})
            self._state = self._attributes.get("remaining")


class SyncThruInputTraySensor(SyncThruSensor):
    """Implementation of a Samsung Printer input tray sensor platform."""

    def __init__(self, syncthru, name, number):
        """Initialize the sensor."""
        super().__init__(syncthru, name)
        self._name = f"{name} Tray {number}"
        self._number = number
        self._id_suffix = f"_tray_{number}"

    def update(self):
        """Get the latest data from SyncThru and update the state."""
        # Data fetching is taken care of through the Main sensor

        if self.syncthru.is_online():
            self._attributes = self.syncthru.input_tray_status().get(self._number, {})
            self._state = self._attributes.get("newError")
            if self._state == "":
                self._state = "Ready"


class SyncThruOutputTraySensor(SyncThruSensor):
    """Implementation of a Samsung Printer input tray sensor platform."""

    def __init__(self, syncthru, name, number):
        """Initialize the sensor."""
        super().__init__(syncthru, name)
        self._name = f"{name} Output Tray {number}"
        self._number = number
        self._id_suffix = f"_output_tray_{number}"

    def update(self):
        """Get the latest data from SyncThru and update the state."""
        # Data fetching is taken care of through the Main sensor

        if self.syncthru.is_online():
            self._attributes = self.syncthru.output_tray_status().get(self._number, {})
            self._state = self._attributes.get("status")
            if self._state == "":
                self._state = "Ready"

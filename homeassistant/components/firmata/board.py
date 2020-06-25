"""Code to handle a Firmata board."""
import logging

from pymata_express.pymata_express import PymataExpress

from homeassistant.const import CONF_NAME
from homeassistant.helpers.entity import Entity

from .const import (
    CONF_ARDUINO_INSTANCE_ID,
    CONF_ARDUINO_WAIT,
    CONF_BINARY_SENSORS,
    CONF_PIN,
    CONF_PIN_MODE,
    CONF_SAMPLING_INTERVAL,
    CONF_SERIAL_BAUD_RATE,
    CONF_SERIAL_PORT,
    CONF_SLEEP_TUNE,
    CONF_SWITCHES,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class FirmataBoard:
    """Manages a single Firmata board."""

    def __init__(self, hass, config_entry):
        """Initialize the board."""
        self.config_entry = config_entry
        self.config = self.config_entry.data
        self.hass = hass
        self.available = True
        self.api = None
        self.firmware_version = None
        self.protocol_version = None
        self.name = self.config[CONF_NAME]
        self.switches = []
        self.binary_sensors = []
        self.used_pins = []

    async def async_setup(self, tries=0):
        """Set up a Firmata instance."""
        try:
            _LOGGER.info("Connecting to Firmata %s", self.name)
            self.api = await get_board(self.config)
            self.firmware_version = await self.api.get_firmware_version()
        except RuntimeError as err:
            _LOGGER.error("Error connecting to PyMata board %s: %s", self.name, err)
            return False

        if CONF_SAMPLING_INTERVAL in self.config:
            try:
                await self.api.set_sampling_interval(
                    self.config[CONF_SAMPLING_INTERVAL]
                )
            except RuntimeError as err:
                _LOGGER.error(
                    "Error setting sampling interval for PyMata \
board %s: %s",
                    self.name,
                    err,
                )
                return False

        if CONF_SWITCHES in self.config:
            self.switches = self.config[CONF_SWITCHES]
        if CONF_BINARY_SENSORS in self.config:
            self.binary_sensors = self.config[CONF_BINARY_SENSORS]

        _LOGGER.info("Firmata connection successful for %s", self.name)
        return True

    async def async_reset(self):
        """Reset the board to default state."""
        _LOGGER.debug("Shutting down board %s", self.name)
        # If the board was never setup, continue.
        if self.api is None:
            return True

        await self.api.shutdown()
        self.api = None

        return True

    async def async_update_device_registry(self):
        """Update board registry."""
        device_registry = await self.hass.helpers.device_registry.async_get_registry()
        device_registry.async_get_or_create(
            config_entry_id=self.config_entry.entry_id,
            connections={},
            identifiers={(DOMAIN, self.name)},
            manufacturer="Firmata",
            name=self.name,
            sw_version=self.firmware_version,
        )


async def get_board(data: dict):
    """Create a Pymata board object."""
    board_data = {}

    if CONF_SERIAL_PORT in data:
        board_data["com_port"] = data[CONF_SERIAL_PORT]
    if CONF_SERIAL_BAUD_RATE in data:
        board_data["baud_rate"] = data[CONF_SERIAL_BAUD_RATE]
    if CONF_ARDUINO_INSTANCE_ID in data:
        board_data["arduino_instance_id"] = data[CONF_ARDUINO_INSTANCE_ID]

    if CONF_ARDUINO_WAIT in data:
        board_data["arduino_wait"] = data[CONF_ARDUINO_WAIT]
    if CONF_SLEEP_TUNE in data:
        board_data["sleep_tune"] = data[CONF_SLEEP_TUNE]

    board_data["autostart"] = False
    board_data["shutdown_on_exception"] = True
    board_data["close_loop_on_shutdown"] = False

    board = PymataExpress(**board_data)

    await board.start_aio()
    return board


class FirmataBoardPin(Entity):
    """Manages a single Firmata board pin."""

    def __init__(self, hass, config_entry, **kwargs):
        """Initialize the pin."""
        self.hass = hass
        self._name = kwargs[CONF_NAME]
        self._state = None
        self._config_entry = config_entry
        self._board = hass.data[DOMAIN][self._config_entry.entry_id]
        self._board_name = self._board.name
        self._conf = kwargs
        self._pin = self._conf[CONF_PIN]
        self._pin_mode = self._conf[CONF_PIN_MODE]
        self._firmata_pin_mode = None
        self._firmata_pin = self._pin
        if isinstance(self._pin, str):
            self._pin_type = "analog"
            self._firmata_pin = int(self._firmata_pin[1:])
            self._firmata_pin += self._board.api.first_analog_pin
        else:
            self._pin_type = "digital"
        self._location = (DOMAIN, self._config_entry.entry_id, "pin", self._pin)
        self._unique_id = "_".join(str(i) for i in self._location)
        self._device_info = self._conf
        self._device_info.update(
            {
                "config_entry_id": self._config_entry.entry_id,
                "identifiers": {(DOMAIN, self._config_entry.entry_id)},
                "name": self._board_name,
                "manufacturer": "Firmata",
            }
        )

    def _mark_pin_used(self):
        """Test if a pin is used already on the board or mark as used."""
        if self._location in self._board.used_pins:
            return False
        self._board.used_pins.append(self._location)
        return True

    @property
    def name(self) -> str:
        """Get the name of the pin."""
        return self._name

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    @property
    def unique_id(self):
        """Return a unique identifier for this device."""
        return self._unique_id

    @property
    def device_info(self) -> dict:
        """Return device info."""
        return self._device_info

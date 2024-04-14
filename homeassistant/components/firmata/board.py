"""Code to handle a Firmata board."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Literal

from pymata_express.pymata_express import PymataExpress
from pymata_express.pymata_express_serial import serial

from homeassistant.const import (
    CONF_BINARY_SENSORS,
    CONF_LIGHTS,
    CONF_NAME,
    CONF_SENSORS,
    CONF_SWITCHES,
)

from .const import (
    CONF_ARDUINO_INSTANCE_ID,
    CONF_ARDUINO_WAIT,
    CONF_SAMPLING_INTERVAL,
    CONF_SERIAL_BAUD_RATE,
    CONF_SERIAL_PORT,
    CONF_SLEEP_TUNE,
    PIN_TYPE_ANALOG,
    PIN_TYPE_DIGITAL,
)

_LOGGER = logging.getLogger(__name__)

FirmataPinType = int | str


class FirmataBoard:
    """Manages a single Firmata board."""

    def __init__(self, config: Mapping) -> None:
        """Initialize the board."""
        self.config = config
        self.api: PymataExpress = None
        self.firmware_version: str | None = None
        self.protocol_version = None
        self.name = self.config[CONF_NAME]
        self.switches = []
        self.lights = []
        self.binary_sensors = []
        self.sensors = []
        self.used_pins: list[FirmataPinType] = []

        if CONF_SWITCHES in self.config:
            self.switches = self.config[CONF_SWITCHES]
        if CONF_LIGHTS in self.config:
            self.lights = self.config[CONF_LIGHTS]
        if CONF_BINARY_SENSORS in self.config:
            self.binary_sensors = self.config[CONF_BINARY_SENSORS]
        if CONF_SENSORS in self.config:
            self.sensors = self.config[CONF_SENSORS]

    async def async_setup(self, tries=0) -> bool:
        """Set up a Firmata instance."""
        try:
            _LOGGER.debug("Connecting to Firmata %s", self.name)
            self.api = await get_board(self.config)
        except RuntimeError as err:
            _LOGGER.error("Error connecting to PyMata board %s: %s", self.name, err)
            return False
        except serial.SerialTimeoutException as err:
            _LOGGER.error(
                "Timeout writing to serial port for PyMata board %s: %s", self.name, err
            )
            return False
        except serial.SerialException as err:
            _LOGGER.error(
                "Error connecting to serial port for PyMata board %s: %s",
                self.name,
                err,
            )
            return False

        self.firmware_version = await self.api.get_firmware_version()
        if not self.firmware_version:
            _LOGGER.error(
                "Error retrieving firmware version from Firmata board %s", self.name
            )
            return False

        if CONF_SAMPLING_INTERVAL in self.config:
            try:
                await self.api.set_sampling_interval(
                    self.config[CONF_SAMPLING_INTERVAL]
                )
            except RuntimeError as err:
                _LOGGER.error(
                    "Error setting sampling interval for PyMata board %s: %s",
                    self.name,
                    err,
                )
                return False

        _LOGGER.debug("Firmata connection successful for %s", self.name)
        return True

    async def async_reset(self) -> bool:
        """Reset the board to default state."""
        _LOGGER.debug("Shutting down board %s", self.name)
        # If the board was never setup, continue.
        if self.api is None:
            return True

        await self.api.shutdown()
        self.api = None

        return True

    def mark_pin_used(self, pin: FirmataPinType) -> bool:
        """Test if a pin is used already on the board or mark as used."""
        if pin in self.used_pins:
            return False
        self.used_pins.append(pin)
        return True

    def get_pin_type(self, pin: FirmataPinType) -> tuple[Literal[0, 1], int]:
        """Return the type and Firmata location of a pin on the board."""
        pin_type: Literal[0, 1]
        firmata_pin: int
        if isinstance(pin, str):
            pin_type = PIN_TYPE_ANALOG
            firmata_pin = int(pin[1:])
            firmata_pin += self.api.first_analog_pin
        else:
            pin_type = PIN_TYPE_DIGITAL
            firmata_pin = pin
        return (pin_type, firmata_pin)


async def get_board(data: Mapping) -> PymataExpress:
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

"""Code to handle pins on a Firmata board."""
import logging
from typing import Callable

from homeassistant.core import callback

from .board import FirmataBoard, FirmataPinType
from .const import PIN_MODE_INPUT, PIN_MODE_PULLUP

_LOGGER = logging.getLogger(__name__)


class FirmataPinUsedException(Exception):
    """Represents an exception when a pin is already in use."""


class FirmataBoardPin:
    """Manages a single Firmata board pin."""

    def __init__(self, board: FirmataBoard, pin: FirmataPinType, pin_mode: str):
        """Initialize the pin."""
        self.board = board
        self._pin = pin
        self._pin_mode = pin_mode
        self._pin_type, self._firmata_pin = self.board.get_pin_type(self._pin)
        self._state = None

    def setup(self):
        """Set up a pin and make sure it is valid."""
        if not self.board.mark_pin_used(self._pin):
            raise FirmataPinUsedException(f"Pin {self._pin} already used!")


class FirmataBinaryDigitalOutput(FirmataBoardPin):
    """Representation of a Firmata Digital Output Pin."""

    def __init__(
        self,
        board: FirmataBoard,
        pin: FirmataPinType,
        pin_mode: str,
        initial: bool,
        negate: bool,
    ):
        """Initialize the digital output pin."""
        self._initial = initial
        self._negate = negate
        super().__init__(board, pin, pin_mode)

    async def start_pin(self) -> None:
        """Set initial state on a pin."""
        _LOGGER.debug(
            "Setting initial state for digital output pin %s on board %s",
            self._pin,
            self.board.name,
        )
        api = self.board.api
        # Only PIN_MODE_OUTPUT mode is supported as binary digital output
        await api.set_pin_mode_digital_output(self._firmata_pin)

        if self._initial:
            new_pin_state = not self._negate
        else:
            new_pin_state = self._negate
        await api.digital_pin_write(self._firmata_pin, int(new_pin_state))
        self._state = self._initial

    @property
    def is_on(self) -> bool:
        """Return true if digital output is on."""
        return self._state

    async def turn_on(self) -> None:
        """Turn on digital output."""
        _LOGGER.debug("Turning digital output on pin %s on", self._pin)
        new_pin_state = not self._negate
        await self.board.api.digital_pin_write(self._firmata_pin, int(new_pin_state))
        self._state = True

    async def turn_off(self) -> None:
        """Turn off digital output."""
        _LOGGER.debug("Turning digital output on pin %s off", self._pin)
        new_pin_state = self._negate
        await self.board.api.digital_pin_write(self._firmata_pin, int(new_pin_state))
        self._state = False


class FirmataBinaryDigitalInput(FirmataBoardPin):
    """Representation of a Firmata Digital Input Pin."""

    def __init__(
        self, board: FirmataBoard, pin: FirmataPinType, pin_mode: str, negate: bool
    ):
        """Initialize the digital input pin."""
        self._negate = negate
        self._forward_callback = None
        super().__init__(board, pin, pin_mode)

    async def start_pin(self, forward_callback: Callable[[], None]) -> None:
        """Get initial state and start reporting a pin."""
        _LOGGER.debug(
            "Starting reporting updates for input pin %s on board %s",
            self._pin,
            self.board.name,
        )
        self._forward_callback = forward_callback
        api = self.board.api
        if self._pin_mode == PIN_MODE_INPUT:
            await api.set_pin_mode_digital_input(self._pin, self.latch_callback)
        elif self._pin_mode == PIN_MODE_PULLUP:
            await api.set_pin_mode_digital_input_pullup(self._pin, self.latch_callback)

        new_state = bool((await self.board.api.digital_read(self._firmata_pin))[0])
        if self._negate:
            new_state = not new_state
        self._state = new_state

        await api.enable_digital_reporting(self._pin)
        self._forward_callback()

    async def stop_pin(self) -> None:
        """Stop reporting digital input pin."""
        _LOGGER.debug(
            "Stopping reporting updates for digital input pin %s on board %s",
            self._pin,
            self.board.name,
        )
        api = self.board.api
        await api.disable_digital_reporting(self._pin)

    @property
    def is_on(self) -> bool:
        """Return true if digital input is on."""
        return self._state

    @callback
    async def latch_callback(self, data: list) -> None:
        """Update pin state on callback."""
        if data[1] != self._firmata_pin:
            return
        _LOGGER.debug(
            "Received latch %d for digital input pin %d on board %s",
            data[2],
            self._firmata_pin,
            self.board.name,
        )
        new_state = bool(data[2])
        if self._negate:
            new_state = not new_state
        if self._state == new_state:
            return
        self._state = new_state
        self._forward_callback()

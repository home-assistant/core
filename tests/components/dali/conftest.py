"""Common fixtures for the Tridonic DALI tests."""

from collections.abc import Generator
from types import GeneratorType, SimpleNamespace
from unittest.mock import AsyncMock, patch

from dali.command import Command
from dali.gear.general import (
    DTR0,
    QueryActualLevel,
    QueryControlGearPresent,
    QueryDeviceType,
    QueryMaxLevel,
    QueryMinLevel,
)
from dali.gear.led import QueryDimmingCurve
import pytest


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.dali.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


class FakeDaliDriver:
    """Fake python-dali driver for integration tests."""

    def __init__(self, uri: str) -> None:
        """Initialize the fake driver."""
        self.uri = uri
        # Models an interface that is plugged in; tests that need it to go away
        # clear this, as python-dali does when the serial transport is lost.
        self.connected = True
        self.closed = False
        self.sent: list[Command] = []
        self.gears = {0: (6,), 1: (1,), 2: (6,)}
        self.levels = {0: 128, 1: 254, 2: 254}
        self.min_levels = {0: 86}
        self.max_levels: dict[int, int] = {}
        self.linear_dimming = {0: True}
        self._transport = SimpleNamespace(close=self._close)
        self._gear_dtr0: int | None = None

    async def connect(self, *, scan_dev_inst: bool = False) -> None:
        """Connect to the fake interface."""
        self.connected = True

    @property
    def is_connected(self) -> bool:
        """Return whether the fake interface is still reachable."""
        return self.connected

    async def send(
        self, msg: Command | Generator, *, priority: int = 5, progress=None
    ) -> object:
        """Return a response for a fake command, or run a fake sequence."""
        if isinstance(msg, GeneratorType):
            return await self._run_sequence(msg, progress=progress)
        return await self._send_command(msg)

    async def _send_command(self, command: Command) -> SimpleNamespace:
        """Return a response for a fake DALI command."""
        self.sent.append(command)
        if isinstance(command, DTR0):
            self._gear_dtr0 = command.param
            return SimpleNamespace(value=None)
        address = command.destination.address
        if isinstance(command, QueryControlGearPresent):
            return self._gear_present_response(address)
        if isinstance(command, QueryActualLevel):
            return SimpleNamespace(value=self.levels[address])
        if isinstance(command, QueryMinLevel):
            return SimpleNamespace(value=self.min_levels.get(address, 1))
        if isinstance(command, QueryMaxLevel):
            return SimpleNamespace(value=self.max_levels.get(address, 254))
        if isinstance(command, QueryDimmingCurve):
            value = 1 if self.linear_dimming.get(address, False) else 0
            return SimpleNamespace(
                raw_value=SimpleNamespace(as_integer=value, error=False)
            )
        return SimpleNamespace(value=None)

    async def _run_sequence(self, sequence, progress=None):
        """Return a fake sequence response."""
        first_command = next(sequence)
        if isinstance(first_command, QueryDeviceType):
            return list(self.gears.get(first_command.destination.address, ()))
        return SimpleNamespace(value=None)

    def _gear_present_response(self, address: int) -> SimpleNamespace:
        """Return a QueryControlGearPresent response for a short address."""
        if address not in self.gears:
            return SimpleNamespace(value=False, raw_value=None)
        return SimpleNamespace(value=True, raw_value=SimpleNamespace(error=False))

    def _close(self) -> None:
        """Close the fake transport."""
        self.closed = True
        self.connected = False


@pytest.fixture
def fake_dali_driver() -> FakeDaliDriver:
    """Return a fake python-dali driver."""
    return FakeDaliDriver("luba232:/dev/ttyACM0")

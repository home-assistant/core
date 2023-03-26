"""Test configuration for Nibe Heat Pump."""
from collections.abc import AsyncIterator, Generator, Iterable
from contextlib import ExitStack
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from nibe.coil import Coil, CoilData
from nibe.connection import Connection
from nibe.exceptions import ReadException
import pytest


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Make sure we never actually run setup."""
    with patch(
        "homeassistant.components.nibe_heatpump.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(autouse=True, name="mock_connection_constructor")
async def fixture_mock_connection_constructor():
    """Make sure we have a dummy connection."""
    mock_constructor = Mock()
    with ExitStack() as stack:
        places = [
            "homeassistant.components.nibe_heatpump.config_flow.NibeGW",
            "homeassistant.components.nibe_heatpump.config_flow.Modbus",
            "homeassistant.components.nibe_heatpump.NibeGW",
            "homeassistant.components.nibe_heatpump.Modbus",
        ]
        for place in places:
            stack.enter_context(patch(place, new=mock_constructor))
        yield mock_constructor


@pytest.fixture(name="mock_connection")
def fixture_mock_connection(mock_connection_constructor: Mock):
    """Make sure we have a dummy connection."""
    mock_connection = AsyncMock(spec=Connection)
    mock_connection_constructor.return_value = mock_connection
    return mock_connection


@pytest.fixture(name="coils")
async def fixture_coils(mock_connection):
    """Return a dict with coil data."""
    coils: dict[int, Any] = {}

    async def read_coil(coil: Coil, timeout: float = 0) -> CoilData:
        nonlocal coils
        if (data := coils.get(coil.address, None)) is None:
            raise ReadException()
        return CoilData(coil, data)

    async def read_coils(
        coils: Iterable[Coil], timeout: float = 0
    ) -> AsyncIterator[Coil]:
        for coil in coils:
            yield await read_coil(coil, timeout)

    mock_connection.read_coil = read_coil
    mock_connection.read_coils = read_coils
    return coils

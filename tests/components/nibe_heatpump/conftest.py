"""Test configuration for Nibe Heat Pump."""

from collections.abc import Generator
from contextlib import ExitStack
from unittest.mock import AsyncMock, Mock, patch

from freezegun.api import FrozenDateTimeFactory
from nibe.exceptions import CoilNotFoundException
import pytest

from homeassistant.core import HomeAssistant

from . import MockConnection

from tests.common import async_fire_time_changed


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Make sure we never actually run setup."""
    with patch(
        "homeassistant.components.nibe_heatpump.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(autouse=True, name="mock_connection_construct")
async def fixture_mock_connection_construct():
    """Fixture to catch constructor calls."""
    return Mock()


@pytest.fixture(autouse=True, name="mock_connection")
async def fixture_mock_connection(mock_connection_construct):
    """Make sure we have a dummy connection."""
    mock_connection = MockConnection()

    def construct(heatpump, *args, **kwargs):
        mock_connection_construct(heatpump, *args, **kwargs)
        mock_connection.heatpump = heatpump
        return mock_connection

    with ExitStack() as stack:
        places = [
            "homeassistant.components.nibe_heatpump.config_flow.NibeGW",
            "homeassistant.components.nibe_heatpump.config_flow.Modbus",
            "homeassistant.components.nibe_heatpump.NibeGW",
            "homeassistant.components.nibe_heatpump.Modbus",
        ]
        for place in places:
            stack.enter_context(patch(place, new=construct))
        yield mock_connection


@pytest.fixture(name="coils")
async def fixture_coils(mock_connection: MockConnection):
    """Return a dict with coil data."""
    # pylint: disable-next=import-outside-toplevel
    from homeassistant.components.nibe_heatpump import HeatPump

    get_coils_original = HeatPump.get_coils
    get_coil_by_address_original = HeatPump.get_coil_by_address

    def get_coils(x):
        coils_data = get_coils_original(x)
        return [coil for coil in coils_data if coil.address in mock_connection.coils]

    def get_coil_by_address(self, address):
        coils_data = get_coil_by_address_original(self, address)
        if coils_data.address not in mock_connection.coils:
            raise CoilNotFoundException
        return coils_data

    with (
        patch.object(HeatPump, "get_coils", new=get_coils),
        patch.object(HeatPump, "get_coil_by_address", new=get_coil_by_address),
    ):
        yield mock_connection.coils


@pytest.fixture(name="freezer_ticker")
async def fixture_freezer_ticker(hass: HomeAssistant, freezer: FrozenDateTimeFactory):
    """Tick time and perform actions."""

    async def ticker(delay, block=True):
        freezer.tick(delay)
        async_fire_time_changed(hass)
        if block:
            await hass.async_block_till_done()

    return ticker

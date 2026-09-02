"""Common fixtures for the Ecowitt WS90 tests.

The mock is loaded with the register image ``ecowitt_ws90_modbus`` ships for
this purpose (``testing.WS90_LIVE_EXAMPLE``), so everything below the
connection is the library's own code decoding a real register layout rather
than a stubbed device. A test that needs a different device overrides
``register_image``.
"""

from collections.abc import AsyncIterator, Generator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from ecowitt_ws90_modbus.testing import WS90_LIVE_EXAMPLE, WS90_UNIT_ID
from modbus_connection import ModbusTcpParams
from modbus_connection.mock import MockModbusConnection, MockModbusUnit
import pytest

from homeassistant.components.ecowitt_ws90.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from . import MOCK_DEVICE_ID, MOCK_USER_INPUT

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.ecowitt_ws90.async_setup_entry",
        new_callable=AsyncMock,
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def register_image() -> dict[int, int]:
    """The registers the mock WS90 answers with."""
    return WS90_LIVE_EXAMPLE


@pytest.fixture
def mock_connection(register_image: dict[int, int]) -> MockModbusConnection:
    """A fake Modbus connection serving the captured register image."""
    connection = MockModbusConnection()
    connection.for_unit(WS90_UNIT_ID).load_raw({"holding": dict(register_image)})
    return connection


@pytest.fixture
def mock_get_unit(mock_connection: MockModbusConnection) -> Generator[MagicMock]:
    """Hand the integration a unit on the mock connection."""
    with patch(
        "homeassistant.components.ecowitt_ws90.async_get_unit",
        side_effect=lambda hass, entry, params, unit_id: mock_connection.for_unit(
            unit_id
        ),
    ) as mock_get_unit:
        yield mock_get_unit


@pytest.fixture
def mock_temporary_unit(
    mock_connection: MockModbusConnection,
) -> Generator[MagicMock]:
    """Hand the config flow a unit on the mock connection."""

    @asynccontextmanager
    async def _get_unit(
        hass: HomeAssistant, params: ModbusTcpParams, unit_id: int
    ) -> AsyncIterator[MockModbusUnit]:
        yield mock_connection.for_unit(unit_id)

    with patch(
        "homeassistant.components.ecowitt_ws90.config_flow.async_get_temporary_unit",
        side_effect=_get_unit,
    ) as mock_temporary_unit:
        yield mock_temporary_unit


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock an Ecowitt WS90 config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_DEVICE_ID,
        data=MOCK_USER_INPUT,
        title=f"WS90 ({MOCK_USER_INPUT[CONF_HOST]})",
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_unit: MagicMock,
) -> MockConfigEntry:
    """Set up the Ecowitt WS90 integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    return mock_config_entry

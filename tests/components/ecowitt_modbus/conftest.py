"""Common fixtures for the Ecowitt Modbus tests.

The mock is loaded with the register image ``ecowitt_modbus`` ships for this
purpose, so everything below the connection is the device library's own code
decoding a real register layout rather than a stubbed device. A test that
needs a different device overrides ``register_image``.

Most fixtures take the model under test from the ``model_case`` fixture,
which is parametrized by the tests that need to run against every model.
"""

from collections.abc import AsyncIterator, Generator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from modbus_connection import ModbusTcpParams
from modbus_connection.mock import MockModbusConnection, MockModbusUnit
import pytest

from homeassistant.components.ecowitt_modbus.config_flow import _title
from homeassistant.components.ecowitt_modbus.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import WN90LP_CASE, ModelCase

from tests.common import MockConfigEntry

# Pinned so entity IDs derived from it are stable across runs.
MOCK_ENTRY_ID = "01JQBX3H8Z9K2M4N6P7R8S9TAV"


@pytest.fixture
def model_case(request: pytest.FixtureRequest) -> ModelCase:
    """The model under test.

    Defaults to the WN90LP so a test only concerned with shared behaviour need
    not care. Tests covering every model parametrize this indirectly.
    """
    return getattr(request, "param", WN90LP_CASE)


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.ecowitt_modbus.async_setup_entry",
        new_callable=AsyncMock,
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def register_image(model_case: ModelCase) -> dict[int, int]:
    """The registers the mock device answers with."""
    return model_case.registers


@pytest.fixture
def mock_connection(
    model_case: ModelCase, register_image: dict[int, int]
) -> MockModbusConnection:
    """A fake Modbus connection serving the captured register image."""
    connection = MockModbusConnection()
    connection.for_unit(model_case.unit_id).load_raw({"holding": dict(register_image)})
    return connection


@pytest.fixture
def mock_unit(
    model_case: ModelCase, mock_connection: MockModbusConnection
) -> MockModbusUnit:
    """The unit the integration talks to, for tests that poke the device."""
    return mock_connection.for_unit(model_case.unit_id)


@pytest.fixture
def mock_get_unit(mock_connection: MockModbusConnection) -> Generator[MagicMock]:
    """Hand the integration a unit on the mock connection."""
    with patch(
        "homeassistant.components.ecowitt_modbus.async_get_unit",
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
        "homeassistant.components.ecowitt_modbus.config_flow.async_get_temporary_unit",
        side_effect=_get_unit,
    ) as mock_temporary_unit:
        yield mock_temporary_unit


@pytest.fixture
def mock_config_entry(model_case: ModelCase) -> MockConfigEntry:
    """Mock a config entry for the model under test.

    The title is built with the config flow's own ``_title``, not a copy of
    its format, so this fixture cannot drift from what a real entry is
    titled -- a mismatch there would let the snapshots pass while missing a
    real regression in title generation.

    The entry ID is pinned because a model that reports no serial number
    keys its entities on the entry itself, and a fresh random ID each run
    would make those snapshots unrepeatable.
    """
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id=MOCK_ENTRY_ID,
        unique_id=model_case.unique_id,
        data=model_case.entry_data,
        title=_title(model_case.name, model_case.user_input),
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_unit: MagicMock,
) -> MockConfigEntry:
    """Set up the Ecowitt Modbus integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    return mock_config_entry

"""Common fixtures for the De Lijn tests."""

from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from pydelijn import Line, Passage, Stop
import pytest

from homeassistant.components.delijn.const import CONF_STOP_NUMBER, DOMAIN
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

STOP_NUMBER = "200112"


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a De Lijn config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "test-api-key", CONF_STOP_NUMBER: STOP_NUMBER},
        unique_id=STOP_NUMBER,
        title="Brugsepoort (Begijnhoflaan), Gent",
    )


@pytest.fixture
def mock_stop() -> Stop:
    """Return a De Lijn stop fixture."""
    return Stop(
        entity_number="2",
        number=STOP_NUMBER,
        name="Brugsepoort (Begijnhoflaan)",
        municipality="Gent",
        latitude=51.070365,
        longitude=3.700651,
    )


@pytest.fixture
def mock_line() -> Line:
    """Return a De Lijn line fixture."""
    return Line(
        entity_number="2",
        number="4048",
        public_number="4",
        description="Wondelgem - Flanders Expo",
        transport_type="tram",
        colour_front_hex="#FFFFFF",
        colour_front_border_hex="#000000",
        colour_back_hex="#FFCC00",
        colour_back_border_hex="#000000",
    )


@pytest.fixture
def mock_passages(mock_line: Line) -> list[Passage]:
    """Return a list of De Lijn passage fixtures."""
    return [
        Passage(
            line=mock_line,
            direction="Heen",
            destination="Wondelgem",
            due_at_schedule=datetime(2026, 8, 6, 12, 5, tzinfo=UTC),
            due_at_realtime=datetime(2026, 8, 6, 12, 7, tzinfo=UTC),
            is_realtime=True,
            cancelled=False,
            ride_number="123456",
            vehicle_number="3101",
        ),
        Passage(
            line=mock_line,
            direction="Heen",
            destination="Wondelgem",
            due_at_schedule=datetime(2026, 8, 6, 12, 20, tzinfo=UTC),
            due_at_realtime=None,
            is_realtime=False,
            cancelled=False,
            ride_number="123457",
            vehicle_number="3102",
        ),
    ]


@pytest.fixture
def mock_delijn_client(
    mock_stop: Stop, mock_passages: list[Passage]
) -> Generator[MagicMock]:
    """Mock the pydelijn client wherever it is constructed."""
    with (
        patch(
            "homeassistant.components.delijn.DeLijnClient", autospec=True
        ) as mock_client,
        patch(
            "homeassistant.components.delijn.coordinator.DeLijnClient",
            new=mock_client,
        ),
        patch(
            "homeassistant.components.delijn.config_flow.DeLijnClient",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.get_stop.return_value = mock_stop
        client.search_stops.return_value = [mock_stop]
        client.get_passages.return_value = mock_passages
        yield client


@pytest.fixture
async def load_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_delijn_client: MagicMock,
) -> MockConfigEntry:
    """Set up the De Lijn integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry

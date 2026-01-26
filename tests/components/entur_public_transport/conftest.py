"""Fixtures for Entur public transport tests."""

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.entur_public_transport.const import (
    CONF_EXPAND_PLATFORMS,
    CONF_NUMBER_OF_DEPARTURES,
    CONF_OMIT_NON_BOARDING,
    CONF_STOP_IDS,
    CONF_WHITELIST_LINES,
    DOMAIN,
)
from homeassistant.const import CONF_SHOW_ON_MAP
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Entur NSR:StopPlace:548",
        data={
            CONF_STOP_IDS: ["NSR:StopPlace:548"],
            CONF_EXPAND_PLATFORMS: True,
            CONF_SHOW_ON_MAP: False,
            CONF_WHITELIST_LINES: [],
            CONF_OMIT_NON_BOARDING: True,
            CONF_NUMBER_OF_DEPARTURES: 2,
        },
        unique_id="NSR:StopPlace:548",
    )


@pytest.fixture
def mock_estimated_call() -> MagicMock:
    """Return a mock estimated call."""
    call = MagicMock()
    call.is_realtime = True
    call.expected_departure_time = datetime.now(tz=UTC) + timedelta(minutes=5)
    call.front_display = "45 Voss"
    call.line_id = "NSB:Line:45"
    call.transport_mode = "rail"
    call.delay_in_min = 0
    return call


@pytest.fixture
def mock_place(mock_estimated_call: MagicMock) -> MagicMock:
    """Return a mock place."""
    place = MagicMock()
    place.name = "Bergen stasjon"
    place.place_id = "NSR:StopPlace:548"
    place.latitude = 60.39032
    place.longitude = 5.33396
    place.estimated_calls = [mock_estimated_call]
    return place


@pytest.fixture
def mock_entur_client(mock_place: MagicMock) -> Generator[MagicMock]:
    """Return a mock Entur client."""
    with patch(
        "homeassistant.components.entur_public_transport.EnturPublicTransportData"
    ) as mock_client_class:
        client = mock_client_class.return_value
        client.update = AsyncMock()
        client.expand_all_quays = AsyncMock()
        client.all_stop_places_quays.return_value = ["NSR:StopPlace:548"]
        client.get_stop_info.return_value = mock_place
        yield client


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_entur_client: MagicMock,
) -> MockConfigEntry:
    """Set up the Entur integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry

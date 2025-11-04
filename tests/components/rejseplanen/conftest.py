"""Fixtures for Rejseplanen tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from py_rejseplan.dataclasses.departure import DepartureType
from py_rejseplan.dataclasses.departure_board import DepartureBoard
from py_rejseplan.enums import TransportClass
import pytest

from homeassistant.components.rejseplanen.const import (
    CONF_API_KEY,
    CONF_NAME,
    CONF_STOP_ID,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER, ConfigSubentry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.rejseplanen.async_setup_entry", return_value=True
    ) as mock_async_setup_entry:
        yield mock_async_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Rejseplanen",
        data={
            CONF_API_KEY: "test_api_key",
            CONF_NAME: "Rejseplanen",
        },
        unique_id="rejseplanen_test",
    )


@pytest.fixture
def mock_departure_data() -> list[DepartureType]:
    """Return mock departure data."""
    mock_departure = MagicMock(spec=DepartureType)
    mock_departure.name = "Test Line"
    mock_departure.type = TransportClass.BUS
    mock_departure.direction = "North"
    mock_departure.stop = "Test Stop"
    mock_departure.time = "12:00"
    mock_departure.date = "2024-11-04"
    mock_departure.track = "1"
    mock_departure.final_stop = "Final Stop"
    mock_departure.messages = []
    mock_departure.rtTime = "12:01"
    mock_departure.rtDate = "2024-11-04"
    mock_departure.stopExtId = 123456  # Add missing stopExtId attribute
    return [mock_departure]


@pytest.fixture
def mock_api() -> Generator[MagicMock]:
    """Return a mocked Rejseplanen API client."""
    with patch(
        "homeassistant.components.rejseplanen.coordinator.DeparturesAPIClient"
    ) as mock_api_class:
        mock_api = MagicMock()
        mock_departure_board = MagicMock(spec=DepartureBoard)
        mock_departure_board.departures = []
        mock_api.get_departures.return_value = (mock_departure_board, [])
        mock_api_class.return_value = mock_api
        yield mock_api


@pytest.fixture
def mock_rejseplan() -> MagicMock:
    """Return a mocked Rejseplanen API client."""
    mock_api = MagicMock()
    mock_api.validate_auth_key = AsyncMock(return_value=True)
    mock_api.get_departures = AsyncMock(return_value=[])
    return mock_api


@pytest.fixture
def platforms() -> list[Platform]:
    """Return platforms to load."""
    return [Platform.SENSOR]


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> MockConfigEntry:
    """Set up the integration for testing."""
    mock_config_entry.add_to_hass(hass)

    # Mock the API at the coordinator level since it's created internally
    with patch(
        "homeassistant.components.rejseplanen.coordinator.DeparturesAPIClient"
    ) as mock_api_class:
        mock_api = MagicMock()
        mock_api.get_departures.return_value = ([], [])
        mock_api_class.return_value = mock_api

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry


@pytest.fixture
async def setup_main_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_departure_data: list[DepartureType],
) -> MockConfigEntry:
    """Set up main integration with departure data."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.rejseplanen.coordinator.DeparturesAPIClient"
    ) as mock_api_class:
        mock_api = MagicMock()

        mock_departure_board = MagicMock(spec=DepartureBoard)
        mock_departure_board.departures = mock_departure_data

        mock_api.get_departures.return_value = (mock_departure_board, [])
        mock_api_class.return_value = mock_api

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry


@pytest.fixture
async def setup_integration_with_stop(
    hass: HomeAssistant,
    setup_main_integration: MockConfigEntry,
    mock_departure_data: list[DepartureType],
) -> tuple[MockConfigEntry, ConfigSubentry]:
    """Set up integration with a stop subentry using proper subentry flow."""
    main_entry = setup_main_integration

    with patch(
        "homeassistant.components.rejseplanen.coordinator.DeparturesAPIClient"
    ) as mock_api_class:
        mock_api = MagicMock()
        mock_board = MagicMock(spec=DepartureBoard)
        mock_board.departures = mock_departure_data
        mock_api.get_departures.return_value = (mock_board, [])
        mock_api_class.return_value = mock_api

        # Create subentry through proper subentry flow
        result = await hass.config_entries.subentries.async_init(
            (main_entry.entry_id, "stop"), context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            user_input={CONF_STOP_ID: "123456", CONF_NAME: "Test Stop"},
        )
        await hass.async_block_till_done()

    # Get the created subentry from main_entry.subentries
    assert len(main_entry.subentries) == 1, "Expected exactly one subentry"
    subentry_id = list(main_entry.subentries.keys())[0]
    subentry = main_entry.subentries[subentry_id]

    return main_entry, subentry


@pytest.fixture
async def setup_with_multiple_departures(hass: HomeAssistant) -> MockConfigEntry:
    """Set up with multiple departure types."""
    # Create departures of different types
    departures = []
    for i, transport_type in enumerate(
        [TransportClass.BUS, TransportClass.METRO, TransportClass.S_TOG]
    ):
        dep = MagicMock(spec=DepartureType)
        dep.name = f"Line {i}"
        dep.type = transport_type
        dep.direction = f"Direction {i}"
        dep.time = f"{12 + i}:00"
        dep.date = "2024-11-04"
        dep.cancelled = False
        departures.append(dep)

    main_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "test", CONF_NAME: "Test"},
        unique_id="test",
    )
    main_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.rejseplanen.coordinator.DeparturesAPIClient"
    ) as mock_api_class:
        mock_api = MagicMock()
        mock_board = MagicMock(spec=DepartureBoard)
        mock_board.departures = departures
        mock_api.get_departures.return_value = (mock_board, [])
        mock_api_class.return_value = mock_api

        await hass.config_entries.async_setup(main_entry.entry_id)
        await hass.async_block_till_done()

    return main_entry

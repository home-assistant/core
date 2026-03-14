"""Tests for Met Office Weather Warnings coordinator."""

from datetime import UTC, datetime

from homeassistant.components.metoffice_warnings.coordinator import (
    MetOfficeWarningsCoordinator,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import TEST_URL

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_single_warning(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_warnings_response: AiohttpClientMocker,
) -> None:
    """Test parsing a feed with a single warning."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator: MetOfficeWarningsCoordinator = mock_config_entry.runtime_data

    assert coordinator.data is not None
    assert coordinator.data.pub_date == datetime(2026, 3, 12, 8, 0, tzinfo=UTC)
    assert len(coordinator.data.warnings) == 1

    warning = coordinator.data.warnings[0]
    assert warning.level == "Yellow"
    assert warning.warning_type == "Rain"
    assert warning.link == "https://weather.metoffice.gov.uk/warnings/123"
    assert warning.start == "2026-03-12T08:00:00"
    assert warning.end == "2026-03-12T20:00:00"


async def test_multiple_warnings(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_multiple_warnings_response: AiohttpClientMocker,
) -> None:
    """Test parsing a feed with multiple warnings."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator: MetOfficeWarningsCoordinator = mock_config_entry.runtime_data

    assert coordinator.data is not None
    assert len(coordinator.data.warnings) == 3

    assert coordinator.data.warnings[0].level == "Yellow"
    assert coordinator.data.warnings[0].warning_type == "Rain"

    assert coordinator.data.warnings[1].level == "Amber"
    assert coordinator.data.warnings[1].warning_type == "Wind"

    assert coordinator.data.warnings[2].level == "Red"
    assert coordinator.data.warnings[2].warning_type == "Snow"


async def test_no_warnings(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_no_warnings_response: AiohttpClientMocker,
) -> None:
    """Test parsing a feed with no warnings."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator: MetOfficeWarningsCoordinator = mock_config_entry.runtime_data

    assert coordinator.data is not None
    assert coordinator.data.pub_date is not None
    assert len(coordinator.data.warnings) == 0


async def test_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test handling of connection errors."""
    aioclient_mock.get(TEST_URL, exc=TimeoutError)

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_invalid_xml(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test handling of invalid XML."""
    aioclient_mock.get(TEST_URL, text="<invalid>xml")

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_no_channel_element(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_no_channel_response: AiohttpClientMocker,
) -> None:
    """Test handling of valid XML with no channel element."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_warning_edge_cases(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_edge_cases_response: AiohttpClientMocker,
) -> None:
    """Test parsing warnings with edge-case validity strings."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator: MetOfficeWarningsCoordinator = mock_config_entry.runtime_data

    assert coordinator.data is not None
    assert len(coordinator.data.warnings) == 3

    # First warning: no "valid from ... to ..." in description
    assert coordinator.data.warnings[0].start is None
    assert coordinator.data.warnings[0].end is None

    # Second warning: unknown month abbreviation "Xyz"
    assert coordinator.data.warnings[1].start == "noon Wed 12 Xyz"
    assert coordinator.data.warnings[1].end == "2000 Wed 12 Xyz"

    # Third warning: invalid day (32) causes ValueError
    assert coordinator.data.warnings[2].start == "0800 Wed 32 Mar"
    assert coordinator.data.warnings[2].end == "2000 Wed 32 Mar"

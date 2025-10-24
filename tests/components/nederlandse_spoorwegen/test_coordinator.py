"""Tests for the Nederlandse Spoorwegen coordinator."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.nederlandse_spoorwegen.coordinator import (
    NSDataUpdateCoordinator,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.freeze_time(
    "2025-09-15 14:30:00+00:00"
)  # Test current time is 16:30 in Amsterdam
async def test_get_time_from_route_no_time_provided(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nsapi: MagicMock,
) -> None:
    """Test _get_time_from_route when no time is provided."""
    await hass.config_entries.async_add(mock_config_entry)
    subentry_id, subentry = next(iter(mock_config_entry.subentries.items()))

    coordinator = NSDataUpdateCoordinator(
        hass, mock_config_entry, subentry_id, subentry
    )

    dt_str, fetch_now = coordinator._get_time_from_route(None)

    assert fetch_now is True
    assert dt_str == "15-09-2025 16:30"


@pytest.mark.freeze_time(
    "2025-09-15 14:30:00+00:00"
)  # Test current time is 16:30 in Amsterdam
async def test_get_time_from_route_within_30_minutes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nsapi: MagicMock,
) -> None:
    """Test _get_time_from_route when time is within ±30 minutes."""
    await hass.config_entries.async_add(mock_config_entry)
    subentry_id, subentry = next(iter(mock_config_entry.subentries.items()))

    coordinator = NSDataUpdateCoordinator(
        hass, mock_config_entry, subentry_id, subentry
    )

    # Test time 15 minutes in the future (16:45)
    dt_str, fetch_now = coordinator._get_time_from_route("16:45")
    assert fetch_now is True
    assert dt_str == "15-09-2025 16:45"

    # Test time exactly 30 minutes in the future (17:00)
    dt_str, fetch_now = coordinator._get_time_from_route("17:00")
    assert fetch_now is True
    assert dt_str == "15-09-2025 17:00"


@pytest.mark.freeze_time(
    "2025-09-15 14:30:00+00:00"
)  # Test current time is 16:30 in Amsterdam
async def test_get_time_from_route_outside_30_minutes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nsapi: MagicMock,
) -> None:
    """Test _get_time_from_route when time is outside ±30 minutes."""
    await hass.config_entries.async_add(mock_config_entry)
    subentry_id, subentry = next(iter(mock_config_entry.subentries.items()))

    coordinator = NSDataUpdateCoordinator(
        hass, mock_config_entry, subentry_id, subentry
    )

    # Test time 45 minutes in the future (17:15) - outside window
    dt_str, fetch_now = coordinator._get_time_from_route("17:15")
    assert fetch_now is False
    assert dt_str == "15-09-2025 17:15"


@pytest.mark.freeze_time(
    "2025-09-15 14:30:00+00:00"
)  # Test current time is 16:30 in Amsterdam
async def test_get_time_from_route_malformed_time(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nsapi: MagicMock,
) -> None:
    """Test _get_time_from_route with malformed time that causes ValueError."""
    await hass.config_entries.async_add(mock_config_entry)
    subentry_id, subentry = next(iter(mock_config_entry.subentries.items()))

    coordinator = NSDataUpdateCoordinator(
        hass, mock_config_entry, subentry_id, subentry
    )

    # Test with invalid hour/minute values that will cause strptime ValueError
    dt_str, fetch_now = coordinator._get_time_from_route("25:99")
    assert fetch_now is True  # Should fallback and treat as fetch now
    assert dt_str == "15-09-2025 16:30"


@pytest.mark.freeze_time(
    "2025-09-15 14:30:00+00:00"
)  # Test current time is 16:30 in Amsterdam
async def test_get_time_from_route_invalid_format(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nsapi: MagicMock,
) -> None:
    """Test _get_time_from_route with invalid time format."""
    await hass.config_entries.async_add(mock_config_entry)
    subentry_id, subentry = next(iter(mock_config_entry.subentries.items()))

    coordinator = NSDataUpdateCoordinator(
        hass, mock_config_entry, subentry_id, subentry
    )

    # Test with space in string (invalid) - falls back to current time
    dt_str, fetch_now = coordinator._get_time_from_route("14:30 PM")
    assert fetch_now is True
    assert dt_str == "15-09-2025 16:30"

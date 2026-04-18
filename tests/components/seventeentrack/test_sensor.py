"""Tests for the seventeentrack sensor."""

from __future__ import annotations

from unittest.mock import AsyncMock

from pyseventeentrack.errors import SeventeenTrackError

from homeassistant.core import HomeAssistant

from . import init_integration
from .conftest import DEFAULT_SUMMARY, get_package

from tests.common import MockConfigEntry


async def test_full_valid_config(
    hass: HomeAssistant,
    mock_seventeentrack: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Ensure everything starts correctly."""
    await init_integration(hass, mock_config_entry)
    assert len(hass.states.async_entity_ids()) == len(DEFAULT_SUMMARY.keys())


async def test_valid_config(
    hass: HomeAssistant,
    mock_seventeentrack: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Ensure everything starts correctly."""
    await init_integration(hass, mock_config_entry)
    assert len(hass.states.async_entity_ids()) == len(DEFAULT_SUMMARY.keys())


async def test_invalid_config(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Ensure nothing is created when config is wrong."""
    await init_integration(hass, mock_config_entry)
    assert not hass.states.async_entity_ids("sensor")


async def test_login_exception(
    hass: HomeAssistant,
    mock_seventeentrack: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Ensure everything starts correctly."""
    mock_seventeentrack.return_value.profile.login.side_effect = SeventeenTrackError(
        "Error"
    )
    await init_integration(hass, mock_config_entry)
    assert not hass.states.async_entity_ids("sensor")


async def test_package_error(
    hass: HomeAssistant,
    mock_seventeentrack: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Ensure package is added correctly when user add a new package."""
    mock_seventeentrack.return_value.profile.packages.side_effect = SeventeenTrackError(
        "Error"
    )
    mock_seventeentrack.return_value.profile.summary.return_value = {}

    await init_integration(hass, mock_config_entry)
    assert hass.states.get("sensor.17track_package_friendly_name_1") is None


async def test_summary_error(
    hass: HomeAssistant,
    mock_seventeentrack: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test summary empty if error."""
    package = get_package(status=30)
    mock_seventeentrack.return_value.profile.packages.return_value = [package]
    mock_seventeentrack.return_value.profile.summary.side_effect = SeventeenTrackError(
        "Error"
    )

    await init_integration(hass, mock_config_entry)

    assert len(hass.states.async_entity_ids()) == 0

    assert (
        hass.states.get("sensor.seventeentrack_packages_ready_to_be_picked_up") is None
    )

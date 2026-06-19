"""Tests for the GeoSphere Austria Warnings integration setup."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from pygeosphere_warnings import (
    GeoSphereApiError,
    GeoSphereConnectionError,
    GeoSphereMunicipalityNotFoundError,
)
import pytest

from homeassistant.components.geosphere_austria_warnings.coordinator import (
    UPDATE_INTERVAL,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.usefixtures("mock_client")
async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test loading and unloading the config entry."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    "side_effect",
    [
        pytest.param(GeoSphereConnectionError, id="connection_error"),
        pytest.param(GeoSphereApiError, id="api_error"),
        pytest.param(GeoSphereMunicipalityNotFoundError, id="municipality_not_found"),
    ],
)
async def test_setup_retry(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    side_effect: type[Exception],
) -> None:
    """Test that the entry is retried when the first refresh fails."""
    mock_client.get_last_modified.side_effect = side_effect
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.freeze_time("2023-03-27 12:00:00+00:00")
async def test_warnings_fetch_skipped_when_unchanged(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that the HEAD precheck avoids refetching unchanged warnings."""
    await setup_integration(hass, mock_config_entry)
    assert mock_client.get_warnings_for_coords.call_count == 1

    # Unchanged Last-Modified: warnings are not refetched
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert mock_client.get_warnings_for_coords.call_count == 1

    # New Last-Modified: warnings are refetched
    mock_client.get_last_modified.return_value = datetime(
        2023, 3, 27, 12, 0, tzinfo=UTC
    )
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert mock_client.get_warnings_for_coords.call_count == 2


@pytest.mark.freeze_time("2023-03-27 12:00:00+00:00")
async def test_entities_unavailable_on_error(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that entities become unavailable when the update fails."""
    await setup_integration(hass, mock_config_entry)
    assert (state := hass.states.get("sensor.schwechat_active_warnings"))
    assert state.state != STATE_UNAVAILABLE

    mock_client.get_last_modified.side_effect = GeoSphereConnectionError
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert (state := hass.states.get("sensor.schwechat_active_warnings"))
    assert state.state == STATE_UNAVAILABLE

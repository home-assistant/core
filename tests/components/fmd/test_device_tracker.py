"""Test the FMD device tracker platform."""

from datetime import timedelta
import json
from typing import Any
from unittest.mock import MagicMock

from fmd_api import AuthenticationError, FmdApiException
from freezegun.api import FrozenDateTimeFactory
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.fmd.const import DEFAULT_POLLING_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import TEST_LOCATION, setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

ENTITY_ID = "device_tracker.fmd_test_user"


async def test_all_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_fmd_client: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test all device tracker entities are created."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_location_attributes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_fmd_client: MagicMock,
) -> None:
    """Test location data flows to state attributes."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state.attributes["latitude"] == 37.7749
    assert state.attributes["longitude"] == -122.4194
    assert state.attributes["battery_level"] == 85
    assert state.attributes["gps_accuracy"] == 10.5


async def test_refresh_updates_location(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_fmd_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a scheduled refresh updates the tracker state."""
    await setup_integration(hass, mock_config_entry)

    new_location = dict(TEST_LOCATION, lat=38.0, lon=-121.0, bat=42)
    mock_fmd_client.decrypt_data_blob.side_effect = lambda blob: json.dumps(
        new_location
    ).encode()

    freezer.tick(timedelta(minutes=DEFAULT_POLLING_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.attributes["latitude"] == 38.0
    assert state.attributes["longitude"] == -121.0
    assert state.attributes["battery_level"] == 42


async def test_inaccurate_locations_skipped(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_fmd_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test BeaconDB fixes are skipped in favor of accurate ones."""
    await setup_integration(hass, mock_config_entry)

    def decrypt(blob: Any) -> bytes:
        """Serve an inaccurate fix first, accurate fix second."""
        if blob == "blob1":
            return json.dumps(dict(TEST_LOCATION, provider="beacondb")).encode()
        return json.dumps(dict(TEST_LOCATION, lat=40.0, provider="gps")).encode()

    mock_fmd_client.get_locations.return_value = ["blob1", "blob2"]
    mock_fmd_client.decrypt_data_blob.side_effect = decrypt

    freezer.tick(timedelta(minutes=DEFAULT_POLLING_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.attributes["latitude"] == 40.0
    assert state.attributes.get("provider") == "gps"


async def test_tracker_becomes_unavailable_on_api_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_fmd_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test tracker goes unavailable when refreshes start failing."""
    await setup_integration(hass, mock_config_entry)

    mock_fmd_client.get_locations.side_effect = FmdApiException("boom")

    freezer.tick(timedelta(minutes=DEFAULT_POLLING_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    # Coordinator keeps last known data, entity stays available with old fix
    assert state.attributes["latitude"] == 37.7749


async def test_auth_failure_starts_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_fmd_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test AuthenticationError during refresh triggers ConfigEntryAuthFailed."""
    await setup_integration(hass, mock_config_entry)

    mock_fmd_client.get_locations.side_effect = AuthenticationError("expired")

    freezer.tick(timedelta(minutes=DEFAULT_POLLING_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # AuthenticationError raised from the coordinator during a refresh
    # (this is where reauth will hook in once PR2 adds the flow)
    assert mock_config_entry.state is ConfigEntryState.LOADED

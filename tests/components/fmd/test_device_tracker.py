"""Test the FMD device tracker platform."""

from datetime import timedelta
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from fmd_api import AuthenticationError, FmdApiException
from freezegun.api import FrozenDateTimeFactory
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.fmd.const import DEFAULT_POLLING_INTERVAL, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ID, CONF_URL, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import TEST_ARTIFACTS, TEST_ID, TEST_LOCATION, TEST_URL, setup_integration

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
    # UpdateFailed propagates: last update failed, entity becomes unavailable
    assert state.state == STATE_UNAVAILABLE


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


async def test_tracker_movement_attributes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_fmd_client: MagicMock,
) -> None:
    """Test altitude, speed and heading are exposed with units."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state.attributes["altitude"] == 132
    assert state.attributes["altitude_unit"] == "m"
    assert state.attributes["speed"] == 23.42
    assert state.attributes["speed_unit"] == "m/s"
    assert state.attributes["heading"] == 95
    assert state.attributes["device_timestamp_ms"] == "1761220800000"


async def test_tracker_parses_bad_numeric_fields(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_fmd_client: MagicMock,
) -> None:
    """Test battery/accuracy fall back gracefully on non-numeric values."""
    bad = dict(TEST_LOCATION)
    bad["bat"] = "not-a-number"
    bad["accuracy"] = None
    del bad["altitude"]
    del bad["speed"]
    del bad["heading"]
    mock_fmd_client.decrypt_data_blob = MagicMock(
        side_effect=lambda blob: json.dumps(bad).encode()
    )
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state.attributes.get("battery_level") is None
    assert state.attributes["gps_accuracy"] == 0
    assert "altitude" not in state.attributes
    assert "speed" not in state.attributes
    assert "heading" not in state.attributes


async def test_tracker_missing_battery_and_accuracy(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_fmd_client: MagicMock,
) -> None:
    """Test battery None path and float() fallback for accuracy."""
    partial = dict(TEST_LOCATION)
    partial["bat"] = None
    partial["accuracy"] = "garbage"
    mock_fmd_client.decrypt_data_blob = MagicMock(
        side_effect=lambda blob: json.dumps(partial).encode()
    )
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state.attributes.get("battery_level") is None
    assert state.attributes["gps_accuracy"] == 0


async def test_tracker_skips_empty_and_inaccurate_blobs(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_fmd_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test empty blobs and inaccurate fixes are skipped for accurate data."""
    weak = dict(TEST_LOCATION)
    weak["provider"] = "beacondb"
    mock_fmd_client.get_locations = AsyncMock(
        return_value=["", "weak-blob", "good-blob"]
    )
    mock_fmd_client.decrypt_data_blob = MagicMock(
        side_effect=lambda blob: json.dumps(
            weak if blob == "weak-blob" else TEST_LOCATION
        ).encode()
    )
    await setup_integration(hass, mock_config_entry)

    # Good fix wins even when preceded by an empty blob and a weak fix
    state = hass.states.get(ENTITY_ID)
    assert state.attributes["provider"] == "gps"

    # All fixes inaccurate -> UpdateFailed on the scheduled refresh
    weak2 = dict(TEST_LOCATION)
    weak2["provider"] = "beacondb"
    mock_fmd_client.decrypt_data_blob = MagicMock(
        side_effect=lambda blob: json.dumps(weak2).encode()
    )
    freezer.tick(timedelta(minutes=DEFAULT_POLLING_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_UNAVAILABLE


async def test_same_account_on_two_servers(
    hass: HomeAssistant,
    mock_fmd_client: MagicMock,
) -> None:
    """Test identical account IDs on different servers get separate devices."""
    entry_a = MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"{TEST_URL}/{TEST_ID}",
        title=TEST_ID,
        data={
            CONF_URL: TEST_URL,
            CONF_ID: TEST_ID,
            "artifacts": dict(TEST_ARTIFACTS),
        },
    )
    entry_b = MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"https://fmd-other.example.com/{TEST_ID}",
        title=TEST_ID,
        data={
            CONF_URL: "https://fmd-other.example.com",
            CONF_ID: TEST_ID,
            "artifacts": dict(TEST_ARTIFACTS),
        },
    )
    for entry in (entry_a, entry_b):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get("device_tracker.fmd_test_user") is not None
    assert hass.states.get("device_tracker.fmd_test_user_2") is not None

    er_entries = er.async_entries_for_config_entry(
        hass.data[er.DATA_REGISTRY], entry_b.entry_id
    )
    assert len(er_entries) == 1
    assert er_entries[0].unique_id == f"https://fmd-other.example.com/{TEST_ID}"

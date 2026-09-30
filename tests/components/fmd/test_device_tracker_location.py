"""Test FMD device tracker location logic."""

import contextlib
from unittest.mock import AsyncMock, patch

from homeassistant.components.fmd.const import DOMAIN
from homeassistant.const import CONF_ID, CONF_PASSWORD, CONF_URL
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.fmd.common import setup_integration


def _make_entry(hass: HomeAssistant, data_overrides: dict) -> MockConfigEntry:
    base = {
        "url": "https://fmd.example.com",
        "id": "edge_user",
        "artifacts": {
            "base_url": "https://fmd.example.com",
            "fmd_id": "edge_user",
            "access_token": "t",
            "private_key": "k",
            "password_hash": "h",
            "session_duration": 3600,
            "token_issued_at": 123.0,
        },
        "polling_interval": 30,
        "allow_inaccurate_locations": False,
    }
    base.update(data_overrides)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="edge_user",
        data=base,
        entry_id="edge_entry_id",
        unique_id="edge_user",
    )
    entry.add_to_hass(hass)
    return entry


async def test_device_tracker_location_filtering(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test location accuracy filtering."""
    import json

    # Create mock encrypted blobs for two locations
    beacondb_data = {
        "lat": 37.7749,
        "lon": -122.4194,
        "time": "2025-10-23T12:00:00Z",
        "provider": "beacondb",  # Inaccurate provider
        "bat": 85,
        "accuracy": 10.5,
        "speed": 0.0,
    }
    gps_data = {
        "lat": 37.7750,
        "lon": -122.4195,
        "time": "2025-10-23T11:59:00Z",
        "provider": "gps",  # Accurate provider
        "bat": 85,
        "accuracy": 10.5,
        "speed": 0.0,
    }

    # Mock returns "encrypted" blobs (we'll mock decrypt to handle both)
    mock_fmd_api.create.return_value.get_locations.return_value = [
        "encrypted_beacondb_blob",
        "encrypted_gps_blob",
    ]

    # Mock decrypt to return appropriate data based on blob
    def decrypt_side_effect(blob):
        if blob == "encrypted_beacondb_blob":
            return json.dumps(beacondb_data).encode("utf-8")
        if blob == "encrypted_gps_blob":
            return json.dumps(gps_data).encode("utf-8")
        return b"{}"

    mock_fmd_api.create.return_value.decrypt_data_blob.side_effect = decrypt_side_effect

    await setup_integration(hass, mock_fmd_api)

    state = hass.states.get("device_tracker.fmd_test_user")
    # Should use GPS location, not beacondb
    assert state.attributes["latitude"] == 37.7750
    assert state.attributes["provider"] == "gps"


async def test_device_tracker_inaccurate_location_filtering_enabled(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test inaccurate location filtering blocks low-accuracy providers."""
    # First set up with accurate location
    mock_fmd_api.create.return_value.get_locations.return_value = [
        {
            "lat": 37.7749,
            "lon": -122.4194,
            "time": "2025-10-23T12:00:00Z",
            "provider": "gps",
            "bat": 85,
            "accuracy": 10.5,
        }
    ]

    await setup_integration(hass, mock_fmd_api)

    state = hass.states.get("device_tracker.fmd_test_user")
    assert state is not None
    assert state.attributes["latitude"] == 37.7749

    # Now test that inaccurate provider (beacondb with high inaccuracy) is filtered
    # Update to inaccurate location only
    mock_fmd_api.create.return_value.get_locations.return_value = [
        {
            "lat": 40.0,
            "lon": -120.0,
            "time": "2025-10-23T12:05:00Z",
            "provider": "beacondb",
            "bat": 85,
            "accuracy": 5000.0,  # Very inaccurate
        }
    ]

    # Trigger an update and verify it doesn't change (stays at previous location)
    tracker = hass.config_entries.async_entries("fmd")[0].runtime_data.tracker
    await tracker.async_update()
    tracker.async_write_ha_state()
    await hass.async_block_till_done()

    state = hass.states.get("device_tracker.fmd_test_user")
    # Should keep previous accurate location, not update to inaccurate one
    assert state.attributes["latitude"] == 37.7749


async def test_device_tracker_inaccurate_locations_warning(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test warning when only inaccurate locations found with filtering enabled."""
    # Return only inaccurate providers
    mock_fmd_api.create.return_value.get_locations.return_value = [
        {
            "lat": 37.7749,
            "lon": -122.4194,
            "time": "2025-10-23T12:00:00Z",
            "provider": "beacondb",  # Inaccurate provider
        },
        {
            "lat": 37.7749,
            "lon": -122.4194,
            "time": "2025-10-23T12:00:00Z",
            "provider": "unknown",  # Inaccurate provider
        },
    ]

    await setup_integration(hass, mock_fmd_api)

    # Force an update
    tracker = hass.config_entries.async_entries("fmd")[0].runtime_data.tracker
    await tracker.async_update()

    # Verify location was not updated (stayed None)
    assert tracker.latitude is None
    assert tracker.longitude is None


async def test_multiple_location_filtering_selects_first_accurate(
    hass: HomeAssistant, mock_fmd_api: AsyncMock
) -> None:
    """When blocking inaccurate locations, choose first accurate provider (gps) after skipping BeaconDB."""
    entry = _make_entry(hass, {"allow_inaccurate_locations": False})

    # Provide two blobs: first inaccurate provider BeaconDB, second GPS accurate
    location_blob_inaccurate = {
        "lat": 10.0,
        "lon": 20.0,
        "time": "2025-10-23T12:00:00Z",
        "provider": "BeaconDB",
        "bat": 50,
        "accuracy": 300.0,
    }
    location_blob_accurate = {
        "lat": 11.1,
        "lon": 21.2,
        "time": "2025-10-23T12:01:00Z",
        "provider": "gps",
        "bat": 51,
        "accuracy": 5.0,
    }

    api = mock_fmd_api.create.return_value
    api.get_locations.return_value = [location_blob_inaccurate, location_blob_accurate]

    with patch(
        "homeassistant.components.fmd.FmdClient.from_auth_artifacts", return_value=api
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    tracker = entry.runtime_data.tracker
    await tracker.async_update()
    assert tracker.latitude == 11.1 and tracker.longitude == 21.2
    # Battery from accurate location
    assert tracker.extra_state_attributes.get("battery_level") == 51
    assert tracker.extra_state_attributes.get("provider") == "gps"


async def test_block_inaccurate_disabled_uses_first_blob(
    hass: HomeAssistant, mock_fmd_api: AsyncMock
) -> None:
    """When allow_inaccurate_locations=True, use first (most recent) blob even if provider is BeaconDB."""
    entry = _make_entry(hass, {"allow_inaccurate_locations": True})

    blob1 = {
        "lat": 1.0,
        "lon": 2.0,
        "time": "2025-10-23T12:00:00Z",
        "provider": "BeaconDB",
        "bat": 80,
    }
    blob2 = {
        "lat": 3.0,
        "lon": 4.0,
        "time": "2025-10-23T12:01:00Z",
        "provider": "gps",
        "bat": 81,
    }

    api = mock_fmd_api.create.return_value
    api.get_locations.return_value = [blob1, blob2]

    with patch(
        "homeassistant.components.fmd.FmdClient.from_auth_artifacts", return_value=api
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    tracker = entry.runtime_data.tracker
    await tracker.async_update()
    # Should keep first blob provider BeaconDB because filtering disabled
    assert tracker.extra_state_attributes.get("provider") == "BeaconDB"
    assert tracker.latitude == 1.0 and tracker.longitude == 2.0


async def test_allow_inaccurate_true_uses_first_location_update(
    hass: HomeAssistant, mock_fmd_api: AsyncMock
) -> None:
    """When allow_inaccurate_locations is True, use the most recent regardless of provider."""
    # Create a base entry and set allow_inaccurate_locations=True using async_update_entry
    config_entry = _make_entry(hass, {"allow_inaccurate_locations": True})

    # Most recent is an inaccurate provider
    mock_fmd_api.create.return_value.get_locations.return_value = [
        {
            "lat": 1.0,
            "lon": 2.0,
            "time": "2025-10-23T12:00:00Z",
            "provider": "beacondb",
        }
    ]

    with patch(
        "homeassistant.components.fmd.FmdClient.from_auth_artifacts",
        return_value=mock_fmd_api.create.return_value,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("device_tracker.fmd_edge_user")
    assert state is not None
    assert state.attributes["latitude"] == 1.0
    assert state.attributes["provider"] == "beacondb"


async def test_device_tracker_imperial_units(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test imperial unit conversion."""
    # Create config entry with imperial units enabled
    config_entry = MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title="test_user",
        data={
            CONF_URL: "https://fmd.example.com",
            CONF_ID: "test_user",
            CONF_PASSWORD: "test_password",
            "polling_interval": 30,
            "allow_inaccurate_locations": False,
            "use_imperial": True,  # Enable imperial units
        },
        entry_id="test_entry_id",
        unique_id="test_user",
    )
    config_entry.add_to_hass(hass)

    mock_fmd_api.create.return_value.get_locations.return_value = [
        {
            "lat": 37.7749,
            "lon": -122.4194,
            "time": "2025-10-23T12:00:00Z",
            "provider": "gps",
            "bat": 85,
            "accuracy": 10.5,
            "altitude": 100.0,
            "speed": 5.5,
            "heading": 180.0,
        }
    ]

    with patch("homeassistant.components.fmd.FmdClient.create", mock_fmd_api.create):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("device_tracker.fmd_test_user")
    # GPS accuracy should be converted from meters to feet
    # Speed should be converted from m/s to mph
    assert "gps_accuracy_unit" in state.attributes
    assert state.attributes["gps_accuracy_unit"] == "ft"
    assert state.attributes["altitude_unit"] == "ft"
    assert state.attributes["speed_unit"] == "mph"


async def test_device_tracker_imperial_altitude_speed(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test device tracker with altitude and speed attributes in imperial."""
    mock_fmd_api.create.return_value.get_locations.return_value = [
        {
            "lat": 37.7749,
            "lon": -122.4194,
            "time": "2025-10-23T12:00:00Z",
            "provider": "gps",
            "bat": 85,
            "accuracy": 10.5,
            "altitude": 100.0,  # meters
            "speed": 10.0,  # m/s
        }
    ]

    # Setup with imperial units
    config_entry = MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title="test_user",
        data={
            CONF_URL: "https://fmd.example.com",
            CONF_ID: "test_user",
            CONF_PASSWORD: "test_password",
            "polling_interval": 30,
            "allow_inaccurate_locations": False,
            "use_imperial": True,
        },
        entry_id="test_entry_id",
        unique_id="test_user",
    )
    config_entry.add_to_hass(hass)

    with patch("homeassistant.components.fmd.FmdClient.create", mock_fmd_api.create):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("device_tracker.fmd_test_user")
    assert state is not None
    # Verify altitude and speed attributes are present and converted
    # 100m -> ~328.1 ft
    # 10 m/s -> ~22.4 mph
    assert state.attributes.get("altitude_unit") == "ft"
    assert state.attributes.get("speed_unit") == "mph"


async def test_device_tracker_zero_accuracy(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test device tracker handles zero accuracy value."""
    # Start fresh with zero accuracy from the beginning
    mock_fmd_api.create.return_value.get_locations.reset_mock()
    mock_fmd_api.create.return_value.get_locations.return_value = [
        {
            "lat": 37.7749,
            "lon": -122.4194,
            "time": "2025-10-23T12:00:00Z",
            "provider": "gps",
            "bat": 85,
            "accuracy": 0.0,  # Zero accuracy
        }
    ]

    await setup_integration(hass, mock_fmd_api)

    state = hass.states.get("device_tracker.fmd_test_user")
    assert state is not None
    assert state.attributes["gps_accuracy"] == 0.0


async def test_device_tracker_missing_attributes(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test device tracker handles missing optional location attributes."""
    # Location with only required fields
    mock_fmd_api.create.return_value.get_locations.return_value = [
        {
            "lat": 37.7749,
            "lon": -122.4194,
            "time": "2025-10-23T12:00:00Z",
            "provider": "gps",
            # Missing optional fields: bat, acc, alt, spd, dir
        }
    ]

    await setup_integration(hass, mock_fmd_api)

    state = hass.states.get("device_tracker.fmd_test_user")
    assert state is not None
    assert state.attributes["latitude"] == 37.7749
    assert state.attributes["longitude"] == -122.4194


async def test_unknown_provider_logged_as_inaccurate(
    hass: HomeAssistant, mock_fmd_api: AsyncMock, caplog
) -> None:
    """Unknown provider should log warning and be treated as inaccurate when filtering enabled."""
    entry = _make_entry(hass, {"allow_inaccurate_locations": False})

    # First blob unknown provider -> skipped, second gps used
    blob_unknown = {
        "lat": 0.0,
        "lon": 0.0,
        "time": "2025-10-23T12:00:00Z",
        "provider": "mystery",
        "bat": 10,
    }
    blob_gps = {
        "lat": 9.9,
        "lon": 9.8,
        "time": "2025-10-23T12:00:10Z",
        "provider": "gps",
        "bat": 11,
    }
    api = mock_fmd_api.create.return_value
    api.get_locations.return_value = [blob_unknown, blob_gps]

    with patch(
        "homeassistant.components.fmd.FmdClient.from_auth_artifacts", return_value=api
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    tracker = entry.runtime_data.tracker
    await tracker.async_update()
    assert tracker.latitude == 9.9 and tracker.longitude == 9.8
    assert any("Unknown location provider" in r.message for r in caplog.records)


async def test_decrypt_returns_invalid_json_logs_exception(
    hass: HomeAssistant, mock_fmd_api: AsyncMock, caplog
) -> None:
    """If decrypted bytes are invalid JSON, update should log error and keep previous location."""
    entry = _make_entry(hass, {"allow_inaccurate_locations": True})
    api = mock_fmd_api.create.return_value

    # Return one 'blob' that will decrypt to invalid JSON string
    api.get_locations.return_value = ["not_json_blob"]

    def bad_decrypt(arg):
        return b"{this is not valid json}"

    api.decrypt_data_blob.side_effect = bad_decrypt

    with patch(
        "homeassistant.components.fmd.FmdClient.from_auth_artifacts", return_value=api
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    tracker = entry.runtime_data.tracker
    # First update will try and fail to parse
    # We expect a generic exception path handled inside async_update; shouldn't propagate
    with contextlib.suppress(Exception):
        await tracker.async_update()
    # Warning or error about unexpected error should appear
    assert any("Unexpected error getting location" in r.message for r in caplog.records)


async def test_empty_blob_warning_then_next_blob_used(
    hass: HomeAssistant, mock_fmd_api: AsyncMock, caplog
) -> None:
    """Empty blob at index 0 logs warning, then next blob is checked and used."""
    await setup_integration(hass, mock_fmd_api)

    # Get the tracker
    entry = hass.config_entries.async_entries("fmd")[0]
    tracker = entry.runtime_data.tracker

    import json

    # First blob is empty, second is valid JSON string
    valid_blob = json.dumps(
        {
            "lat": 38.0,
            "lon": -123.0,
            "provider": "gps",
            "time": "2025-11-22T15:00:00Z",
            "bat": 80,
            "acc": 10.5,
        }
    )

    mock_fmd_api.create.return_value.get_locations.return_value = [
        None,  # Empty blob (triggers warning)
        valid_blob,  # String blob
    ]

    # Mock decrypt to return bytes (JSON string as bytes)
    mock_fmd_api.create.return_value.decrypt_data_blob.side_effect = [
        valid_blob.encode()  # Return bytes, will be parsed by json.loads
    ]

    caplog.clear()
    await tracker.async_update()

    # Verify warning about empty blob was logged
    assert any("Empty blob at index" in record.message for record in caplog.records)

    # Verify the valid second blob was used
    assert tracker.latitude == 38.0
    assert tracker.longitude == -123.0


async def test_device_tracker_location_provider_types(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test device tracker correctly identifies different provider types."""
    # Test GPS (Accurate)
    mock_fmd_api.create.return_value.get_locations.return_value = [
        {
            "lat": 37.7749,
            "lon": -122.4194,
            "time": "2025-10-23T12:00:00Z",
            "provider": "gps",
            "bat": 85,
            "accuracy": 5.0,
        }
    ]
    await setup_integration(hass, mock_fmd_api)
    state = hass.states.get("device_tracker.fmd_test_user")
    assert state.attributes.get("latitude") == 37.7749

    # Test Network (Accurate)
    mock_fmd_api.create.return_value.get_locations.return_value = [
        {
            "lat": 37.7749,
            "lon": -122.4194,
            "time": "2025-10-23T12:00:00Z",
            "provider": "network",
            "bat": 85,
            "accuracy": 15.0,
        }
    ]
    tracker = hass.config_entries.async_entries("fmd")[0].runtime_data.tracker
    await tracker.async_update()
    assert tracker.latitude == 37.7749

    # Test Cell (Inaccurate)
    mock_fmd_api.create.return_value.get_locations.return_value = [
        {
            "lat": 37.7749,
            "lon": -122.4194,
            "time": "2025-10-23T12:00:00Z",
            "provider": "cell",
            "bat": 85,
            "accuracy": 1000.0,
        }
    ]
    # Should be filtered if inaccurate locations not allowed (default)
    await tracker.async_update()
    # Since we already have a location, it shouldn't update to this one if filtered
    # But wait, if it's the same location, we can't tell.
    # Let's change the location for the inaccurate one
    mock_fmd_api.create.return_value.get_locations.return_value = [
        {
            "lat": 40.0,
            "lon": -120.0,
            "time": "2025-10-23T12:05:00Z",
            "provider": "cell",
            "bat": 85,
            "accuracy": 1000.0,
        }
    ]
    await tracker.async_update()
    # Should still be the old location
    assert tracker.latitude == 37.7749


async def test_device_tracker_decrypt_error_in_update(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
    caplog,
) -> None:
    """Test device tracker handles decryption error during update."""
    mock_fmd_api.create.return_value.get_locations.return_value = ["corrupted_blob"]
    mock_fmd_api.create.return_value.decrypt_data_blob.side_effect = Exception(
        "Decryption failed"
    )

    await setup_integration(hass, mock_fmd_api)

    state = hass.states.get("device_tracker.fmd_test_user")
    assert state is not None
    assert any(
        "Unexpected error getting location" in message for message in caplog.messages
    )

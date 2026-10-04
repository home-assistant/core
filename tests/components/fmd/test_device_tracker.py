"""Test the FMD device tracker platform."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

from fmd_api import AuthenticationError, FmdApiException
from fmd_api.models import Location
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
    assert state.attributes["battery"] == 85
    assert state.attributes["gps_accuracy"] == 10.5


async def test_refresh_updates_location(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_fmd_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a scheduled refresh updates the tracker state."""
    await setup_integration(hass, mock_config_entry)

    new_location = Location.from_json(dict(TEST_LOCATION, lat=38.0, lon=-121.0, bat=42))
    mock_fmd_client.get_latest_location = AsyncMock(return_value=new_location)

    freezer.tick(timedelta(minutes=DEFAULT_POLLING_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.attributes["latitude"] == 38.0
    assert state.attributes["longitude"] == -121.0
    assert state.attributes["battery"] == 42


async def test_accuracy_preference_plumbs_through_to_client(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_fmd_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the accuracy preference is passed to the client call."""
    await setup_integration(hass, mock_config_entry)

    freezer.tick(timedelta(minutes=DEFAULT_POLLING_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # The coordinator passes filter_inaccurate=True by default; provider
    # filtering itself is covered by fmd-api's own test suite.
    assert mock_fmd_client.get_latest_location.await_count >= 1
    kwargs = mock_fmd_client.get_latest_location.await_args.kwargs
    assert kwargs.get("filter_inaccurate") is True


async def test_tracker_becomes_unavailable_on_api_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_fmd_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test tracker goes unavailable when refreshes start failing."""
    await setup_integration(hass, mock_config_entry)

    mock_fmd_client.get_latest_location = AsyncMock(side_effect=FmdApiException("boom"))

    freezer.tick(timedelta(minutes=DEFAULT_POLLING_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_UNAVAILABLE


async def test_auth_failure_entry_stays_loaded_no_reauth_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_fmd_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test AuthenticationError handling before a reauth flow exists.

    FMD has no async_step_reauth yet, so no reauth flow is started;
    reauth arrives with the follow-up platform PR.
    """
    await setup_integration(hass, mock_config_entry)

    mock_fmd_client.get_latest_location = AsyncMock(
        side_effect=AuthenticationError("expired")
    )

    freezer.tick(timedelta(minutes=DEFAULT_POLLING_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    assert not any(
        mock_config_entry.async_get_active_flows(hass, {"reauth", "reconfigure"})
    )


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


async def test_tracker_lenient_optional_fields(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_fmd_client: MagicMock,
) -> None:
    """Test unusable optional values become None without failing the fix."""
    partial = dict(TEST_LOCATION)
    partial["bat"] = "not-a-number"
    partial["accuracy"] = None
    del partial["altitude"]
    del partial["speed"]
    del partial["heading"]
    mock_fmd_client.get_latest_location = AsyncMock(
        return_value=Location.from_json(partial)
    )

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert "battery" not in state.attributes
    assert state.attributes["gps_accuracy"] == 0
    assert "altitude" not in state.attributes
    assert "speed" not in state.attributes
    assert "heading" not in state.attributes


async def test_tracker_missing_battery_and_accuracy(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_fmd_client: MagicMock,
) -> None:
    """Test battery None path and missing accuracy fall back gracefully."""
    partial = dict(TEST_LOCATION)
    partial["bat"] = None
    partial["accuracy"] = "garbage"
    mock_fmd_client.get_latest_location = AsyncMock(
        return_value=Location.from_json(partial)
    )

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert "battery" not in state.attributes
    assert state.attributes["gps_accuracy"] == 0


async def test_no_location_data_raises_update_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_fmd_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that no usable fix (client returns None) surfaces as unavailable.

    The library-level scan (malformed blobs, invalid coordinates, provider
    filtering) is covered by fmd-api's own test suite; at this layer, None
    from get_latest_location means no usable fix was found.
    """
    await setup_integration(hass, mock_config_entry)

    mock_fmd_client.get_latest_location = AsyncMock(return_value=None)

    freezer.tick(timedelta(minutes=DEFAULT_POLLING_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
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

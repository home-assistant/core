"""Test the Tesla Fleet init."""

from copy import deepcopy
from datetime import timedelta
from unittest.mock import AsyncMock, Mock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from tesla_fleet_api.const import Scope, VehicleDataEndpoint
from tesla_fleet_api.exceptions import (
    InvalidRegion,
    InvalidToken,
    LibraryError,
    LoginRequired,
    OAuthExpired,
    RateLimited,
    TeslaFleetError,
    VehicleOffline,
)

from homeassistant.components.tesla_fleet.const import DOMAIN
from homeassistant.components.tesla_fleet.coordinator import (
    ENERGY_HISTORY_INTERVAL,
    ENERGY_INTERVAL,
    ENERGY_INTERVAL_SECONDS,
    VEHICLE_INTERVAL,
    VEHICLE_INTERVAL_SECONDS,
    VEHICLE_WAIT,
    _invalidate_access_token,
)
from homeassistant.components.tesla_fleet.models import TeslaFleetData
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import (
    OAuth2TokenRequestReauthError,
    OAuth2TokenRequestTransientError,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
)

from . import setup_platform
from .conftest import create_config_entry
from .const import LIVE_STATUS, VEHICLE_ASLEEP, VEHICLE_DATA_ALT

from tests.common import MockConfigEntry, async_fire_time_changed

SETUP_ERRORS = [
    (InvalidToken, ConfigEntryState.SETUP_ERROR),
    (OAuthExpired, ConfigEntryState.SETUP_ERROR),
    (LoginRequired, ConfigEntryState.SETUP_ERROR),
    (TeslaFleetError, ConfigEntryState.SETUP_RETRY),
]

RUNTIME_ERRORS = [InvalidToken, OAuthExpired, LoginRequired, TeslaFleetError]


async def test_load_unload(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
) -> None:
    """Test load and unload."""

    await setup_platform(hass, normal_config_entry)

    assert normal_config_entry.state is ConfigEntryState.LOADED
    assert isinstance(normal_config_entry.runtime_data, TeslaFleetData)
    assert await hass.config_entries.async_unload(normal_config_entry.entry_id)
    await hass.async_block_till_done()
    assert normal_config_entry.state is ConfigEntryState.NOT_LOADED
    assert not hasattr(normal_config_entry, "runtime_data")


@pytest.mark.parametrize(("side_effect", "state"), SETUP_ERRORS)
async def test_init_error(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    mock_products: AsyncMock,
    side_effect: type[TeslaFleetError],
    state: ConfigEntryState,
) -> None:
    """Test init with errors."""

    mock_products.side_effect = side_effect
    await setup_platform(hass, normal_config_entry)
    assert normal_config_entry.state is state


async def test_oauth_refresh_expired(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    mock_products: AsyncMock,
) -> None:
    """Test init with expired Oauth token."""

    # Patch the token refresh to raise an error
    with patch(
        "homeassistant.components.tesla_fleet.OAuth2Session.async_ensure_token_valid",
        side_effect=OAuth2TokenRequestReauthError(
            domain=DOMAIN,
            request_info=Mock(),
        ),
    ) as mock_async_ensure_token_valid:
        # Trigger an unmocked function call
        mock_products.side_effect = InvalidRegion
        await setup_platform(hass, normal_config_entry)

        mock_async_ensure_token_valid.assert_called_once()
    assert normal_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_oauth_refresh_error(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    mock_products: AsyncMock,
) -> None:
    """Test init with Oauth refresh failure."""

    # Patch the token refresh to raise an error
    with patch(
        "homeassistant.components.tesla_fleet.OAuth2Session.async_ensure_token_valid",
        side_effect=OAuth2TokenRequestTransientError(
            domain=DOMAIN,
            request_info=Mock(),
        ),
    ) as mock_async_ensure_token_valid:
        # Trigger an unmocked function call
        mock_products.side_effect = InvalidRegion
        await setup_platform(hass, normal_config_entry)

        mock_async_ensure_token_valid.assert_called_once()
    assert normal_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_invalidate_access_token_updates_when_not_expired(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
) -> None:
    """Test invalidating token updates entry when token is not expired."""
    normal_config_entry.add_to_hass(hass)
    expected_data = {
        **dict(normal_config_entry.data),
        CONF_TOKEN: {
            **normal_config_entry.data[CONF_TOKEN],
            "expires_at": 0,
        },
    }

    _invalidate_access_token(hass, normal_config_entry)

    assert dict(normal_config_entry.data) == expected_data


async def test_invalidate_access_token_noop_when_already_expired(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
) -> None:
    """Test invalidating token does not update an already expired token."""
    normal_config_entry.add_to_hass(hass)
    normal_config_entry.data[CONF_TOKEN]["expires_at"] = 0
    before_data = dict(normal_config_entry.data)

    _invalidate_access_token(hass, normal_config_entry)

    assert dict(normal_config_entry.data) == before_data


async def test_invalidate_access_token_noop_when_token_missing(
    hass: HomeAssistant,
) -> None:
    """Test invalidating token does not update when token data is missing."""

    missing_token_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"auth_implementation": DOMAIN},
    )
    missing_token_entry.add_to_hass(hass)
    before_data = dict(missing_token_entry.data)

    _invalidate_access_token(hass, missing_token_entry)

    assert dict(missing_token_entry.data) == before_data


# Test devices
async def test_devices(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test device registry."""
    await setup_platform(hass, normal_config_entry)
    devices = dr.async_entries_for_config_entry(
        device_registry, normal_config_entry.entry_id
    )

    for device in devices:
        assert device == snapshot(name=f"{device.identifiers}")


# Vehicle Coordinator
async def test_vehicle_refresh_offline(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    mock_vehicle_state: AsyncMock,
    mock_vehicle_data: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test coordinator refresh with an error."""
    await setup_platform(hass, normal_config_entry)
    assert normal_config_entry.state is ConfigEntryState.LOADED

    mock_vehicle_state.assert_called_once()
    mock_vehicle_data.assert_called_once()
    mock_vehicle_state.reset_mock()
    mock_vehicle_data.reset_mock()

    # Then the vehicle goes offline despite saying its online
    mock_vehicle_data.side_effect = VehicleOffline
    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_vehicle_state.assert_called_once()
    mock_vehicle_data.assert_called_once()
    mock_vehicle_state.reset_mock()
    mock_vehicle_data.reset_mock()

    # And stays offline
    mock_vehicle_state.return_value = VEHICLE_ASLEEP
    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_vehicle_state.assert_called_once()
    mock_vehicle_data.assert_not_called()


@pytest.mark.parametrize("side_effect", RUNTIME_ERRORS)
async def test_vehicle_refresh_error(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    mock_vehicle_data: AsyncMock,
    side_effect: type[TeslaFleetError],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test coordinator refresh makes entity unavailable."""

    await setup_platform(hass, normal_config_entry)

    mock_vehicle_data.side_effect = side_effect
    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get("sensor.test_battery_level"))
    assert state.state == "unavailable"


async def test_vehicle_refresh_token_expired_recovery(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    mock_vehicle_data: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test coordinator recovers from expired vehicle access token."""
    await setup_platform(hass, normal_config_entry)
    assert normal_config_entry.state is ConfigEntryState.LOADED
    assert (state := hass.states.get("sensor.test_battery_level"))
    assert state.state != "unavailable"

    mock_vehicle_data.reset_mock()
    mock_vehicle_data.side_effect = OAuthExpired

    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert normal_config_entry.state is ConfigEntryState.LOADED
    assert (state := hass.states.get("sensor.test_battery_level"))
    assert state.state == "unavailable"
    assert normal_config_entry.data["token"]["expires_at"] == 0
    assert mock_vehicle_data.call_count == 1

    mock_vehicle_data.side_effect = None
    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get("sensor.test_battery_level"))
    assert state.state != "unavailable"
    assert mock_vehicle_data.call_count == 2


async def test_vehicle_refresh_ratelimited(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    mock_vehicle_data: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test coordinator refresh handles 429."""

    mock_vehicle_data.side_effect = RateLimited(
        {"after": VEHICLE_INTERVAL_SECONDS + 10}
    )
    await setup_platform(hass, normal_config_entry)

    assert (state := hass.states.get("sensor.test_battery_level"))
    assert state.state == "unknown"

    mock_vehicle_data.reset_mock()

    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get("sensor.test_battery_level"))
    assert state.state == "unknown"


async def test_vehicle_refresh_ratelimited_no_after(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    mock_vehicle_data: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test coordinator refresh handles 429 without after."""

    await setup_platform(hass, normal_config_entry)
    # mock_vehicle_data called once during setup
    assert mock_vehicle_data.call_count == 1

    mock_vehicle_data.side_effect = RateLimited({})
    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Called again during refresh, failed with RateLimited
    assert mock_vehicle_data.call_count == 2

    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Called again because skip refresh doesn't change interval
    assert mock_vehicle_data.call_count == 3


async def test_init_invalid_region(
    hass: HomeAssistant,
    expires_at: int,
) -> None:
    """Test init with an invalid region in the token."""

    # ou_code 'other' should be caught by the region validation and set to None
    config_entry = create_config_entry(
        expires_at, [Scope.VEHICLE_DEVICE_DATA], region="other"
    )

    with patch("homeassistant.components.tesla_fleet.TeslaFleetApi") as mock_api:
        await setup_platform(hass, config_entry)
        # Check if TeslaFleetApi was called with region=None
        mock_api.assert_called()
        assert mock_api.call_args.kwargs.get("region") is None


async def test_vehicle_sleep(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    mock_vehicle_data: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test coordinator refresh with an error."""

    TEST_INTERVAL = timedelta(seconds=120)

    with patch(
        "homeassistant.components.tesla_fleet.coordinator.VEHICLE_INTERVAL",
        TEST_INTERVAL,
    ):
        await setup_platform(hass, normal_config_entry)
        assert mock_vehicle_data.call_count == 1

        freezer.tick(VEHICLE_WAIT + TEST_INTERVAL)
        async_fire_time_changed(hass)
        # Let vehicle sleep, no updates for 15 minutes
        await hass.async_block_till_done()
        assert mock_vehicle_data.call_count == 2

        freezer.tick(TEST_INTERVAL)
        async_fire_time_changed(hass)
        # No polling, call_count should not increase
        await hass.async_block_till_done()
        assert mock_vehicle_data.call_count == 2

        freezer.tick(VEHICLE_WAIT)
        async_fire_time_changed(hass)
        # Vehicle didn't sleep, go back to normal
        await hass.async_block_till_done()
        assert mock_vehicle_data.call_count == 3

        freezer.tick(TEST_INTERVAL)
        async_fire_time_changed(hass)
        # Regular polling
        await hass.async_block_till_done()
        assert mock_vehicle_data.call_count == 4

        mock_vehicle_data.return_value = VEHICLE_DATA_ALT
        freezer.tick(TEST_INTERVAL)
        async_fire_time_changed(hass)
        # Vehicle active
        await hass.async_block_till_done()
        assert mock_vehicle_data.call_count == 5

        freezer.tick(TEST_INTERVAL)
        async_fire_time_changed(hass)
        # Dont let sleep when active
        await hass.async_block_till_done()
        assert mock_vehicle_data.call_count == 6

        freezer.tick(TEST_INTERVAL)
        async_fire_time_changed(hass)
        # Dont let sleep when active
        await hass.async_block_till_done()
        assert mock_vehicle_data.call_count == 7


# Test Energy Live Coordinator
@pytest.mark.parametrize("side_effect", RUNTIME_ERRORS)
async def test_energy_live_refresh_error(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    mock_live_status: AsyncMock,
    side_effect: type[TeslaFleetError],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test coordinator refresh with an error."""
    await setup_platform(hass, normal_config_entry)
    assert normal_config_entry.state is ConfigEntryState.LOADED

    mock_live_status.side_effect = side_effect
    freezer.tick(ENERGY_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get("sensor.energy_site_grid_power"))
    assert state.state == "unavailable"


async def test_energy_live_refresh_bad_response(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    mock_live_status: AsyncMock,
) -> None:
    """Test coordinator refresh with malformed live status payload."""
    bad_live_status = deepcopy(LIVE_STATUS)
    bad_live_status["response"] = "site data is unavailable"
    mock_live_status.side_effect = None
    mock_live_status.return_value = bad_live_status

    await setup_platform(hass, normal_config_entry)

    assert normal_config_entry.state is ConfigEntryState.LOADED
    assert (state := hass.states.get("sensor.test_battery_level"))
    assert state.state != "unavailable"


async def test_energy_live_refresh_bad_wall_connectors(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    mock_live_status: AsyncMock,
) -> None:
    """Test coordinator refresh with malformed wall connector payload."""
    bad_live_status = deepcopy(LIVE_STATUS)
    bad_live_status["response"]["wall_connectors"] = "site data is unavailable"
    mock_live_status.side_effect = None
    mock_live_status.return_value = bad_live_status

    await setup_platform(hass, normal_config_entry)

    assert normal_config_entry.state is ConfigEntryState.LOADED
    assert (state := hass.states.get("sensor.test_battery_level"))
    assert state.state != "unavailable"


# Test Energy Site Coordinator
@pytest.mark.parametrize("side_effect", RUNTIME_ERRORS)
async def test_energy_site_refresh_error(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    mock_site_info: AsyncMock,
    side_effect: type[TeslaFleetError],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test coordinator refresh with an error."""
    await setup_platform(hass, normal_config_entry)
    assert normal_config_entry.state is ConfigEntryState.LOADED

    mock_site_info.side_effect = side_effect
    freezer.tick(ENERGY_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get("number.energy_site_backup_reserve"))
    assert state.state == "unavailable"


async def test_energy_refresh_token_expired_recovery(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    mock_live_status: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test energy coordinator recovers from expired access token."""
    await setup_platform(hass, normal_config_entry)
    assert normal_config_entry.state is ConfigEntryState.LOADED
    assert (state := hass.states.get("sensor.energy_site_grid_power"))
    assert state.state != "unavailable"

    mock_live_status.reset_mock()
    mock_live_status.side_effect = OAuthExpired

    freezer.tick(ENERGY_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert normal_config_entry.state is ConfigEntryState.LOADED
    assert (state := hass.states.get("sensor.energy_site_grid_power"))
    assert state.state == "unavailable"
    assert normal_config_entry.data["token"]["expires_at"] == 0
    assert mock_live_status.call_count == 1

    mock_live_status.side_effect = None
    freezer.tick(ENERGY_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get("sensor.energy_site_grid_power"))
    assert state.state != "unavailable"
    assert mock_live_status.call_count == 2


# Test Energy History Coordinator
@pytest.mark.parametrize("side_effect", RUNTIME_ERRORS)
async def test_energy_history_refresh_error(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    mock_energy_history: AsyncMock,
    side_effect: type[TeslaFleetError],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test coordinator refresh with an error."""
    await setup_platform(hass, normal_config_entry)
    assert normal_config_entry.state is ConfigEntryState.LOADED

    # Now test that the coordinator handles errors during refresh
    mock_energy_history.side_effect = side_effect
    freezer.tick(ENERGY_HISTORY_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # The coordinator should handle the error gracefully
    assert normal_config_entry.state is ConfigEntryState.LOADED


async def test_energy_live_refresh_ratelimited(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    mock_live_status,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test coordinator refresh handles 429."""

    await setup_platform(hass, normal_config_entry)

    mock_live_status.side_effect = RateLimited({"after": ENERGY_INTERVAL_SECONDS + 10})
    freezer.tick(ENERGY_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_live_status.call_count == 2

    freezer.tick(ENERGY_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Should not call for another 10 seconds
    assert mock_live_status.call_count == 2

    freezer.tick(ENERGY_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_live_status.call_count == 3


async def test_energy_info_refresh_ratelimited(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    mock_site_info: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test coordinator refresh handles 429."""

    await setup_platform(hass, normal_config_entry)

    mock_site_info.side_effect = RateLimited({"after": ENERGY_INTERVAL_SECONDS + 10})
    freezer.tick(ENERGY_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_site_info.call_count == 2

    freezer.tick(ENERGY_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Should not call for another 10 seconds
    assert mock_site_info.call_count == 2

    freezer.tick(ENERGY_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_site_info.call_count == 3


async def test_energy_history_refresh_ratelimited(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    mock_energy_history: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test coordinator refresh handles 429."""

    await setup_platform(hass, normal_config_entry)

    mock_energy_history.side_effect = RateLimited(
        {"after": int(ENERGY_HISTORY_INTERVAL.total_seconds() + 10)}
    )
    freezer.tick(ENERGY_HISTORY_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_energy_history.call_count == 1

    freezer.tick(ENERGY_HISTORY_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Should not call for another 10 seconds
    assert mock_energy_history.call_count == 1

    freezer.tick(ENERGY_HISTORY_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_energy_history.call_count == 2


async def test_init_region_issue(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    mock_products: AsyncMock,
    mock_find_server: AsyncMock,
) -> None:
    """Test init with region issue."""

    mock_products.side_effect = InvalidRegion
    await setup_platform(hass, normal_config_entry)
    mock_find_server.assert_called_once()
    assert normal_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_init_region_issue_failed(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    mock_products: AsyncMock,
    mock_find_server: AsyncMock,
) -> None:
    """Test init with unresolvable region issue."""

    mock_products.side_effect = InvalidRegion
    mock_find_server.side_effect = LibraryError
    await setup_platform(hass, normal_config_entry)
    mock_find_server.assert_called_once()
    assert normal_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_signing(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    mock_products: AsyncMock,
) -> None:
    """Tests when a vehicle requires signing."""

    # Make the vehicle require command signing
    products = deepcopy(mock_products.return_value)
    products["response"][0]["command_signing"] = "required"
    mock_products.return_value = products

    with patch(
        "homeassistant.components.tesla_fleet.TeslaFleetApi.get_private_key"
    ) as mock_get_private_key:
        await setup_platform(hass, normal_config_entry)
        mock_get_private_key.assert_called_once()


async def test_bad_implementation(
    hass: HomeAssistant,
    bad_config_entry: MockConfigEntry,
) -> None:
    """Test handling of a bad authentication implementation."""

    await setup_platform(hass, bad_config_entry)
    assert bad_config_entry.state is ConfigEntryState.SETUP_ERROR

    # Ensure reauth flow starts
    assert any(bad_config_entry.async_get_active_flows(hass, {"reauth"}))
    result = await bad_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert not result["errors"]


async def test_vehicle_without_location_scope(
    hass: HomeAssistant,
    expires_at: int,
    mock_vehicle_data: AsyncMock,
) -> None:
    """Test vehicle setup without VEHICLE_LOCATION scope excludes location endpoint."""

    # Create config entry without VEHICLE_LOCATION scope
    config_entry = create_config_entry(
        expires_at,
        [
            Scope.OPENID,
            Scope.OFFLINE_ACCESS,
            Scope.VEHICLE_DEVICE_DATA,
            # Deliberately exclude Scope.VEHICLE_LOCATION
        ],
    )

    await setup_platform(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED

    # Verify that vehicle_data was called without LOCATION_DATA endpoint
    mock_vehicle_data.assert_called()
    call_args = mock_vehicle_data.call_args
    endpoints = call_args.kwargs.get("endpoints", [])

    # Should not include LOCATION_DATA endpoint
    assert VehicleDataEndpoint.LOCATION_DATA not in endpoints

    # Should include other endpoints
    assert VehicleDataEndpoint.CHARGE_STATE in endpoints
    assert VehicleDataEndpoint.CLIMATE_STATE in endpoints
    assert VehicleDataEndpoint.DRIVE_STATE in endpoints
    assert VehicleDataEndpoint.VEHICLE_STATE in endpoints
    assert VehicleDataEndpoint.VEHICLE_CONFIG in endpoints


async def test_vehicle_with_location_scope(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    mock_vehicle_data: AsyncMock,
) -> None:
    """Test vehicle setup with VEHICLE_LOCATION scope includes location endpoint."""
    await setup_platform(hass, normal_config_entry)
    assert normal_config_entry.state is ConfigEntryState.LOADED

    # Verify that vehicle_data was called with LOCATION_DATA endpoint
    mock_vehicle_data.assert_called()
    call_args = mock_vehicle_data.call_args
    endpoints = call_args.kwargs.get("endpoints", [])

    # Should include LOCATION_DATA endpoint when scope is present
    assert VehicleDataEndpoint.LOCATION_DATA in endpoints

    # Should include all other endpoints
    assert VehicleDataEndpoint.CHARGE_STATE in endpoints
    assert VehicleDataEndpoint.CLIMATE_STATE in endpoints
    assert VehicleDataEndpoint.DRIVE_STATE in endpoints
    assert VehicleDataEndpoint.VEHICLE_STATE in endpoints
    assert VehicleDataEndpoint.VEHICLE_CONFIG in endpoints


async def test_oauth_implementation_not_available(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
) -> None:
    """Test that unavailable OAuth implementation raises ConfigEntryNotReady."""
    normal_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.tesla_fleet.async_get_config_entry_implementation",
        side_effect=ImplementationUnavailableError,
    ):
        await hass.config_entries.async_setup(normal_config_entry.entry_id)
        await hass.async_block_till_done()

    assert normal_config_entry.state is ConfigEntryState.SETUP_RETRY

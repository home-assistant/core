"""Test the Tesla Fleet init."""

from unittest.mock import AsyncMock, patch

from aiohttp import RequestInfo
from aiohttp.client_exceptions import ClientResponseError
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
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

from homeassistant.components.tesla_fleet.const import AUTHORIZE_URL
from homeassistant.components.tesla_fleet.coordinator import (
    ENERGY_INTERVAL,
    ENERGY_INTERVAL_SECONDS,
    VEHICLE_INTERVAL,
    VEHICLE_INTERVAL_SECONDS,
    VEHICLE_WAIT,
)
from homeassistant.components.tesla_fleet.models import TeslaFleetData
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_platform
from .const import VEHICLE_ASLEEP, VEHICLE_DATA_ALT

from tests.common import MockConfigEntry, async_fire_time_changed

ERRORS = [
    (InvalidToken, ConfigEntryState.SETUP_ERROR),
    (OAuthExpired, ConfigEntryState.SETUP_ERROR),
    (LoginRequired, ConfigEntryState.SETUP_ERROR),
    (TeslaFleetError, ConfigEntryState.SETUP_RETRY),
]


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


@pytest.mark.parametrize(("side_effect", "state"), ERRORS)
async def test_init_error(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    mock_products: AsyncMock,
    side_effect: TeslaFleetError,
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
        side_effect=ClientResponseError(
            RequestInfo(AUTHORIZE_URL, "POST", {}, AUTHORIZE_URL), None, status=401
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
        side_effect=ClientResponseError(
            RequestInfo(AUTHORIZE_URL, "POST", {}, AUTHORIZE_URL), None, status=400
        ),
    ) as mock_async_ensure_token_valid:
        # Trigger an unmocked function call
        mock_products.side_effect = InvalidRegion
        await setup_platform(hass, normal_config_entry)

        mock_async_ensure_token_valid.assert_called_once()
    assert normal_config_entry.state is ConfigEntryState.SETUP_RETRY


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

    # Then the vehicle goes offline
    mock_vehicle_data.side_effect = VehicleOffline
    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_vehicle_state.assert_not_called()
    mock_vehicle_data.assert_called_once()
    mock_vehicle_data.reset_mock()

    # And stays offline
    mock_vehicle_state.return_value = VEHICLE_ASLEEP
    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_vehicle_state.assert_called_once()
    mock_vehicle_data.assert_not_called()


@pytest.mark.parametrize(("side_effect"), ERRORS)
async def test_vehicle_refresh_error(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    mock_vehicle_data: AsyncMock,
    side_effect: TeslaFleetError,
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
    assert mock_vehicle_data.call_count == 1

    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Should not call for another 10 seconds
    assert mock_vehicle_data.call_count == 1

    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_vehicle_data.call_count == 2


async def test_vehicle_sleep(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    mock_vehicle_data: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test coordinator refresh with an error."""
    await setup_platform(hass, normal_config_entry)
    assert mock_vehicle_data.call_count == 1

    freezer.tick(VEHICLE_WAIT + VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    # Let vehicle sleep, no updates for 15 minutes
    await hass.async_block_till_done()
    assert mock_vehicle_data.call_count == 2

    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    # No polling, call_count should not increase
    await hass.async_block_till_done()
    assert mock_vehicle_data.call_count == 2

    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    # No polling, call_count should not increase
    await hass.async_block_till_done()
    assert mock_vehicle_data.call_count == 2

    freezer.tick(VEHICLE_WAIT)
    async_fire_time_changed(hass)
    # Vehicle didn't sleep, go back to normal
    await hass.async_block_till_done()
    assert mock_vehicle_data.call_count == 3

    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    # Regular polling
    await hass.async_block_till_done()
    assert mock_vehicle_data.call_count == 4

    mock_vehicle_data.return_value = VEHICLE_DATA_ALT
    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    # Vehicle active
    await hass.async_block_till_done()
    assert mock_vehicle_data.call_count == 5

    freezer.tick(VEHICLE_WAIT)
    async_fire_time_changed(hass)
    # Dont let sleep when active
    await hass.async_block_till_done()
    assert mock_vehicle_data.call_count == 6

    freezer.tick(VEHICLE_WAIT)
    async_fire_time_changed(hass)
    # Dont let sleep when active
    await hass.async_block_till_done()
    assert mock_vehicle_data.call_count == 7


# Test Energy Live Coordinator
@pytest.mark.parametrize(("side_effect", "state"), ERRORS)
async def test_energy_live_refresh_error(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    mock_live_status: AsyncMock,
    side_effect: TeslaFleetError,
    state: ConfigEntryState,
) -> None:
    """Test coordinator refresh with an error."""
    mock_live_status.side_effect = side_effect
    await setup_platform(hass, normal_config_entry)
    assert normal_config_entry.state is state


# Test Energy Site Coordinator
@pytest.mark.parametrize(("side_effect", "state"), ERRORS)
async def test_energy_site_refresh_error(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    mock_site_info: AsyncMock,
    side_effect: TeslaFleetError,
    state: ConfigEntryState,
) -> None:
    """Test coordinator refresh with an error."""
    mock_site_info.side_effect = side_effect
    await setup_platform(hass, normal_config_entry)
    assert normal_config_entry.state is state


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

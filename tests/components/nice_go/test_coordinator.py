"""Test the Nice G.O. coordinator."""

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from nice_go import ApiError, AuthFailedError, BarrierState
import pytest

from homeassistant.components.nice_go.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import issue_registry as ir

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_firmware_update_required(
    hass: HomeAssistant,
    mock_nice_go: AsyncMock,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test firmware update required."""

    await setup_integration(hass, mock_config_entry, [])

    await mock_config_entry.runtime_data._parse_barrier(
        BarrierState(
            deviceId="test-device-id",
            reported={
                "displayName": "test-display-name",
                "migrationStatus": "NOT_STARTED",
            },
            desired=None,
            connectionState=None,
            version=None,
            timestamp=None,
        )
    )

    issue = issue_registry.async_get_issue(
        DOMAIN,
        "firmware_update_required_test-device-id",
    )
    assert issue


async def test_update_data_already_authed(
    hass: HomeAssistant,
    mock_nice_go: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test updating data when already authenticated."""

    await setup_integration(hass, mock_config_entry, [Platform.COVER])

    assert mock_nice_go.authenticate_refresh.call_count == 1
    assert mock_nice_go.get_all_barriers.call_count == 1

    mock_nice_go.id_token = "test-id-token"
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)

    assert mock_nice_go.authenticate_refresh.call_count == 1
    assert mock_nice_go.get_all_barriers.call_count == 1


async def test_update_refresh_token(
    hass: HomeAssistant,
    mock_nice_go: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test updating refresh token."""

    await setup_integration(hass, mock_config_entry, [Platform.COVER])

    assert mock_nice_go.authenticate_refresh.call_count == 1
    assert mock_nice_go.get_all_barriers.call_count == 1
    assert mock_nice_go.authenticate.call_count == 0

    mock_nice_go.authenticate.return_value = "new-refresh-token"
    freezer.tick(timedelta(days=30))
    async_fire_time_changed(hass)

    assert mock_nice_go.authenticate_refresh.call_count == 1
    assert mock_nice_go.authenticate.call_count == 1
    assert mock_nice_go.get_all_barriers.call_count == 2
    assert mock_config_entry.data["refresh_token"] == "new-refresh-token"


async def test_update_refresh_token_api_error(
    hass: HomeAssistant,
    mock_nice_go: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test updating refresh token with error."""

    await setup_integration(hass, mock_config_entry, [Platform.COVER])

    assert mock_nice_go.authenticate_refresh.call_count == 1
    assert mock_nice_go.get_all_barriers.call_count == 1
    assert mock_nice_go.authenticate.call_count == 0

    mock_nice_go.authenticate.side_effect = ApiError
    freezer.tick(timedelta(days=30))
    async_fire_time_changed(hass)

    assert mock_nice_go.authenticate_refresh.call_count == 1
    assert mock_nice_go.authenticate.call_count == 1
    assert mock_nice_go.get_all_barriers.call_count == 1
    assert mock_config_entry.data["refresh_token"] == "test-refresh-token"
    assert not mock_config_entry.runtime_data.last_update_success
    assert (
        mock_config_entry.runtime_data.last_exception.__class__.__name__
        == "UpdateFailed"
    )


async def test_update_refresh_token_auth_failed(
    hass: HomeAssistant,
    mock_nice_go: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test updating refresh token with error."""

    await setup_integration(hass, mock_config_entry, [Platform.COVER])

    assert mock_nice_go.authenticate_refresh.call_count == 1
    assert mock_nice_go.get_all_barriers.call_count == 1
    assert mock_nice_go.authenticate.call_count == 0

    mock_nice_go.authenticate.side_effect = AuthFailedError
    freezer.tick(timedelta(days=30))
    async_fire_time_changed(hass)

    assert mock_nice_go.authenticate_refresh.call_count == 1
    assert mock_nice_go.authenticate.call_count == 1
    assert mock_nice_go.get_all_barriers.call_count == 1
    assert mock_config_entry.data["refresh_token"] == "test-refresh-token"
    assert not mock_config_entry.runtime_data.last_update_success
    assert (
        mock_config_entry.runtime_data.last_exception.__class__.__name__
        == "ConfigEntryAuthFailed"
    )
    assert any(mock_config_entry.async_get_active_flows(hass, {"reauth"}))


async def test_client_listen_api_error(
    hass: HomeAssistant,
    mock_nice_go: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test client listen with error."""

    await setup_integration(hass, mock_config_entry, [Platform.COVER])

    mock_nice_go.connect.side_effect = ApiError

    with pytest.raises(ConfigEntryNotReady):
        await mock_config_entry.runtime_data.client_listen()


async def test_on_data_none_parsed(
    hass: HomeAssistant,
    mock_nice_go: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test on data with None parsed."""

    await setup_integration(hass, mock_config_entry, [Platform.COVER])

    mock_config_entry.runtime_data.async_set_updated_data = AsyncMock()

    await mock_config_entry.runtime_data.on_data(
        {
            "data": {
                "devicesStatesUpdateFeed": {
                    "item": {
                        "deviceId": "test-device-id",
                        "desired": '{"key": "value"}',
                        "reported": '{"displayName":"test-display-name", "migrationStatus":"NOT_STARTED"}',
                        "connectionState": {
                            "connected": None,
                            "updatedTimestamp": None,
                        },
                        "version": None,
                        "timestamp": None,
                    }
                }
            }
        }
    )

    assert mock_config_entry.runtime_data.async_set_updated_data.call_count == 0


async def test_on_connected(
    hass: HomeAssistant,
    mock_nice_go: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test on connected."""

    await setup_integration(hass, mock_config_entry, [Platform.COVER])

    mock_nice_go.subscribe = AsyncMock()

    await mock_config_entry.runtime_data.on_connected()

    assert mock_nice_go.subscribe.call_count == 1


async def test_parse_barrier_no_connection_state(
    hass: HomeAssistant,
    mock_nice_go: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test parsing barrier with no connection state."""

    await setup_integration(hass, mock_config_entry, [Platform.COVER])

    parsed_barrier = await mock_config_entry.runtime_data._parse_barrier(
        BarrierState(
            deviceId="test-device-id",
            reported={
                "displayName": "test-display-name",
                "migrationStatus": "DONE",
                "barrierStatus": "1,100,0",
                "deviceFwVersion": "1.0.0",
                "lightStatus": "1,100",
            },
            desired=None,
            connectionState=None,
            version=None,
            timestamp=None,
        )
    )

    assert not parsed_barrier.connected

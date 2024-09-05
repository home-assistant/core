"""Test Nice G.O. init."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

from freezegun.api import FrozenDateTimeFactory
from nice_go import ApiError, AuthFailedError, Barrier, BarrierState
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.nice_go.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_unload_entry(
    hass: HomeAssistant, mock_nice_go: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test the unload entry."""

    await setup_integration(hass, mock_config_entry, [])
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("side_effect", "entry_state"),
    [
        (
            AuthFailedError(),
            ConfigEntryState.SETUP_ERROR,
        ),
        (ApiError(), ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_setup_failure(
    hass: HomeAssistant,
    mock_nice_go: AsyncMock,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception,
    entry_state: ConfigEntryState,
) -> None:
    """Test reauth trigger setup."""

    mock_nice_go.authenticate_refresh.side_effect = side_effect

    await setup_integration(hass, mock_config_entry, [])
    assert mock_config_entry.state is entry_state


async def test_firmware_update_required(
    hass: HomeAssistant,
    mock_nice_go: AsyncMock,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test firmware update required."""

    mock_nice_go.get_all_barriers.return_value = [
        Barrier(
            id="test-device-id",
            type="test-type",
            controlLevel="test-control-level",
            attr=[{"key": "test-attr", "value": "test-value"}],
            state=BarrierState(
                deviceId="test-device-id",
                reported={
                    "displayName": "test-display-name",
                    "migrationStatus": "NOT_STARTED",
                },
                desired=None,
                connectionState=None,
                version=None,
                timestamp=None,
            ),
            api=mock_nice_go,
        )
    ]

    await setup_integration(hass, mock_config_entry, [])

    issue = issue_registry.async_get_issue(
        DOMAIN,
        "firmware_update_required_test-device-id",
    )
    assert issue


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
    freezer.tick(timedelta(days=30, seconds=1))
    async_fire_time_changed(hass)
    assert await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_nice_go.authenticate_refresh.call_count == 1
    assert mock_nice_go.authenticate.call_count == 1
    assert mock_nice_go.get_all_barriers.call_count == 2
    assert mock_config_entry.data["refresh_token"] == "new-refresh-token"


async def test_update_refresh_token_api_error(
    hass: HomeAssistant,
    mock_nice_go: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test updating refresh token with error."""

    await setup_integration(hass, mock_config_entry, [Platform.COVER])

    assert mock_nice_go.authenticate_refresh.call_count == 1
    assert mock_nice_go.get_all_barriers.call_count == 1
    assert mock_nice_go.authenticate.call_count == 0

    mock_nice_go.authenticate.side_effect = ApiError
    freezer.tick(timedelta(days=30))
    async_fire_time_changed(hass)
    assert not await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_nice_go.authenticate_refresh.call_count == 1
    assert mock_nice_go.authenticate.call_count == 1
    assert mock_nice_go.get_all_barriers.call_count == 1
    assert mock_config_entry.data["refresh_token"] == "test-refresh-token"
    assert "API error" in caplog.text


async def test_update_refresh_token_auth_failed(
    hass: HomeAssistant,
    mock_nice_go: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test updating refresh token with error."""

    await setup_integration(hass, mock_config_entry, [Platform.COVER])

    assert mock_nice_go.authenticate_refresh.call_count == 1
    assert mock_nice_go.get_all_barriers.call_count == 1
    assert mock_nice_go.authenticate.call_count == 0

    mock_nice_go.authenticate.side_effect = AuthFailedError
    freezer.tick(timedelta(days=30))
    async_fire_time_changed(hass)
    assert not await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_nice_go.authenticate_refresh.call_count == 1
    assert mock_nice_go.authenticate.call_count == 1
    assert mock_nice_go.get_all_barriers.call_count == 1
    assert mock_config_entry.data["refresh_token"] == "test-refresh-token"
    assert "Authentication failed" in caplog.text


async def test_client_listen_api_error(
    hass: HomeAssistant,
    mock_nice_go: AsyncMock,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test client listen with error."""

    mock_nice_go.connect.side_effect = ApiError

    await setup_integration(hass, mock_config_entry, [Platform.COVER])

    assert "API error" in caplog.text

    mock_nice_go.connect.side_effect = None

    freezer.tick(timedelta(seconds=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_nice_go.connect.call_count == 2


async def test_on_data_none_parsed(
    hass: HomeAssistant,
    mock_nice_go: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test on data with None parsed."""

    mock_nice_go.event = MagicMock()

    await setup_integration(hass, mock_config_entry, [Platform.COVER])

    await mock_nice_go.event.call_args[0][0](
        {
            "data": {
                "devicesStatesUpdateFeed": {
                    "item": {
                        "deviceId": "1",
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

    assert hass.states.get("cover.test_garage_1") == snapshot


async def test_on_connected(
    hass: HomeAssistant,
    mock_nice_go: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test on connected."""

    mock_nice_go.event = MagicMock()

    await setup_integration(hass, mock_config_entry, [Platform.COVER])

    assert mock_nice_go.event.call_count == 2

    mock_nice_go.subscribe = AsyncMock()
    await mock_nice_go.event.call_args_list[0][0][0]()

    assert mock_nice_go.subscribe.call_count == 1


async def test_no_connection_state(
    hass: HomeAssistant,
    mock_nice_go: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test parsing barrier with no connection state."""

    mock_nice_go.event = MagicMock()

    await setup_integration(hass, mock_config_entry, [Platform.COVER])

    assert mock_nice_go.event.call_count == 2

    await mock_nice_go.event.call_args[0][0](
        {
            "data": {
                "devicesStatesUpdateFeed": {
                    "item": {
                        "deviceId": "1",
                        "desired": '{"key": "value"}',
                        "reported": '{"displayName":"Test Garage 1", "migrationStatus":"DONE", "barrierStatus": "1,100,0", "deviceFwVersion": "1.0.0", "lightStatus": "1,100", "vcnMode": false}',
                        "connectionState": None,
                        "version": None,
                        "timestamp": None,
                    }
                }
            }
        }
    )

    assert hass.states.get("cover.test_garage_1").state == "unavailable"

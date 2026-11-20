"""Test Nice G.O. init."""

import asyncio
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from nice_go import ApiError, AuthFailedError, Barrier, BarrierState
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.nice_go.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import CONF_EMAIL, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir

from . import setup_integration


async def test_unload_entry(
    hass: HomeAssistant, mock_nice_go: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test the unload entry."""

    await setup_integration(hass, mock_config_entry, [])
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_failure_api_error(
    hass: HomeAssistant,
    mock_nice_go: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauth trigger setup."""

    mock_nice_go.get_all_barriers.side_effect = ApiError()

    await setup_integration(hass, mock_config_entry, [])
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_auth_api_error(
    hass: HomeAssistant,
    mock_nice_go: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauth trigger setup."""

    mock_nice_go.authenticate_refresh.side_effect = ApiError()

    await setup_integration(hass, mock_config_entry, [])
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_failure_auth_failed(
    hass: HomeAssistant,
    mock_nice_go: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauth trigger setup."""

    mock_nice_go.authenticate_refresh.side_effect = AuthFailedError()

    await setup_integration(hass, mock_config_entry, [])
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR

    assert any(mock_config_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))


def _barrier_needing_firmware_update(api: AsyncMock) -> Barrier:
    """Return a barrier whose firmware migration has not started."""
    return Barrier(
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
            connectionState=None,
            version=None,
            timestamp=None,
        ),
        api=api,
    )


async def test_firmware_update_required(
    hass: HomeAssistant,
    mock_nice_go: AsyncMock,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test firmware update required."""

    mock_nice_go.get_all_barriers.return_value = [
        _barrier_needing_firmware_update(mock_nice_go)
    ]

    await setup_integration(hass, mock_config_entry, [])

    issue_id = f"firmware_update_required_{mock_config_entry.entry_id}_test-device-id"
    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue
    assert issue.config_entry_id == mock_config_entry.entry_id

    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert not issue_registry.async_get_issue(DOMAIN, issue_id)


async def test_firmware_update_required_shared_barrier(
    hass: HomeAssistant,
    mock_nice_go: AsyncMock,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test each account sharing a barrier gets its own firmware issue."""

    mock_nice_go.get_all_barriers.return_value = [
        _barrier_needing_firmware_update(mock_nice_go)
    ]
    other_entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="0123456789abcdef0123456789abcdef",
        title="other-email",
        data={**mock_config_entry.data, CONF_EMAIL: "other-email"},
        version=1,
        unique_id="other-email",
    )

    await setup_integration(hass, mock_config_entry, [])
    await setup_integration(hass, other_entry, [])

    issue_id = f"firmware_update_required_{mock_config_entry.entry_id}_test-device-id"
    other_issue_id = f"firmware_update_required_{other_entry.entry_id}_test-device-id"
    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue
    assert issue.config_entry_id == mock_config_entry.entry_id
    other_issue = issue_registry.async_get_issue(DOMAIN, other_issue_id)
    assert other_issue
    assert other_issue.config_entry_id == other_entry.entry_id

    issue_registry.async_ignore(DOMAIN, other_issue_id, True)

    # Removing one account must not delete the other account's issue
    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert not issue_registry.async_get_issue(DOMAIN, issue_id)
    other_issue = issue_registry.async_get_issue(DOMAIN, other_issue_id)
    assert other_issue
    assert other_issue.config_entry_id == other_entry.entry_id
    assert other_issue.dismissed_version is not None


def _state_update(reported: str) -> dict[str, Any]:
    """Return a websocket state update for barrier 1."""
    return {
        "data": {
            "devicesStatesUpdateFeed": {
                "item": {
                    "deviceId": "1",
                    "desired": '{"key": "value"}',
                    "reported": reported,
                    "connectionState": None,
                    "version": None,
                    "timestamp": None,
                }
            }
        }
    }


async def test_firmware_update_required_resolved(
    hass: HomeAssistant,
    mock_nice_go: AsyncMock,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the firmware issue is deleted once the migration has started."""

    mock_nice_go.listen = MagicMock()

    await setup_integration(hass, mock_config_entry, [Platform.COVER])
    on_data = mock_nice_go.listen.call_args_list[1][0][1]
    issue_id = f"firmware_update_required_{mock_config_entry.entry_id}_1"

    await on_data(
        _state_update(
            '{"displayName":"Test Garage 1", "migrationStatus":"NOT_STARTED"}'
        )
    )
    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue
    assert issue.config_entry_id == mock_config_entry.entry_id

    await on_data(
        _state_update(
            '{"displayName":"Test Garage 1",'
            ' "migrationStatus":"DONE",'
            ' "barrierStatus": "1,100,0",'
            ' "deviceFwVersion": "1.0.0",'
            ' "lightStatus": "1,100",'
            ' "vcnMode": false}'
        )
    )
    assert not issue_registry.async_get_issue(DOMAIN, issue_id)


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
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert any(mock_config_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))


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


async def test_client_listen_auth_failed(
    hass: HomeAssistant,
    mock_nice_go: AsyncMock,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test client listen with error."""

    mock_nice_go.connect.side_effect = AuthFailedError

    await setup_integration(hass, mock_config_entry, [Platform.COVER])

    assert (
        "Got auth failed when connecting to websocket, trying to reauthenticate"
        in caplog.text
    )
    assert mock_nice_go.authenticate_refresh.call_count == 2


async def test_on_data_none_parsed(
    hass: HomeAssistant,
    mock_nice_go: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test on data with None parsed."""

    mock_nice_go.listen = MagicMock()

    await setup_integration(hass, mock_config_entry, [Platform.COVER])

    await mock_nice_go.listen.call_args_list[1][0][1](
        {
            "data": {
                "devicesStatesUpdateFeed": {
                    "item": {
                        "deviceId": "1",
                        "desired": '{"key": "value"}',
                        "reported": (
                            '{"displayName":"test-display-name",'
                            ' "migrationStatus":"NOT_STARTED"}'
                        ),
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

    mock_nice_go.listen = MagicMock()

    await setup_integration(hass, mock_config_entry, [Platform.COVER])

    assert mock_nice_go.listen.call_count == 3

    mock_nice_go.subscribe = AsyncMock()
    await mock_nice_go.listen.call_args_list[0][0][1]()

    assert mock_nice_go.subscribe.call_count == 1


async def test_on_connection_lost(
    hass: HomeAssistant,
    mock_nice_go: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test on connection lost."""

    mock_nice_go.listen = MagicMock()

    await setup_integration(hass, mock_config_entry, [Platform.COVER])

    assert mock_nice_go.listen.call_count == 3

    with patch("homeassistant.components.nice_go.coordinator.RECONNECT_DELAY", 0):
        await mock_nice_go.listen.call_args_list[2][0][1](
            {"exception": ValueError("test")}
        )

    assert hass.states.get("cover.test_garage_1").state == "unavailable"

    # Now fire connected

    mock_nice_go.subscribe = AsyncMock()

    await mock_nice_go.listen.call_args_list[0][0][1]()

    assert mock_nice_go.subscribe.call_count == 1

    assert hass.states.get("cover.test_garage_1").state == "closed"


async def test_on_connection_lost_reconnect(
    hass: HomeAssistant,
    mock_nice_go: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test on connection lost with reconnect."""

    mock_nice_go.listen = MagicMock()

    await setup_integration(hass, mock_config_entry, [Platform.COVER])

    assert mock_nice_go.listen.call_count == 3

    assert hass.states.get("cover.test_garage_1").state == "closed"

    with patch("homeassistant.components.nice_go.coordinator.RECONNECT_DELAY", 0):
        await mock_nice_go.listen.call_args_list[2][0][1](
            {"exception": ValueError("test")}
        )

    assert hass.states.get("cover.test_garage_1").state == "unavailable"


async def test_no_connection_state(
    hass: HomeAssistant,
    mock_nice_go: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test parsing barrier with no connection state."""

    mock_nice_go.listen = MagicMock()

    await setup_integration(hass, mock_config_entry, [Platform.COVER])

    assert mock_nice_go.listen.call_count == 3

    await mock_nice_go.listen.call_args_list[1][0][1](
        {
            "data": {
                "devicesStatesUpdateFeed": {
                    "item": {
                        "deviceId": "1",
                        "desired": '{"key": "value"}',
                        "reported": (
                            '{"displayName":"Test Garage 1",'
                            ' "migrationStatus":"DONE",'
                            ' "barrierStatus": "1,100,0",'
                            ' "deviceFwVersion": "1.0.0",'
                            ' "lightStatus": "1,100",'
                            ' "vcnMode": false}'
                        ),
                        "connectionState": None,
                        "version": None,
                        "timestamp": None,
                    }
                }
            }
        }
    )

    assert hass.states.get("cover.test_garage_1").state == "open"


async def test_connection_attempts_exhausted(
    hass: HomeAssistant,
    mock_nice_go: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test connection attempts exhausted."""

    mock_nice_go.connect.side_effect = ApiError

    with (
        patch("homeassistant.components.nice_go.coordinator.RECONNECT_ATTEMPTS", 1),
        patch("homeassistant.components.nice_go.coordinator.RECONNECT_DELAY", 0),
    ):
        await setup_integration(hass, mock_config_entry, [Platform.COVER])

    assert "API error" in caplog.text
    assert "Error requesting Nice G.O. data" in caplog.text


async def test_reconnect_hass_stopping(
    hass: HomeAssistant,
    mock_nice_go: AsyncMock,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test reconnect with hass stopping."""

    mock_nice_go.listen = MagicMock()
    mock_nice_go.connect.side_effect = ApiError

    wait_for_hass = asyncio.Event()

    @callback
    def _async_ha_stop(event: Event) -> None:
        """Stop reconnecting if hass is stopping."""
        wait_for_hass.set()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_ha_stop)

    with (
        patch("homeassistant.components.nice_go.coordinator.RECONNECT_DELAY", 0.1),
        patch("homeassistant.components.nice_go.coordinator.RECONNECT_ATTEMPTS", 20),
    ):
        await setup_integration(hass, mock_config_entry, [Platform.COVER])
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await wait_for_hass.wait()
        await hass.async_block_till_done(wait_background_tasks=True)

        assert mock_nice_go.connect.call_count < 10

        assert len(hass._background_tasks) == 0

        assert "API error" in caplog.text
        assert (
            "Failed to connect to the websocket, reconnect attempts exhausted"
            not in caplog.text
        )

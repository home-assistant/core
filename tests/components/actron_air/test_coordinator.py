"""Tests for the Actron Air coordinator."""

from unittest.mock import AsyncMock, patch

from actron_neo_api import ActronAirAPIError, ActronAirAuthError
from actron_neo_api.rt import (
    RealtimeConnectionEvent,
    RealtimeConnectionState,
    RealtimeEventKind,
    RealtimeTransportType,
)
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.actron_air.coordinator import (
    POLL_INTERVAL,
    PUSH_POLL_INTERVAL,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed

CLIMATE_ENTITY_ID = "climate.test_system"


def connection_event(
    state: RealtimeConnectionState,
    previous_state: RealtimeConnectionState | None,
) -> RealtimeConnectionEvent:
    """Build a realtime connection state transition."""
    return RealtimeConnectionEvent(
        transport=RealtimeTransportType.MQTT,
        kind=RealtimeEventKind.CONNECTION,
        state=state,
        previous_state=previous_state,
    )


async def test_coordinator_update_auth_error(
    hass: HomeAssistant,
    mock_actron_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test coordinator handles auth error during update."""
    with patch("homeassistant.components.actron_air.PLATFORMS", [Platform.CLIMATE]):
        await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    mock_actron_api.update_status.side_effect = ActronAirAuthError("Auth expired")

    freezer.tick(PUSH_POLL_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # ConfigEntryAuthFailed triggers a reauth flow
    assert len(hass.config_entries.flow.async_progress()) == 1


async def test_coordinator_update_api_error(
    hass: HomeAssistant,
    mock_actron_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test coordinator handles API error during update."""
    with patch("homeassistant.components.actron_air.PLATFORMS", [Platform.CLIMATE]):
        await setup_integration(hass, mock_config_entry)

    mock_actron_api.update_status.side_effect = ActronAirAPIError("API error")

    freezer.tick(PUSH_POLL_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # UpdateFailed sets last_update_success to False on the coordinator
    coordinator = next(
        iter(mock_config_entry.runtime_data.system_coordinators.values())
    )
    assert coordinator.last_update_success is False
    assert hass.states.get(CLIMATE_ENTITY_ID).state == STATE_UNAVAILABLE


async def test_coordinator_update_status_none(
    hass: HomeAssistant,
    mock_actron_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test coordinator handles get_status returning None."""
    with patch("homeassistant.components.actron_air.PLATFORMS", [Platform.CLIMATE]):
        await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    mock_actron_api.state_manager.get_status.return_value = None

    freezer.tick(PUSH_POLL_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # UpdateFailed sets last_update_success to False on the coordinator
    coordinator = next(
        iter(mock_config_entry.runtime_data.system_coordinators.values())
    )
    assert coordinator.last_update_success is False


async def test_push_update(
    hass: HomeAssistant,
    mock_actron_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a realtime push update reaches entities without polling."""
    with patch("homeassistant.components.actron_air.PLATFORMS", [Platform.CLIMATE]):
        await setup_integration(hass, mock_config_entry)

    serial, push_callback = mock_actron_api.subscribe_system_updates.call_args.args
    assert serial == "123456"

    assert hass.states.get(CLIMATE_ENTITY_ID).attributes["current_temperature"] == 22.0

    status = mock_actron_api.state_manager.get_status.return_value
    status.master_info.live_temp_c = 25.5
    push_callback(status)
    await hass.async_block_till_done()

    assert hass.states.get(CLIMATE_ENTITY_ID).attributes["current_temperature"] == 25.5


async def test_push_update_offline(
    hass: HomeAssistant,
    mock_actron_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test entities become unavailable when the system reports itself offline."""
    with patch("homeassistant.components.actron_air.PLATFORMS", [Platform.CLIMATE]):
        await setup_integration(hass, mock_config_entry)

    assert hass.states.get(CLIMATE_ENTITY_ID).state != STATE_UNAVAILABLE

    _, push_callback = mock_actron_api.subscribe_system_updates.call_args.args
    status = mock_actron_api.state_manager.get_status.return_value
    status.is_online = False
    push_callback(status)
    await hass.async_block_till_done()

    assert hass.states.get(CLIMATE_ENTITY_ID).state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("previous_state", "expect_refresh"),
    [
        pytest.param(RealtimeConnectionState.RECONNECTING, True, id="reconnecting"),
        pytest.param(RealtimeConnectionState.DISCONNECTED, True, id="disconnected"),
        pytest.param(RealtimeConnectionState.ERROR, True, id="error"),
        pytest.param(RealtimeConnectionState.CONNECTING, False, id="initial_connect"),
    ],
)
async def test_reconnect_resync(
    hass: HomeAssistant,
    mock_actron_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    previous_state: RealtimeConnectionState,
    expect_refresh: bool,
) -> None:
    """Test the coordinator only resyncs after the transport recovers from an outage."""
    with patch("homeassistant.components.actron_air.PLATFORMS", [Platform.CLIMATE]):
        await setup_integration(hass, mock_config_entry)

    connection_callback = mock_actron_api.subscribe_connection_state.call_args.args[0]
    mock_actron_api.update_status.reset_mock()

    await connection_callback(
        connection_event(RealtimeConnectionState.CONNECTED, previous_state)
    )
    # The coordinator debounces refresh requests, so let the debouncer fire.
    freezer.tick(POLL_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (mock_actron_api.update_status.call_count > 0) is expect_refresh


async def test_push_unavailable_falls_back_to_polling(
    hass: HomeAssistant,
    mock_actron_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the coordinator polls on the short interval when push is unavailable."""
    mock_actron_api.start_push.return_value = False

    with patch("homeassistant.components.actron_air.PLATFORMS", [Platform.CLIMATE]):
        await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_actron_api.subscribe_system_updates.assert_not_called()
    mock_actron_api.subscribe_connection_state.assert_not_called()

    mock_actron_api.update_status.reset_mock()
    freezer.tick(POLL_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_actron_api.update_status.call_count == 1

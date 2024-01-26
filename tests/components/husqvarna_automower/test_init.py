"""Tests for init module."""
import http
import time
from unittest.mock import patch

from aiohttp import ClientError
import pytest

from homeassistant.components.husqvarna_automower.const import OAUTH2_TOKEN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util

from .common import setup_platform

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker

SCAN_INTERVAL = dt_util.dt.timedelta(60)
TEST_MOWER_ID = "c7233734-b219-4287-a173-08e3643f89f0"


async def test_async_setup_raises_entry_not_ready(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test that it throws ConfigEntryNotReady when exception occurs during setup."""
    config_entry = mock_config_entry
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        side_effect=ClientError("API unavailable"),
    ), patch(
        "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation",
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.SETUP_RETRY
        assert await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_load_unload(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test load and unload."""

    entry = await setup_platform(hass, mock_config_entry)
    assert entry.state is ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_callback(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test load and unload."""

    def side_effect_function():
        hass.components.husqvarna_automower.coordinator.AutomowerDataUpdateCoordinator.async_set_updated_data(
            hass, 1
        )

    with patch(
        "homeassistant.components.husqvarna_automower.coordinator.AutomowerDataUpdateCoordinator.callback",
    ):
        entry = await setup_platform(hass, mock_config_entry)
        assert entry.state is ConfigEntryState.LOADED
        assert hass.components.husqvarna_automower.coordinator.AutomowerDataUpdateCoordinator.callback(
            1
        )
        # side_effect_function()


# @pytest.mark.parametrize("expires_at", [time.time() - 3600], ids=["expired"])
# async def test_expired_token_refresh_success(
#     hass: HomeAssistant,
#     aioclient_mock: AiohttpClientMocker,
#     mock_config_entry,
#     load_jwt_fixture,
# ) -> None:
#     """Test expired token is refreshed."""

#     aioclient_mock.clear_requests()
#     aioclient_mock.post(
#         OAUTH2_TOKEN,
#         json={
#             "access_token": "updated-access-token",
#             "refresh_token": "updated-refresh-token",
#             "expires_at": time.time() - 3600,
#             "expires_in": 86399,
#         },
#     )

#     await setup_platform(hass, mock_config_entry)

#     entries = hass.config_entries.async_entries(DOMAIN)
#     assert len(entries) == 1
#     assert entries[0].state is ConfigEntryState.LOADED
#     assert entries[0].data["token"]["access_token"] == "updated-access-token"
#     assert entries[0].data["token"]["expires_in"] == 86399


@pytest.mark.parametrize(
    ("expires_at", "status", "expected_state"),
    [
        (
            time.time() - 3600,
            http.HTTPStatus.UNAUTHORIZED,
            ConfigEntryState.SETUP_RETRY,  # Will trigger reauth in the future
        ),
        (
            time.time() - 3600,
            http.HTTPStatus.INTERNAL_SERVER_ERROR,
            ConfigEntryState.SETUP_RETRY,
        ),
    ],
    ids=["unauthorized", "internal_server_error"],
)
async def test_expired_token_refresh_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    load_jwt_fixture,
    aioclient_mock: AiohttpClientMocker,
    status: http.HTTPStatus,
    expected_state: ConfigEntryState,
) -> None:
    """Test failure while refreshing token with a transient error."""

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        OAUTH2_TOKEN,
        status=status,
    )

    await setup_platform(hass, mock_config_entry)

    assert mock_config_entry.state is expected_state


# @pytest.mark.parametrize(
#     ("activity", "state", "target_state"),
#     [
#         ("PARKED_IN_CS", "RESTRICTED", LawnMowerActivity.DOCKED),
#     ],
# )
# async def test_websocket(
#     hass: HomeAssistant, setup_entity, activity, state, target_state, mock_wled
# ) -> None:
#     """Test WebSocket connection."""
#     state = hass.states.get("lawn_mower.test_mower_1")
#     assert state is not None
#     assert state.state == LawnMowerActivity.DOCKED

#     # There is no Future in place yet...
#     #assert mock_wled.listen.call_count == 1
#     connection_connected = asyncio.Future()
#     connection_finished = asyncio.Future()

#     async def connect(callback: Callable[[MowerData], None]):
#         connection_connected.set_result(callback)
#         await connection_finished

#     mock_wled.listen.side_effect = connect
#     # Mock out the event bus
#     mock_bus = MagicMock()
#     hass.bus = mock_bus

#     # # Next refresh it should connect
#     async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
#     callback = await connection_connected

#     # # Connected to WebSocket, disconnect not called
#     # # listening for Home Assistant to stop
#     # assert mock_wled.connect.call_count == 2
#     # assert mock_wled.listen.call_count == 2
#     # assert mock_wled.disconnect.call_count == 1
#     # assert mock_bus.async_listen_once.call_count == 1
#     # assert (
#     #     mock_bus.async_listen_once.call_args_list[0][0][0] == EVENT_HOMEASSISTANT_STOP
#     # )
#     # assert (
#     #     mock_bus.async_listen_once.call_args_list[0][0][1].__name__ == "close_websocket"
#     # )
#     # assert mock_bus.async_listen_once.return_value.call_count == 0

#     # Send update from WebSocket
#     updated_device: MowerData = deepcopy(mock_wled._async_update_data.return_value)

#     mower:MowerAttributes=updated_device[TEST_MOWER_ID]
#     #print(updated_device[TEST_MOWER_ID].system)
#     print(mower.mower.activity)
#     mower.mower.activity = "MOWING"
#     print(updated_device)
#     callback(updated_device)
#     await hass.async_block_till_done(

#     )

#     # Check if entity updated
#     state = hass.states.get("light.wled_websocket")
#     assert state
#     assert state.state == STATE_OFF

#     # Resolve Future with a connection losed.
#     connection_finished.set_exception(WLEDConnectionClosedError)
#     await hass.async_block_till_done()

#     # Disconnect called, unsubbed Home Assistant stop listener
#     assert mock_wled.disconnect.call_count == 2
#     assert mock_bus.async_listen_once.return_value.call_count == 1

#     # Light still available, as polling takes over
#     state = hass.states.get("light.wled_websocket")
#     assert state
#     assert state.state == STATE_OFF

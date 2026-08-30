"""Test init for Anova."""

import asyncio
from contextlib import suppress
from datetime import timedelta
import logging
from unittest.mock import AsyncMock, patch

from anova_wifi import (
    AnovaApi,
    APCUpdate,
    APCUpdateBinary,
    APCUpdateSensor,
    APCWifiDevice,
    InvalidLogin,
    NoDevicesFound,
    WebsocketFailure,
)
from anova_wifi.exceptions import LoginUnreachable
import pytest

from homeassistant.components.anova.const import DOMAIN
from homeassistant.components.anova.coordinator import (
    DEVICE_STALE_THRESHOLD,
    RECONNECT_RETRY_DELAY,
    AnovaCoordinator,
    AnovaData,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_DEVICES, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import async_init_integration, create_entry
from .conftest import DUMMY_ID, MockedAnovaWebsocketHandler

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_async_setup_entry(hass: HomeAssistant, anova_api: AnovaApi) -> None:
    """Test a successful setup entry."""
    await async_init_integration(hass)
    state = hass.states.get("sensor.anova_precision_cooker_mode")
    assert state is not None
    assert state.state == "idle"


async def test_wrong_login(
    hass: HomeAssistant, anova_api_wrong_login: AnovaApi
) -> None:
    """Test for setup failure if connection to Anova is missing."""
    entry = create_entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_unload_entry(hass: HomeAssistant, anova_api: AnovaApi) -> None:
    """Test successful unload of entry."""
    entry = await async_init_integration(hass)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_no_devices_found(
    hass: HomeAssistant,
    anova_api_no_devices: AnovaApi,
) -> None:
    """Test when there don't seem to be any devices on the account."""
    entry = await async_init_integration(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_websocket_failure(
    hass: HomeAssistant,
    anova_api_websocket_failure: AnovaApi,
) -> None:
    """Test that we successfully handle a websocket failure on setup."""
    entry = await async_init_integration(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_websocket_reconnects_on_disconnect(
    hass: HomeAssistant,
    anova_api: AnovaApi,
) -> None:
    """Test that the integration automatically reconnects when the websocket drops."""
    entry = await async_init_integration(hass)

    initial_call_count = entry.runtime_data.api.create_websocket.call_count
    ws_handler = entry.runtime_data.api.websocket_handler
    assert isinstance(ws_handler, MockedAnovaWebsocketHandler)

    ws_handler.simulate_disconnect()
    # First call: _wait_for_disconnect completes and the done callback schedules
    # async_request_refresh as a background task.
    # Second call: the background task runs async_request_refresh -> _async_update_data
    # -> _async_reconnect.
    await hass.async_block_till_done()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.runtime_data.api.create_websocket.call_count == initial_call_count + 1
    new_ws_handler = entry.runtime_data.api.websocket_handler
    assert new_ws_handler is not ws_handler
    for coordinator in entry.runtime_data.coordinators:
        device = new_ws_handler.devices.get(coordinator.device_unique_id)
        assert device is not None
        assert coordinator.anova_device is device


async def test_websocket_reconnect_reloads_entry_when_new_device_appears(
    hass: HomeAssistant,
    anova_api: AnovaApi,
) -> None:
    """Test a reconnect that discovers an unset-up device triggers a reload."""
    entry = await async_init_integration(hass)
    ws_handler = entry.runtime_data.api.websocket_handler
    assert isinstance(ws_handler, MockedAnovaWebsocketHandler)

    original_side_effect = entry.runtime_data.api.create_websocket.side_effect
    new_device_id = "anova_id_2"

    async def create_websocket_with_new_device() -> None:
        await original_side_effect()
        entry.runtime_data.api.websocket_handler.devices[new_device_id] = APCWifiDevice(
            cooker_id=new_device_id,
            type="a5",
            paired_at="2023-08-12T02:33:20.917716Z",
            name="Anova Precision Cooker",
        )

    entry.runtime_data.api.create_websocket.side_effect = (
        create_websocket_with_new_device
    )
    reload_mock = AsyncMock()
    with patch.object(hass.config_entries, "async_reload", reload_mock):
        ws_handler.simulate_disconnect()
        await hass.async_block_till_done()
        await hass.async_block_till_done(wait_background_tasks=True)

    reload_mock.assert_awaited_once_with(entry.entry_id)


async def test_websocket_listener_exception_is_consumed_and_triggers_reconnect(
    hass: HomeAssistant,
    anova_api: AnovaApi,
) -> None:
    """Test a message listener that ends in an exception still reconnects.

    The done callback must fetch the task exception so anova_wifi listener
    errors are logged instead of surfacing as an unhandled task exception.
    """
    entry = await async_init_integration(hass)
    ws_handler = entry.runtime_data.api.websocket_handler
    assert isinstance(ws_handler, MockedAnovaWebsocketHandler)

    initial_call_count = entry.runtime_data.api.create_websocket.call_count
    original_listener = ws_handler._message_listener

    async def failing_listener() -> None:
        raise WebsocketFailure("transport died")

    ws_handler._message_listener = asyncio.create_task(failing_listener())
    entry.runtime_data.coordinators[0].async_start_disconnect_listener()

    await hass.async_block_till_done()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.runtime_data.api.create_websocket.call_count == initial_call_count + 1

    original_listener.cancel()
    with suppress(asyncio.CancelledError):
        await original_listener


async def test_coordinator_replays_cached_device_state_at_attach(
    hass: HomeAssistant,
    anova_api: AnovaApi,
) -> None:
    """Test a state pushed before attach is replayed onto the coordinator."""
    entry = create_entry(hass)
    entry.runtime_data = AnovaData(api_jwt="jwt", coordinators=[], api=anova_api)

    device = APCWifiDevice(
        cooker_id=DUMMY_ID,
        type="a5",
        paired_at="2023-08-12T02:33:20.917716Z",
        name="Anova Precision Cooker",
    )
    update = APCUpdate(
        sensor=APCUpdateSensor(
            cook_time=3600,
            target_temperature=55.5,
            cook_time_remaining=3600,
            firmware_version="2.2.0",
        ),
        binary_sensor=APCUpdateBinary(cooking=True),
    )
    device.last_update = update

    coordinator = AnovaCoordinator(hass, entry, device)

    assert coordinator.data == update
    assert coordinator.pending_target_temperature == update.sensor.target_temperature
    assert coordinator.pending_cook_time_seconds == update.sensor.cook_time


async def test_websocket_reconnects_after_auth_expiry(
    hass: HomeAssistant,
    anova_api: AnovaApi,
) -> None:
    """Test that the integration re-authenticates and reconnects when auth has expired."""
    entry = await async_init_integration(hass)

    ws_handler = entry.runtime_data.api.websocket_handler
    assert isinstance(ws_handler, MockedAnovaWebsocketHandler)

    # Simulate: first create_websocket call fails (stale JWT), then succeeds after re-auth.
    original_side_effect = entry.runtime_data.api.create_websocket.side_effect
    call_count = 0

    async def create_websocket_after_reauth():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise WebsocketFailure("Token expired")
        await original_side_effect()

    entry.runtime_data.api.create_websocket.side_effect = create_websocket_after_reauth
    entry.runtime_data.api.authenticate = AsyncMock()

    ws_handler.simulate_disconnect()
    await hass.async_block_till_done()
    await hass.async_block_till_done(wait_background_tasks=True)

    entry.runtime_data.api.authenticate.assert_called_once()
    assert call_count == 2
    new_ws_handler = entry.runtime_data.api.websocket_handler
    assert new_ws_handler is not ws_handler


@pytest.mark.parametrize(
    ("ws_side_effect", "auth_side_effect", "expected_log"),
    [
        pytest.param(
            NoDevicesFound("offline"),
            None,
            "Failed to reconnect to Anova websocket",
            id="no_devices_found",
        ),
        pytest.param(
            WebsocketFailure("expired"),
            InvalidLogin("bad creds"),
            "Anova re-authentication failed",
            id="invalid_login_on_reauth",
        ),
        pytest.param(
            WebsocketFailure("expired"),
            LoginUnreachable("server down"),
            "Failed to re-authenticate with Anova",
            id="login_unreachable_on_reauth",
        ),
        pytest.param(
            WebsocketFailure("expired"),
            None,
            "Failed to reconnect to Anova websocket",
            id="websocket_failure_after_reauth",
        ),
    ],
)
async def test_websocket_reconnect_failure_paths(
    hass: HomeAssistant,
    anova_api: AnovaApi,
    caplog: pytest.LogCaptureFixture,
    ws_side_effect: Exception,
    auth_side_effect: Exception | None,
    expected_log: str,
) -> None:
    """Test that reconnect failures are logged and the entry stays loaded."""
    entry = await async_init_integration(hass)
    ws_handler = entry.runtime_data.api.websocket_handler
    assert isinstance(ws_handler, MockedAnovaWebsocketHandler)

    entry.runtime_data.api.create_websocket.side_effect = ws_side_effect
    entry.runtime_data.api.authenticate = AsyncMock(side_effect=auth_side_effect)

    with caplog.at_level(logging.WARNING, logger="homeassistant.components.anova"):
        ws_handler.simulate_disconnect()
        await hass.async_block_till_done()
        await hass.async_block_till_done(wait_background_tasks=True)

    assert expected_log in caplog.text
    assert entry.state is ConfigEntryState.LOADED


async def test_reconnect_backoff_skips_retries_until_elapsed(
    hass: HomeAssistant,
    anova_api: AnovaApi,
) -> None:
    """Test repeated reconnect failures back off instead of retrying every poll."""
    entry = await async_init_integration(hass)
    ws_handler = entry.runtime_data.api.websocket_handler
    assert isinstance(ws_handler, MockedAnovaWebsocketHandler)

    original_side_effect = entry.runtime_data.api.create_websocket.side_effect
    entry.runtime_data.api.create_websocket.side_effect = NoDevicesFound("offline")
    entry.runtime_data.api.authenticate = AsyncMock()

    ws_handler.simulate_disconnect()
    await hass.async_block_till_done()
    await hass.async_block_till_done(wait_background_tasks=True)
    attempts_after_first_failure = entry.runtime_data.api.create_websocket.call_count
    assert entry.runtime_data.reconnect_backoff > timedelta(
        seconds=RECONNECT_RETRY_DELAY
    )
    next_attempt = entry.runtime_data.next_reconnect_attempt
    assert next_attempt is not None

    # A poll before the backoff window elapses must not attempt to reconnect again.
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=RECONNECT_RETRY_DELAY + 1)
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    assert (
        entry.runtime_data.api.create_websocket.call_count
        == attempts_after_first_failure
    )
    assert entry.runtime_data.next_reconnect_attempt == next_attempt
    assert entry.runtime_data.coordinators[0].data is None

    # Once the backoff window elapses and the connection recovers, retry
    # succeeds and the backoff resets to the base delay for the next outage.
    entry.runtime_data.api.create_websocket.side_effect = original_side_effect
    entry.runtime_data.next_reconnect_attempt = dt_util.utcnow() - timedelta(seconds=1)
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=RECONNECT_RETRY_DELAY + 1)
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (
        entry.runtime_data.api.create_websocket.call_count
        > attempts_after_first_failure
    )
    assert entry.runtime_data.reconnect_backoff == timedelta(
        seconds=RECONNECT_RETRY_DELAY
    )
    assert entry.runtime_data.next_reconnect_attempt is None


async def test_coordinator_poll_does_not_reconnect_when_connected(
    hass: HomeAssistant,
    anova_api: AnovaApi,
) -> None:
    """Test that the periodic coordinator poll is a no-op when the websocket is alive."""
    entry = await async_init_integration(hass)
    initial_call_count = entry.runtime_data.api.create_websocket.call_count

    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=RECONNECT_RETRY_DELAY + 1)
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.runtime_data.api.create_websocket.call_count == initial_call_count


async def test_device_marked_unavailable_after_prolonged_silence(
    hass: HomeAssistant,
    anova_api: AnovaApi,
) -> None:
    """Test a device is marked unavailable after DEVICE_STALE_THRESHOLD.

    This applies even though the websocket transport to Anova's cloud is
    still alive - Anova has no disconnect signal for a specific device.
    """
    entry = await async_init_integration(hass)
    coordinator = entry.runtime_data.coordinators[0]
    assert coordinator.anova_device.last_update_received_at is not None
    assert hass.states.get("switch.anova_precision_cooker_cook").state == "off"

    coordinator.anova_device.last_update_received_at = (
        dt_util.utcnow() - DEVICE_STALE_THRESHOLD - timedelta(seconds=1)
    )
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=RECONNECT_RETRY_DELAY + 1)
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert coordinator.data is None
    assert hass.states.get("switch.anova_precision_cooker_cook").state == "unavailable"


async def test_device_stays_available_when_recently_seen(
    hass: HomeAssistant,
    anova_api: AnovaApi,
) -> None:
    """Test the periodic poll alone does not mark a device unavailable.

    Only prolonged silence should trigger it.
    """
    entry = await async_init_integration(hass)
    coordinator = entry.runtime_data.coordinators[0]

    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=RECONNECT_RETRY_DELAY + 1)
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert coordinator.data is not None
    assert hass.states.get("switch.anova_precision_cooker_cook").state == "off"


async def test_websocket_reconnect_retries_after_transient_failure(
    hass: HomeAssistant,
    anova_api: AnovaApi,
) -> None:
    """Test that a transient NoDevicesFound is retried immediately via re-auth.

    A stale session can connect but never have the device attached
    (NoDevicesFound) just as easily as it can fail outright
    (WebsocketFailure), so this must not wait for the next poll cycle to
    retry with the same session - it should re-authenticate and retry within
    the same reconnect attempt, same as WebsocketFailure does.
    """
    entry = await async_init_integration(hass)
    ws_handler = entry.runtime_data.api.websocket_handler
    assert isinstance(ws_handler, MockedAnovaWebsocketHandler)

    original_side_effect = entry.runtime_data.api.create_websocket.side_effect
    attempts: list[int] = []

    async def create_websocket_fails_once() -> None:
        attempts.append(1)
        if len(attempts) == 1:
            raise NoDevicesFound("Device temporarily offline")
        await original_side_effect()

    entry.runtime_data.api.create_websocket.side_effect = create_websocket_fails_once
    entry.runtime_data.api.authenticate = AsyncMock()

    ws_handler.simulate_disconnect()
    await hass.async_block_till_done()
    await hass.async_block_till_done(wait_background_tasks=True)

    entry.runtime_data.api.authenticate.assert_called_once()
    assert len(attempts) == 2
    new_ws_handler = entry.runtime_data.api.websocket_handler
    assert new_ws_handler is not ws_handler


async def test_migration_removing_devices_in_config_entry(
    hass: HomeAssistant, anova_api: AnovaApi
) -> None:
    """Test a successful setup entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Anova",
        data={
            CONF_USERNAME: "sample@gmail.com",
            CONF_PASSWORD: "sample",
            CONF_DEVICES: [],
        },
        unique_id="sample@gmail.com",
        version=1,
        minor_version=1,
    )
    entry.add_to_hass(hass)

    with patch("homeassistant.components.anova.AnovaApi.authenticate"):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.anova_precision_cooker_mode")
    assert state is not None
    assert state.state == "idle"

    assert entry.version == 1
    assert entry.minor_version == 2
    assert CONF_DEVICES not in entry.data

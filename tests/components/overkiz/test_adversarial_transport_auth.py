"""Adversarial stress tests for transport and authentication fault resilience (Milestone M5)."""

from datetime import timedelta
from unittest.mock import Mock

from aiohttp import ClientConnectorError, ClientError, ServerDisconnectedError
from freezegun.api import FrozenDateTimeFactory
from pyoverkiz.enums import EventName
from pyoverkiz.exceptions import (
    BadCredentialsError,
    MaintenanceError,
    NotAuthenticatedError,
    ServiceUnavailableError,
    TooManyConcurrentRequestsError,
    TooManyRequestsError,
)
from pyoverkiz.models import ExecutionRegisteredEvent
import pytest

from homeassistant.components.overkiz.const import UPDATE_INTERVAL
from homeassistant.components.overkiz.coordinator import OverkizDataUpdateCoordinator
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from .conftest import FixtureDevice, MockOverkizClient, SetupOverkizIntegration
from .helpers import async_deliver_events

from tests.common import async_fire_time_changed

TEMPERATURE_SENSOR = FixtureDevice(
    "setup/cloud_nexity_rail_din_europe.json",
    "io://1234-5678-1698/15702199#2",
    "sensor.maple_residence_garden_radiator_bathroom_temperature_sensor_temperature",
)


# =========================================================================
# Scenario 1: Prolonged Network Disconnects & Multi-Cycle Reconnection
# =========================================================================


async def test_adversarial_prolonged_disconnect_multi_cycle_recovery(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Stress test prolonged network disconnect with multiple consecutive connection errors.

    Verify coordinator handles each failure as UpdateFailed, stays LOADED, keeps update_interval
    at default 30s, and automatically recovers when connectivity is restored.
    """
    entry = await setup_overkiz_integration(fixture=TEMPERATURE_SENSOR.fixture)
    coordinator: OverkizDataUpdateCoordinator = entry.runtime_data.coordinator

    initial_state = hass.states.get(TEMPERATURE_SENSOR.entity_id)
    assert initial_state.state != STATE_UNAVAILABLE

    consecutive_faults = [
        TimeoutError("Connection timed out"),
        ClientConnectorError(Mock(), OSError("Connection refused")),
        ServerDisconnectedError("Server disconnected"),
        ClientError("Generic aiohttp client error"),
        TimeoutError("Read timeout"),
    ]

    for fault in consecutive_faults:
        mock_client.fetch_events.side_effect = fault
        mock_client.get_devices.side_effect = fault
        if isinstance(fault, ServerDisconnectedError):
            mock_client.login.side_effect = fault

        freezer.tick(UPDATE_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        # Entity must be unavailable during outage
        assert hass.states.get(TEMPERATURE_SENSOR.entity_id).state == STATE_UNAVAILABLE
        # Config entry must stay LOADED (never unloaded or faulted)
        assert entry.state is ConfigEntryState.LOADED
        # Coordinator must maintain default 30s interval
        assert coordinator.update_interval == UPDATE_INTERVAL
        assert coordinator.executions == {}
        assert coordinator._need_full_resync is True

    # Reconnection: network is restored
    mock_client.fetch_events.side_effect = None
    mock_client.fetch_events.return_value = []
    mock_client.get_devices.side_effect = mock_client._async_get_devices
    mock_client.login.side_effect = None
    mock_client.get_devices.reset_mock()

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Recovery: full device fetch occurred and entity is available again
    assert mock_client.get_devices.await_count == 1
    assert coordinator._need_full_resync is False
    restored_state = hass.states.get(TEMPERATURE_SENSOR.entity_id)
    assert restored_state.state != STATE_UNAVAILABLE
    assert restored_state.state == initial_state.state


# =========================================================================
# Scenario 2: Session Expiration During Outage & Safe Relogin
# =========================================================================


async def test_adversarial_session_expiration_during_outage_relogin_recovery(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Simulate session expiration during network outage (401 NotAuthenticatedError on reconnect).

    Verify coordinator executes automatic relogin and device fetch without escalating to ConfigEntryAuthFailed.
    """
    entry = await setup_overkiz_integration(fixture=TEMPERATURE_SENSOR.fixture)
    coordinator: OverkizDataUpdateCoordinator = entry.runtime_data.coordinator

    # 1. Outage occurs
    mock_client.fetch_events.side_effect = ClientConnectorError(
        Mock(), OSError("Network down")
    )
    mock_client.get_devices.side_effect = ClientConnectorError(
        Mock(), OSError("Network down")
    )
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(TEMPERATURE_SENSOR.entity_id).state == STATE_UNAVAILABLE
    assert coordinator._need_full_resync is True

    # 2. Network returns, but cloud session has expired -> 401 NotAuthenticatedError on get_devices / fetch_events
    mock_client.login.reset_mock()
    mock_client.get_devices.side_effect = NotAuthenticatedError("Session expired")
    mock_client.fetch_events.side_effect = NotAuthenticatedError("Session expired")

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Resync attempt failed due to NotAuthenticatedError -> caught as UpdateFailed, entry stays LOADED
    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get(TEMPERATURE_SENSOR.entity_id).state == STATE_UNAVAILABLE
    assert coordinator._need_full_resync is True

    # 3. Next poll: coordinator attempts relogin & device fetch
    mock_client.get_devices.side_effect = mock_client._async_get_devices
    mock_client.fetch_events.side_effect = None
    mock_client.fetch_events.return_value = []
    mock_client.get_devices.reset_mock()
    mock_client.login.reset_mock()

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Coordinator must have fetched devices and restored entity
    assert mock_client.get_devices.await_count == 1
    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get(TEMPERATURE_SENSOR.entity_id).state != STATE_UNAVAILABLE
    assert coordinator._need_full_resync is False


async def test_adversarial_session_expiration_transient_relogin_failure_survives(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Verify transient relogin failure does not escalate to auth failed.

    When session is expired, if the relogin attempt encounters a transient network drop,
    verify coordinator raises UpdateFailed (temporary retry) and does NOT kill the config entry with ConfigEntryAuthFailed.
    """
    entry = await setup_overkiz_integration(fixture=TEMPERATURE_SENSOR.fixture)
    coordinator: OverkizDataUpdateCoordinator = entry.runtime_data.coordinator

    # Session expired, and relogin hits network timeout
    mock_client.fetch_events.side_effect = NotAuthenticatedError("Session expired")
    mock_client.login.side_effect = TimeoutError("Timeout connecting to auth endpoint")

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Config entry remains LOADED (temporary UpdateFailed)
    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get(TEMPERATURE_SENSOR.entity_id).state == STATE_UNAVAILABLE
    assert coordinator._need_full_resync is True

    # Next cycle: auth endpoint reachable -> relogin succeeds, fetch_events succeeds
    mock_client.login.side_effect = None
    mock_client.fetch_events.side_effect = None
    mock_client.fetch_events.return_value = []
    mock_client.get_devices.side_effect = mock_client._async_get_devices
    mock_client.get_devices.reset_mock()

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Recovery complete
    assert entry.state is ConfigEntryState.LOADED
    assert mock_client.get_devices.await_count == 1
    assert hass.states.get(TEMPERATURE_SENSOR.entity_id).state != STATE_UNAVAILABLE
    assert coordinator._need_full_resync is False


# =========================================================================
# Scenario 3: Fatal Auth Failure (BadCredentialsError Escalation)
# =========================================================================


async def test_adversarial_fatal_bad_credentials_on_relogin_escalates_cleanly(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Verify that permanent BadCredentialsError during relogin escalates cleanly to ConfigEntryAuthFailed."""
    await setup_overkiz_integration(fixture=TEMPERATURE_SENSOR.fixture)

    mock_client.fetch_events.side_effect = NotAuthenticatedError("Session expired")
    mock_client.login.side_effect = BadCredentialsError("Bad username or password")

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(TEMPERATURE_SENSOR.entity_id).state == STATE_UNAVAILABLE


async def test_adversarial_fatal_bad_credentials_during_resync_device_fetch(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Verify that BadCredentialsError during full resync _get_devices() escalates cleanly."""
    entry = await setup_overkiz_integration(fixture=TEMPERATURE_SENSOR.fixture)
    coordinator: OverkizDataUpdateCoordinator = entry.runtime_data.coordinator

    # Invalidate listener to set _need_full_resync
    coordinator._need_full_resync = True

    # In resync path, _get_devices raises BadCredentialsError
    mock_client.get_devices.side_effect = BadCredentialsError("Token revoked")

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(TEMPERATURE_SENSOR.entity_id).state == STATE_UNAVAILABLE


async def test_adversarial_server_disconnected_relogin_bad_credentials_escalates(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Verify ServerDisconnectedError followed by BadCredentialsError on relogin escalates cleanly."""
    await setup_overkiz_integration(fixture=TEMPERATURE_SENSOR.fixture)

    mock_client.fetch_events.side_effect = ServerDisconnectedError(
        "Server disconnected"
    )
    mock_client.login.side_effect = BadCredentialsError("Invalid credentials")

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(TEMPERATURE_SENSOR.entity_id).state == STATE_UNAVAILABLE


# =========================================================================
# Scenario 4: Server Maintenance / 503 / 502 / Rate Limiting Responses
# =========================================================================


@pytest.mark.parametrize(
    "server_error",
    [
        MaintenanceError("Somfy cloud scheduled maintenance"),
        ServiceUnavailableError("503 Service Unavailable"),
        ServiceUnavailableError("502 Bad Gateway"),
        TooManyRequestsError("429 Too Many Requests"),
        TooManyConcurrentRequestsError("Too Many Concurrent Requests"),
    ],
    ids=[
        "maintenance_error",
        "service_unavailable_503",
        "bad_gateway_502",
        "too_many_requests_429",
        "too_many_concurrent_requests",
    ],
)
async def test_adversarial_server_maintenance_and_outage_recovery_lifecycle(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
    server_error: Exception,
) -> None:
    """Verify server maintenance and 5xx/429 errors are handled gracefully without unhandled exceptions.

    Entity becomes unavailable, entry stays LOADED, and once maintenance ends, entity recovers automatically.
    """
    entry = await setup_overkiz_integration(fixture=TEMPERATURE_SENSOR.fixture)
    coordinator: OverkizDataUpdateCoordinator = entry.runtime_data.coordinator

    initial_state = hass.states.get(TEMPERATURE_SENSOR.entity_id)

    # Server error occurs
    mock_client.fetch_events.side_effect = server_error
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(TEMPERATURE_SENSOR.entity_id).state == STATE_UNAVAILABLE
    assert entry.state is ConfigEntryState.LOADED
    assert coordinator.update_interval == UPDATE_INTERVAL

    # Server recovers
    mock_client.fetch_events.side_effect = None
    mock_client.fetch_events.return_value = []
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get(TEMPERATURE_SENSOR.entity_id).state == initial_state.state


# =========================================================================
# Scenario 5: Active Execution Fault Reset Storm Prevention
# =========================================================================


async def test_adversarial_active_execution_transport_fault_resets_storm(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Verify that network failures during active execution reset the 1s interval.

    Verify that if a network failure occurs during an active 1s execution poll:
    1. Execution is immediately cleared.
    2. Polling interval is immediately restored to default 30s.
    3. Coordinator does NOT bombard the unreachable server every 1 second.
    """
    entry = await setup_overkiz_integration(fixture=TEMPERATURE_SENSOR.fixture)
    coordinator: OverkizDataUpdateCoordinator = entry.runtime_data.coordinator

    # Register an execution to enter 1s fast polling
    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            ExecutionRegisteredEvent(
                name=EventName.EXECUTION_REGISTERED, exec_id="exec-active-drop"
            )
        ],
    )
    assert coordinator.update_interval == timedelta(seconds=1)
    assert "exec-active-drop" in coordinator.executions

    # Next fetch encounters TimeoutError
    mock_client.fetch_events.side_effect = TimeoutError("Connection timed out")
    freezer.tick(timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Executions cleared and interval restored to 30s
    assert coordinator.executions == {}
    assert coordinator._executions_registered_at == {}
    assert coordinator.update_interval == UPDATE_INTERVAL
    assert hass.states.get(TEMPERATURE_SENSOR.entity_id).state == STATE_UNAVAILABLE

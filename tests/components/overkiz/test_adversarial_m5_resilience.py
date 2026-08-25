"""Adversarial stress tests for execution storm prevention and state drift resilience (Milestone M5)."""

from datetime import timedelta
from unittest.mock import Mock

from aiohttp import ClientConnectorError, ClientError, ServerDisconnectedError
from freezegun.api import FrozenDateTimeFactory
from pyoverkiz.enums import EventName, ExecutionState
from pyoverkiz.exceptions import (
    InvalidEventListenerIdError,
    MaintenanceError,
    OverkizError,
    ServiceUnavailableError,
    TooManyConcurrentRequestsError,
    TooManyRequestsError,
)
from pyoverkiz.models import (
    DataType,
    ExecutionRegisteredEvent,
    ExecutionStateChangedEvent,
    State,
    States,
)
import pytest

from homeassistant.components.overkiz.const import UPDATE_INTERVAL
from homeassistant.components.overkiz.coordinator import OverkizDataUpdateCoordinator
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
# Category 1: 1-Second Polling Storm Prevention & TTL Recovery Scenarios
# =========================================================================


async def test_adversarial_single_execution_dropped_completion_ttl_recovery(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Simulate a single execution whose completion event is permanently dropped.

    Verify coordinator interval drops to 1s, remains 1s during normal execution,
    and automatically resets to 30s when TTL expires, purging the execution.
    """
    entry = await setup_overkiz_integration(fixture=TEMPERATURE_SENSOR.fixture)
    coordinator: OverkizDataUpdateCoordinator = entry.runtime_data.coordinator

    assert coordinator.update_interval == UPDATE_INTERVAL
    assert coordinator.executions == {}

    # Register an execution
    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            ExecutionRegisteredEvent(
                name=EventName.EXECUTION_REGISTERED, exec_id="exec-storm-1"
            )
        ],
    )

    # Polling frequency increases to 1s
    assert coordinator.update_interval == timedelta(seconds=1)
    assert "exec-storm-1" in coordinator.executions
    assert "exec-storm-1" in coordinator._executions_registered_at

    # Advance 30 seconds (still within 60s TTL) with empty poll events (no completion)
    freezer.tick(timedelta(seconds=30))
    mock_client.queue_events([])
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Still tracking execution at 1s interval
    assert coordinator.update_interval == timedelta(seconds=1)
    assert "exec-storm-1" in coordinator.executions

    # Advance another 35 seconds (total 65s > 60s EXECUTION_TTL)
    freezer.tick(timedelta(seconds=35))
    mock_client.queue_events([])
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # TTL expired: execution purged, interval restored to 30s default
    assert "exec-storm-1" not in coordinator.executions
    assert "exec-storm-1" not in coordinator._executions_registered_at
    assert coordinator.executions == {}
    assert coordinator.update_interval == UPDATE_INTERVAL


async def test_adversarial_multi_execution_staggered_ttl_and_partial_completion(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Stress test multiple concurrent executions with staggered registration and dropped events.

    Exec A registered at t=0s, Exec B registered at t=20s.
    Exec A completes at t=30s.
    Exec B completion event is dropped.
    Verify Exec B keeps 1s interval until t=85s (its own TTL), then resets to 30s.
    """
    entry = await setup_overkiz_integration(fixture=TEMPERATURE_SENSOR.fixture)
    coordinator: OverkizDataUpdateCoordinator = entry.runtime_data.coordinator

    # Register Exec A at t=0
    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            ExecutionRegisteredEvent(
                name=EventName.EXECUTION_REGISTERED, exec_id="exec-A"
            )
        ],
    )
    assert coordinator.update_interval == timedelta(seconds=1)
    assert "exec-A" in coordinator.executions

    # Advance 20s, register Exec B at t=20
    freezer.tick(timedelta(seconds=20))
    mock_client.queue_events(
        [
            ExecutionRegisteredEvent(
                name=EventName.EXECUTION_REGISTERED, exec_id="exec-B"
            )
        ]
    )
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert "exec-A" in coordinator.executions
    assert "exec-B" in coordinator.executions
    assert coordinator.update_interval == timedelta(seconds=1)

    # Advance 10s (t=30s): Exec A completes
    freezer.tick(timedelta(seconds=10))
    mock_client.queue_events(
        [
            ExecutionStateChangedEvent(
                name=EventName.EXECUTION_STATE_CHANGED,
                exec_id="exec-A",
                new_state=ExecutionState.COMPLETED,
                old_state=ExecutionState.IN_PROGRESS,
            )
        ]
    )
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Exec A removed, Exec B remains active -> interval must remain 1s
    assert "exec-A" not in coordinator.executions
    assert "exec-B" in coordinator.executions
    assert coordinator.update_interval == timedelta(seconds=1)

    # Advance to t=70s (Exec A would be 70s old, Exec B is 50s old < 60s TTL)
    freezer.tick(timedelta(seconds=40))
    mock_client.queue_events([])
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Exec B still alive at t=70s (age 50s)
    assert "exec-B" in coordinator.executions
    assert coordinator.update_interval == timedelta(seconds=1)

    # Advance to t=85s (Exec B is now 65s old > 60s TTL, dropped completion)
    freezer.tick(timedelta(seconds=15))
    mock_client.queue_events([])
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Exec B purged, interval returned to 30s
    assert coordinator.executions == {}
    assert coordinator._executions_registered_at == {}
    assert coordinator.update_interval == UPDATE_INTERVAL


async def test_adversarial_multi_execution_both_dropped_staggered_ttl(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Stress test two executions where both completion events are dropped.

    Exec 1 registered at t=0s.
    Exec 2 registered at t=30s.
    Both completion events dropped.
    At t=65s: Exec 1 expired (>60s), Exec 2 (age 35s) still active -> interval remains 1s.
    At t=95s: Exec 2 expired (age 65s > 60s) -> interval resets to 30s.
    """
    entry = await setup_overkiz_integration(fixture=TEMPERATURE_SENSOR.fixture)
    coordinator: OverkizDataUpdateCoordinator = entry.runtime_data.coordinator

    # Register Exec 1 at t=0s
    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            ExecutionRegisteredEvent(
                name=EventName.EXECUTION_REGISTERED, exec_id="exec-1"
            )
        ],
    )
    assert "exec-1" in coordinator.executions
    assert coordinator.update_interval == timedelta(seconds=1)

    # Advance 30s, register Exec 2 at t=30s
    freezer.tick(timedelta(seconds=30))
    mock_client.queue_events(
        [
            ExecutionRegisteredEvent(
                name=EventName.EXECUTION_REGISTERED, exec_id="exec-2"
            )
        ]
    )
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Advance to t=65s: Exec 1 is 65s old (>60s TTL), Exec 2 is 35s old (<60s TTL)
    freezer.tick(timedelta(seconds=35))
    mock_client.queue_events([])
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert "exec-1" not in coordinator.executions
    assert "exec-2" in coordinator.executions
    assert coordinator.update_interval == timedelta(seconds=1)

    # Advance to t=95s: Exec 2 is now 65s old (>60s TTL)
    freezer.tick(timedelta(seconds=30))
    mock_client.queue_events([])
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert coordinator.executions == {}
    assert coordinator.update_interval == UPDATE_INTERVAL


async def test_adversarial_untracked_legacy_execution_injection_ttl_cleanup(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Adversarially inject an execution without timestamp tracking.

    Verify coordinator discovers it during cleanup, adopts a registration timestamp,
    and purges it after TTL.
    """
    entry = await setup_overkiz_integration(fixture=TEMPERATURE_SENSOR.fixture)
    coordinator: OverkizDataUpdateCoordinator = entry.runtime_data.coordinator

    # Adversarially inject directly into dictionary (bypassing track_execution)
    coordinator.executions["exec-untracked-ghost"] = []
    coordinator.update_interval = timedelta(seconds=1)

    assert "exec-untracked-ghost" not in coordinator._executions_registered_at

    # Trigger refresh: coordinator runs _cleanup_stale_executions, registers timestamp
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert "exec-untracked-ghost" in coordinator._executions_registered_at
    assert coordinator.update_interval == timedelta(seconds=1)

    # Fast-forward 65 seconds
    freezer.tick(timedelta(seconds=65))
    mock_client.queue_events([])
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Verify ghost execution was cleaned up and interval restored
    assert "exec-untracked-ghost" not in coordinator.executions
    assert "exec-untracked-ghost" not in coordinator._executions_registered_at
    assert coordinator.update_interval == UPDATE_INTERVAL


async def test_adversarial_non_terminal_execution_states_do_not_prematurely_untrack(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Verify non-terminal execution states (IN_PROGRESS, NOT_TRANSMITTED, TRANSMITTED) do not clear execution.

    Only COMPLETED and FAILED states should untrack.
    """
    entry = await setup_overkiz_integration(fixture=TEMPERATURE_SENSOR.fixture)
    coordinator: OverkizDataUpdateCoordinator = entry.runtime_data.coordinator

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            ExecutionRegisteredEvent(
                name=EventName.EXECUTION_REGISTERED, exec_id="exec-state-test"
            )
        ],
    )
    assert coordinator.update_interval == timedelta(seconds=1)

    # Deliver non-terminal states
    for non_terminal in [
        ExecutionState.IN_PROGRESS,
        ExecutionState.NOT_TRANSMITTED,
        ExecutionState.TRANSMITTED,
        ExecutionState.UNKNOWN,
    ]:
        freezer.tick(timedelta(seconds=1))
        mock_client.queue_events(
            [
                ExecutionStateChangedEvent(
                    name=EventName.EXECUTION_STATE_CHANGED,
                    exec_id="exec-state-test",
                    new_state=non_terminal,
                    old_state=ExecutionState.IN_PROGRESS,
                )
            ]
        )
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        # Must still be tracked and polling at 1s
        assert "exec-state-test" in coordinator.executions
        assert coordinator.update_interval == timedelta(seconds=1)

    # Deliver terminal state: FAILED
    freezer.tick(timedelta(seconds=1))
    mock_client.queue_events(
        [
            ExecutionStateChangedEvent(
                name=EventName.EXECUTION_STATE_CHANGED,
                exec_id="exec-state-test",
                new_state=ExecutionState.FAILED,
                old_state=ExecutionState.IN_PROGRESS,
            )
        ]
    )
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Untracked and restored to 30s
    assert "exec-state-test" not in coordinator.executions
    assert coordinator.update_interval == UPDATE_INTERVAL


async def test_adversarial_custom_default_update_interval_preservation(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Verify that when a custom update interval is set (e.g. 5s for local), execution recovery restores that custom interval."""
    entry = await setup_overkiz_integration(fixture=TEMPERATURE_SENSOR.fixture)
    coordinator: OverkizDataUpdateCoordinator = entry.runtime_data.coordinator

    custom_interval = timedelta(seconds=5)
    coordinator.set_update_interval(custom_interval)
    assert coordinator.update_interval == custom_interval
    assert coordinator._default_update_interval == custom_interval

    # Register execution
    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            ExecutionRegisteredEvent(
                name=EventName.EXECUTION_REGISTERED, exec_id="exec-custom-int"
            )
        ],
    )
    assert coordinator.update_interval == timedelta(seconds=1)

    # TTL expiry
    freezer.tick(timedelta(seconds=65))
    mock_client.queue_events([])
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Restores to 5s, NOT hardcoded 30s!
    assert coordinator.update_interval == custom_interval


# =========================================================================
# Category 2: Error-Induced Execution Reset Scenarios
# =========================================================================


@pytest.mark.parametrize(
    "injected_error",
    [
        ClientConnectorError(Mock(), Mock()),
        TimeoutError("Connection timeout"),
        ServerDisconnectedError("Server disconnected"),
        InvalidEventListenerIdError("Invalid event listener id"),
        TooManyRequestsError("Rate limited 429"),
        TooManyConcurrentRequestsError("Too many concurrent requests"),
        MaintenanceError("Maintenance in progress"),
        ServiceUnavailableError("503 Service Unavailable"),
        OverkizError("Internal generic Overkiz error"),
        ClientError("Generic aiohttp ClientError"),
    ],
    ids=[
        "client_connector_error",
        "timeout_error",
        "server_disconnected_error",
        "invalid_event_listener_id",
        "too_many_requests",
        "too_many_concurrent_requests",
        "maintenance_error",
        "service_unavailable",
        "overkiz_error",
        "client_error",
    ],
)
async def test_adversarial_error_induced_execution_reset(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
    injected_error: Exception,
) -> None:
    """Adversarially inject various network and API errors during an active 1s execution poll.

    Verify that ANY error immediately wipes executions, clears registration timestamps,
    and restores update_interval to 30s so the coordinator never loops at 1s during failures.
    """
    entry = await setup_overkiz_integration(fixture=TEMPERATURE_SENSOR.fixture)
    coordinator: OverkizDataUpdateCoordinator = entry.runtime_data.coordinator

    # Register execution to enter 1s fast polling mode
    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            ExecutionRegisteredEvent(
                name=EventName.EXECUTION_REGISTERED, exec_id="exec-active-during-fault"
            )
        ],
    )
    assert coordinator.update_interval == timedelta(seconds=1)
    assert len(coordinator.executions) == 1

    # Inject error during fetch_events
    mock_client.fetch_events.side_effect = injected_error
    if isinstance(injected_error, ServerDisconnectedError):
        # If server disconnected, relogin attempt will also encounter network error
        mock_client.login.side_effect = injected_error

    freezer.tick(timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Coordinator must have reset all execution state and returned interval to 30s
    assert coordinator.executions == {}
    assert coordinator._executions_registered_at == {}
    assert coordinator.update_interval == UPDATE_INTERVAL
    assert hass.states.get(TEMPERATURE_SENSOR.entity_id).state == STATE_UNAVAILABLE


# =========================================================================
# Category 3: State Drift Resynchronization Scenarios
# =========================================================================


async def test_adversarial_state_drift_resync_after_invalid_listener_id(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Verify that when a listener ID is invalidated and server state changes offline, full resync reconciles drift.

    1. Initial temperature is 20.0 °C.
    2. Server invalidates listener ID with InvalidEventListenerIdError.
    3. While disconnected, server state changes to 28.5 °C.
    4. Upon listener re-registration / recovery, coordinator fetches full device list (_get_devices()).
    5. Entity state reflects the 28.5 °C server state.
    6. Subsequent polls do NOT call _get_devices() (event-driven efficiency).
    """
    await setup_overkiz_integration(fixture=TEMPERATURE_SENSOR.fixture)

    initial_state = hass.states.get(TEMPERATURE_SENSOR.entity_id)
    assert float(initial_state.state) == 24.4

    mock_client.get_devices.reset_mock()

    # 1. Simulate listener invalidation
    mock_client.fetch_events.side_effect = InvalidEventListenerIdError(
        "Listener session expired on Somfy server"
    )
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Entity becomes unavailable during outage
    assert hass.states.get(TEMPERATURE_SENSOR.entity_id).state == STATE_UNAVAILABLE

    # 2. Simulate offline state drift on server side (device temperature changed to 28.5)
    for dev in mock_client.setup.devices:
        if dev.device_url == TEMPERATURE_SENSOR.device_url:
            dev.states = States(
                [
                    State(
                        name="core:TemperatureState",
                        type=DataType.FLOAT,
                        value=28.5,
                    )
                ]
            )

    # 3. Server recovers: next poll returns empty events
    mock_client.fetch_events.side_effect = None
    mock_client.fetch_events.return_value = []

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # 4. Verify coordinator executed full resync via get_devices(refresh=True)
    assert mock_client.get_devices.await_count == 1
    updated_state = hass.states.get(TEMPERATURE_SENSOR.entity_id)
    assert updated_state.state != STATE_UNAVAILABLE
    assert float(updated_state.state) == 28.5

    # 5. Verify subsequent normal poll does NOT re-fetch all devices
    mock_client.get_devices.reset_mock()
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_client.get_devices.await_count == 0


async def test_adversarial_state_drift_resync_after_server_disconnected_error(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Verify state drift resynchronization when ServerDisconnectedError occurs and reconnect succeeds.

    1. Disconnect occurs.
    2. Server state changes to 15.2 °C.
    3. Reconnect succeeds: full device state is pulled and entity is updated to 15.2 °C immediately.
    """
    await setup_overkiz_integration(fixture=TEMPERATURE_SENSOR.fixture)

    initial_state = hass.states.get(TEMPERATURE_SENSOR.entity_id)
    assert float(initial_state.state) == 24.4

    # Simulate offline change on server
    for dev in mock_client.setup.devices:
        if dev.device_url == TEMPERATURE_SENSOR.device_url:
            dev.states = States(
                [
                    State(
                        name="core:TemperatureState",
                        type=DataType.FLOAT,
                        value=15.2,
                    )
                ]
            )

    mock_client.get_devices.reset_mock()
    mock_client.login.reset_mock()

    # Trigger ServerDisconnectedError on fetch_events
    mock_client.fetch_events.side_effect = ServerDisconnectedError("Remote closed")

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Verify coordinator performed relogin and fetched devices
    assert mock_client.login.await_count == 1
    assert mock_client.get_devices.await_count == 1

    # Verify state was synchronized to 15.2 °C
    updated_state = hass.states.get(TEMPERATURE_SENSOR.entity_id)
    assert updated_state.state != STATE_UNAVAILABLE
    assert float(updated_state.state) == 15.2


async def test_adversarial_state_drift_resync_persists_across_multiple_failed_recovery_polls(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Verify that _need_full_resync remains True even if recovery poll attempts fail multiple times.

    1. Listener invalidated -> _need_full_resync = True.
    2. Attempt 1 recovery fails in _get_devices with ClientConnectorError -> _need_full_resync must REMAIN True.
    3. Attempt 2 recovery fails with TimeoutError -> _need_full_resync must REMAIN True.
    4. Server state changes to 31.0 °C.
    5. Attempt 3 recovery succeeds -> pulls full device state and updates entity to 31.0 °C.
    """
    entry = await setup_overkiz_integration(fixture=TEMPERATURE_SENSOR.fixture)
    coordinator: OverkizDataUpdateCoordinator = entry.runtime_data.coordinator

    # 1. Invalidate listener
    mock_client.fetch_events.side_effect = InvalidEventListenerIdError("Expired")
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert coordinator._need_full_resync is True

    # 2. Recovery attempt 1 fails in _get_devices
    mock_client.fetch_events.side_effect = None
    mock_client.get_devices.side_effect = ClientConnectorError(Mock(), Mock())

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Still marked as needing full resync
    assert coordinator._need_full_resync is True

    # 3. Recovery attempt 2 fails with TimeoutError
    mock_client.get_devices.side_effect = TimeoutError("Still down")

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Still marked as needing full resync
    assert coordinator._need_full_resync is True

    # 4. Modify server state offline
    for dev in mock_client.setup.devices:
        if dev.device_url == TEMPERATURE_SENSOR.device_url:
            dev.states = States(
                [
                    State(
                        name="core:TemperatureState",
                        type=DataType.FLOAT,
                        value=31.0,
                    )
                ]
            )

    # 5. Recovery attempt 3 succeeds
    mock_client.get_devices.side_effect = mock_client._async_get_devices
    mock_client.fetch_events.return_value = []

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Resync resolved
    assert coordinator._need_full_resync is False
    updated_state = hass.states.get(TEMPERATURE_SENSOR.entity_id)
    assert updated_state.state != STATE_UNAVAILABLE
    assert float(updated_state.state) == 31.0

"""Test Visonic integration setup and cleanup."""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, call, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import async_fire_time_changed

from homeassistant.components.visonic import async_terminate_coordinator
from homeassistant.components.visonic.const import (
    CONF_CLOUD_APP_ID,
    CONF_PANEL_NUMBER,
    CONF_PANEL_SERIAL,
    TEXT_PANEL_MODEL,
)
from homeassistant.components.visonic.exceptions import (
    VisonicAuthException,
    VisonicException,
)
from homeassistant.components.visonic.visonic_data_types import (
    VisonicConfigEntry,
    VisonicCoordinatorData,
)
from homeassistant.components.visonic.visonic_types import DeviceType
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_TYPE
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .helpers import create_mock_config_entry

MODULE = "homeassistant.components.visonic"
type SetupIntegration = Callable[..., Awaitable[tuple[bool, VisonicConfigEntry]]]


@pytest.mark.parametrize("missing_field", [CONF_TYPE, CONF_PANEL_NUMBER])
async def test_setup_missing_required_field(
    hass: HomeAssistant, missing_field: str
) -> None:
    """Incomplete configuration cannot create runtime data."""
    entry = create_mock_config_entry(delete_data=[missing_field])
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert not hasattr(entry, "runtime_data")


@pytest.mark.parametrize("device_type", list(DeviceType))
async def test_unload_entry(
    hass: HomeAssistant,
    setup_integration: SetupIntegration,
    device_type: DeviceType,
) -> None:
    """Unload the backend and remove its shutdown listener."""
    result, entry = await setup_integration(data={CONF_TYPE: device_type})
    assert result
    connection = entry.runtime_data.coordinator.connection
    with (
        patch.object(hass.config_entries, "async_unload_platforms", return_value=True),
        patch.object(
            connection, "async_panel_stop", wraps=connection.async_panel_stop
        ) as stop,
    ):
        assert await hass.config_entries.async_unload(entry.entry_id)
        stop.assert_awaited_once_with()
        await hass.async_stop()
        stop.assert_awaited_once_with()


@pytest.mark.parametrize("device_type", list(DeviceType))
async def test_shutdown_stops_backend(
    hass: HomeAssistant,
    setup_integration: SetupIntegration,
    device_type: DeviceType,
) -> None:
    """Home Assistant shutdown closes each supported panel connection."""
    result, entry = await setup_integration(data={CONF_TYPE: device_type})
    assert result
    coordinator = entry.runtime_data.coordinator
    connection = coordinator.connection
    with patch.object(
        connection, "async_panel_stop", wraps=connection.async_panel_stop
    ) as stop:
        await hass.async_stop()
        stop.assert_awaited_once_with()
    assert not coordinator.data.connected
    assert coordinator.data.mode == "stopped"


async def test_shutdown_logs_out_cloud_before_session_closes(
    hass: HomeAssistant,
) -> None:
    """Log out the real cloud backend while its shared HTTP session is usable."""
    entry = create_mock_config_entry(
        data={
            CONF_TYPE: DeviceType.CLOUD,
            CONF_PANEL_SERIAL: "ABCDEF",
            CONF_CLOUD_APP_ID: "test-app-id",
        }
    )
    entry.add_to_hass(hass)
    session = async_get_clientsession(hass)
    session_closed_during_logout: list[bool] = []

    async def logout() -> None:
        session_closed_during_logout.append(session.closed)

    with (
        patch(
            "homeassistant.components.visonic.cloud.API", autospec=True
        ) as api_factory,
        patch(
            "homeassistant.components.visonic.cloud.AlarmSystem", autospec=True
        ) as alarm_factory,
        patch(
            "homeassistant.components.visonic.cloud.VisonicCloudConnection.create_state_snapshot",
            return_value=VisonicCoordinatorData(connected=True),
        ),
        patch.object(hass.config_entries, "async_forward_entry_setups"),
    ):
        api = api_factory.return_value
        api.app_id = "test-app-id"
        api.authenticate_user.return_value = True
        api.get_panels.return_value = [
            {CONF_PANEL_SERIAL: "ABCDEF", TEXT_PANEL_MODEL: "PowerMaster 30"}
        ]
        alarm = alarm_factory.return_value
        alarm.api = api
        alarm.panel_login.return_value = True
        alarm.panel_logout.side_effect = logout
        assert await hass.config_entries.async_setup(entry.entry_id)
        alarm.panel_login.assert_awaited_once_with("ABCDEF", "")
        alarm.panel_logout.assert_not_awaited()
        await hass.async_stop()
        alarm.panel_logout.assert_awaited_once_with()
    assert session_closed_during_logout == [False]
    assert session.closed


@pytest.mark.parametrize("initial_state", [CoreState.not_running, CoreState.starting])
@pytest.mark.parametrize(
    ("device_type", "backend"),
    [
        pytest.param(DeviceType.ETHERNET, "VisonicDirectConnection", id="ethernet"),
        pytest.param(DeviceType.SERIAL, "VisonicDirectConnection", id="serial"),
        pytest.param(DeviceType.CLOUD, "VisonicCloudConnection", id="cloud"),
    ],
)
async def test_panel_connection_does_not_block_startup(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    initial_state: CoreState,
    device_type: DeviceType,
    backend: str,
) -> None:
    """Start Home Assistant before waiting for a panel, and retry until it responds."""
    hass.set_state(initial_state)
    entry = create_mock_config_entry(data={CONF_TYPE: device_type})
    entry.add_to_hass(hass)
    started = asyncio.Event()
    response = asyncio.Event()

    async def unresponsive_panel() -> bool:
        started.set()
        await response.wait()
        raise TimeoutError

    with (
        patch(
            f"homeassistant.components.visonic.coordinator.{backend}.async_panel_connect",
            side_effect=TimeoutError,
        ) as connect,
        patch(
            f"homeassistant.components.visonic.coordinator.{backend}.create_state_snapshot",
            return_value=VisonicCoordinatorData(connected=True),
        ),
        patch.object(hass.config_entries, "async_forward_entry_setups") as forward,
        patch.object(hass.config_entries, "async_unload_platforms", return_value=True),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state is ConfigEntryState.SETUP_RETRY
        assert not hasattr(entry, "runtime_data")
        connect.assert_not_awaited()
        forward.assert_not_awaited()

        connect.side_effect = unresponsive_panel
        await hass.async_start()
        await started.wait()
        assert hass.state is CoreState.running
        assert entry.state is ConfigEntryState.SETUP_IN_PROGRESS

        response.set()
        await hass.async_block_till_done(wait_background_tasks=True)
        assert entry.state is ConfigEntryState.SETUP_RETRY
        connect.assert_awaited_once_with()

        connect.side_effect = None
        connect.return_value = True
        freezer.tick(timedelta(seconds=30))
        async_fire_time_changed(hass, dt_util.utcnow())
        await hass.async_block_till_done(wait_background_tasks=True)
        assert entry.state is ConfigEntryState.LOADED
        assert entry.runtime_data.coordinator.data.connected
        assert connect.await_count == 2


@pytest.mark.parametrize(
    ("device_type", "panel_number"),
    [
        pytest.param(DeviceType.ETHERNET, 2, id="ethernet"),
        pytest.param(DeviceType.CLOUD, 3, id="cloud"),
        pytest.param(DeviceType.SERIAL, 4, id="serial"),
    ],
)
async def test_setup_success(
    setup_integration: SetupIntegration, device_type: DeviceType, panel_number: int
) -> None:
    """Create runtime data for each supported connection type."""
    result, entry = await setup_integration(
        data={CONF_TYPE: device_type, CONF_PANEL_NUMBER: panel_number}
    )
    assert result
    assert entry.runtime_data.panel_id == panel_number
    assert entry.runtime_data.coordinator is not None


async def test_setup_two_panels(setup_integration: SetupIntegration) -> None:
    """Separate panels receive independent runtime data."""
    result_a, entry_a = await setup_integration(
        data={CONF_TYPE: DeviceType.SERIAL, CONF_PANEL_NUMBER: 4}
    )
    result_b, entry_b = await setup_integration(
        data={CONF_TYPE: DeviceType.CLOUD, CONF_PANEL_NUMBER: 5}
    )
    assert result_a
    assert result_b
    assert entry_a.runtime_data.panel_id == 4
    assert entry_b.runtime_data.panel_id == 5
    assert entry_a.runtime_data is not entry_b.runtime_data


@pytest.mark.parametrize(
    ("data", "expected_calls"),
    [
        pytest.param(
            None, [call.async_panel_stop(), call.async_shutdown()], id="uninitialized"
        ),
        pytest.param(
            VisonicCoordinatorData(connected=True),
            [
                call.async_set_updated_data(
                    VisonicCoordinatorData(connected=False, mode="stopped")
                ),
                call.async_panel_stop(),
                call.async_shutdown(),
            ],
            id="initialized",
        ),
    ],
)
async def test_terminate_coordinator(
    data: VisonicCoordinatorData | None, expected_calls: list[object]
) -> None:
    """Publish a stopped snapshot when initialized, then stop and shut down in order."""
    coordinator = MagicMock()
    coordinator.data = data
    coordinator.async_panel_stop = AsyncMock()
    coordinator.async_shutdown = AsyncMock()
    await async_terminate_coordinator(coordinator)
    assert coordinator.mock_calls == expected_calls


async def test_terminate_missing_coordinator() -> None:
    """Cleanup is safe before a coordinator has been created."""
    await async_terminate_coordinator(None)


@pytest.mark.parametrize(
    ("connect_result", "exception", "expected_state"),
    [
        pytest.param(False, None, ConfigEntryState.SETUP_RETRY, id="false-result"),
        pytest.param(
            None,
            VisonicAuthException("bad credentials"),
            ConfigEntryState.SETUP_ERROR,
            id="auth",
        ),
        pytest.param(
            None, VisonicException("failed"), ConfigEntryState.SETUP_RETRY, id="library"
        ),
        pytest.param(
            None, TimeoutError("timeout"), ConfigEntryState.SETUP_RETRY, id="timeout"
        ),
        pytest.param(
            None, OSError("offline"), ConfigEntryState.SETUP_RETRY, id="os-error"
        ),
    ],
)
async def test_setup_entry_cleans_up_after_connect_failure(
    hass: HomeAssistant,
    connect_result: bool | None,
    exception: Exception | None,
    expected_state: ConfigEntryState,
) -> None:
    """Unload platforms and stop the coordinator while retaining its runtime reference."""
    entry = create_mock_config_entry(data={CONF_PANEL_NUMBER: 4})
    coordinator = MagicMock()
    coordinator.async_panel_connect = AsyncMock(
        return_value=connect_result, side_effect=exception
    )
    with (
        patch(f"{MODULE}.VisonicCoordinator", return_value=coordinator),
        patch.object(hass.config_entries, "async_forward_entry_setups", AsyncMock()),
        patch.object(
            hass.config_entries, "async_unload_platforms", return_value=True
        ) as unload,
        patch(f"{MODULE}.async_terminate_coordinator", AsyncMock()) as terminate,
    ):
        entry.add_to_hass(hass)
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_stop()
    assert entry.state is expected_state
    assert entry.runtime_data.coordinator is coordinator
    assert entry.runtime_data.panel_id == 4
    unload.assert_awaited_once()
    terminate.assert_awaited_once_with(coordinator)


@pytest.mark.parametrize(
    ("data", "unload_result"),
    [
        pytest.param({CONF_TYPE: "bad-type"}, True, id="invalid-type"),
        pytest.param({CONF_TYPE: DeviceType.CLOUD}, False, id="unload-failed"),
    ],
)
async def test_unload_entry_boundaries(
    hass: HomeAssistant,
    setup_integration: SetupIntegration,
    data: dict[str, str],
    unload_result: bool,
) -> None:
    """Failed unloading marks the entry as requiring a restart."""
    result, entry = await setup_integration(data={CONF_TYPE: DeviceType.CLOUD})
    assert result
    original_data = dict(entry.data)
    runtime_data = entry.runtime_data
    with (
        patch.object(hass.config_entries, "async_schedule_reload"),
        patch.object(
            hass.config_entries, "async_unload_platforms", return_value=unload_result
        ),
    ):
        hass.config_entries.async_update_entry(entry, data=data)
        await hass.async_block_till_done()
        assert not await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.FAILED_UNLOAD
    hass.config_entries.async_update_entry(entry, data=original_data)
    entry.runtime_data = runtime_data


async def test_unload_entry_without_runtime_data(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    """Missing runtime data makes the framework mark unloading as failed."""
    result, entry = await setup_integration(data={CONF_TYPE: DeviceType.CLOUD})
    assert result
    runtime_data = entry.runtime_data
    entry.runtime_data = None
    with patch.object(hass.config_entries, "async_unload_platforms", return_value=True):
        assert not await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.FAILED_UNLOAD
    entry.runtime_data = runtime_data


async def test_unload_entry_without_device_type(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    """Unload requires a connection type."""
    result, entry = await setup_integration()
    assert result
    original_data = dict(entry.data)
    with patch.object(hass.config_entries, "async_schedule_reload"):
        hass.config_entries.async_update_entry(entry, data={})
        await hass.async_block_till_done()
        assert not await hass.config_entries.async_unload(entry.entry_id)
    hass.config_entries.async_update_entry(entry, data=original_data)


async def test_current_entry_skips_migration(hass: HomeAssistant) -> None:
    """Set up the current entry version without requesting migration."""
    entry = create_mock_config_entry()
    entry.add_to_hass(hass)
    with (
        patch(
            f"{MODULE}.async_migrate_entry", new_callable=AsyncMock, create=True
        ) as migrate,
        patch(
            f"{MODULE}.VisonicCoordinator.async_panel_connect",
            side_effect=TimeoutError,
        ),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
    migrate.assert_not_called()
    assert entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    ("device_type", "error", "state"),
    [
        pytest.param(
            DeviceType.ETHERNET,
            OSError("offline"),
            ConfigEntryState.SETUP_RETRY,
            id="direct-offline",
        ),
        pytest.param(
            DeviceType.CLOUD,
            VisonicException("API failed"),
            ConfigEntryState.SETUP_RETRY,
            id="cloud-offline",
        ),
        pytest.param(
            DeviceType.CLOUD,
            VisonicAuthException("expired credentials"),
            ConfigEntryState.SETUP_ERROR,
            id="cloud-auth",
        ),
    ],
)
async def test_initial_refresh_failure(
    hass: HomeAssistant,
    device_type: DeviceType,
    error: Exception,
    state: ConfigEntryState,
) -> None:
    """Initial update errors propagate through first refresh and stop the backend."""
    entry = create_mock_config_entry(data={CONF_TYPE: device_type})
    entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.visonic.coordinator.VisonicDirectConnection.async_panel_connect",
            return_value=True,
        ),
        patch(
            "homeassistant.components.visonic.coordinator.VisonicCloudConnection.async_panel_connect",
            return_value=True,
        ),
        patch(
            "homeassistant.components.visonic.coordinator.VisonicCoordinator.create_state_snapshot",
            side_effect=error,
        ),
        patch.object(hass.config_entries, "async_forward_entry_setups"),
        patch.object(hass.config_entries, "async_unload_platforms", return_value=True),
        patch(
            "homeassistant.components.visonic.coordinator.VisonicCoordinator.async_panel_stop"
        ) as stop,
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state is state
        stop.assert_awaited_once()


async def test_initial_disconnected_state(hass: HomeAssistant) -> None:
    """Successful cloud login with an offline panel does not complete setup."""
    entry = create_mock_config_entry(data={CONF_TYPE: DeviceType.CLOUD})
    entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.visonic.coordinator.VisonicCloudConnection.async_panel_connect",
            return_value=True,
        ),
        patch(
            "homeassistant.components.visonic.coordinator.VisonicCloudConnection.create_state_snapshot",
            return_value=VisonicCoordinatorData(connected=False),
        ),
        patch.object(hass.config_entries, "async_forward_entry_setups"),
        patch.object(hass.config_entries, "async_unload_platforms", return_value=True),
        patch(
            "homeassistant.components.visonic.coordinator.VisonicCoordinator.async_panel_stop"
        ) as stop,
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state is ConfigEntryState.SETUP_RETRY
        stop.assert_awaited_once()


@pytest.mark.parametrize(
    "state",
    [
        pytest.param(ConfigEntryState.LOADED, id="loaded"),
        pytest.param(ConfigEntryState.NOT_LOADED, id="unloaded"),
    ],
)
async def test_setup_duplicate_endpoint(
    hass: HomeAssistant, state: ConfigEntryState
) -> None:
    """Previously saved duplicate endpoints cannot both be set up."""
    existing = create_mock_config_entry()
    existing.add_to_hass(hass)
    entry = create_mock_config_entry(data={CONF_PANEL_NUMBER: 2})
    entry.add_to_hass(hass)
    existing._async_set_state(hass, state, None)
    with patch(f"{MODULE}.VisonicCoordinator") as factory:
        assert not await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state is ConfigEntryState.SETUP_ERROR
        assert entry.error_reason_translation_key == "panel_already_configured"
        factory.assert_not_called()


async def test_cancelled_setup_cleanup(hass: HomeAssistant) -> None:
    """Cancelling initialization closes the active backend before propagating cancellation."""
    started = asyncio.Event()

    async def connect() -> bool:
        started.set()
        await asyncio.Event().wait()
        return True

    entry = create_mock_config_entry()
    entry.add_to_hass(hass)
    with (
        patch(f"{MODULE}.VisonicCoordinator.async_panel_connect", side_effect=connect),
        patch.object(hass.config_entries, "async_forward_entry_setups"),
        patch.object(hass.config_entries, "async_unload_platforms", return_value=True),
        patch(f"{MODULE}.VisonicCoordinator.async_panel_stop") as stop,
    ):
        task = asyncio.create_task(hass.config_entries.async_setup(entry.entry_id))
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        stop.assert_awaited_once_with()


@pytest.mark.usefixtures("mock_panel_connect", "mock_async_zeroconf")
async def test_numbered_panel_entity_name(hass: HomeAssistant) -> None:
    """The chosen panel number produces the familiar P1 alarm entity name."""
    entry = create_mock_config_entry(data={CONF_PANEL_NUMBER: 1})
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.visonic.direct.VisonicDirectConnection.create_state_snapshot",
        return_value=VisonicCoordinatorData(connected=True),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert hass.states.get("alarm_control_panel.visonic_alarm_p1") is not None
        assert entry.data[CONF_PANEL_NUMBER] == 1
        assert CONF_PANEL_NUMBER not in entry.options
        assert await hass.config_entries.async_unload(entry.entry_id)


async def test_setup_duplicate_number(hass: HomeAssistant) -> None:
    """Different endpoints cannot initialize entities with the same panel-number identity."""
    existing = create_mock_config_entry(data={CONF_PANEL_NUMBER: 1})
    existing.add_to_hass(hass)
    entry = create_mock_config_entry(
        data={CONF_PANEL_NUMBER: 1, CONF_HOST: "192.0.2.2"}
    )
    entry.add_to_hass(hass)
    with patch(f"{MODULE}.VisonicCoordinator") as factory:
        assert not await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state is ConfigEntryState.SETUP_ERROR
        assert entry.error_reason_translation_key == "number_in_config_not_unique"
        assert entry.error_reason_translation_placeholders == {
            "ident": "panel",
            "ref": "1",
        }
        factory.assert_not_called()

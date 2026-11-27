"""Test the bootstrap progress."""

import asyncio
from time import monotonic
from unittest.mock import Mock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    MockModule,
    async_fire_time_changed,
    mock_config_flow,
    mock_integration,
    mock_platform,
)

from homeassistant import bootstrap, config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_START
from homeassistant.core import CoreState, Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import bootstrap_progress
from homeassistant.helpers.bootstrap_progress import (
    BootstrapPhase,
    BootstrapProgress,
    async_subscribe_bootstrap_progress,
)
from homeassistant.helpers.typing import ConfigType


async def test_subscribe_bootstrap_progress(hass: HomeAssistant) -> None:
    """Test the bootstrap progress is only built and sent for subscribers."""
    progress = {"phase": "setup"}
    source = Mock(return_value=progress)
    first = Mock()
    unsubscribe_first = bootstrap_progress.async_subscribe_bootstrap_progress(
        hass, first
    )
    first.assert_not_called()

    bootstrap_progress._async_set_bootstrap_progress_source(hass, source)
    first.assert_called_once_with(progress)

    # A late subscriber gets the current progress right away.
    second = Mock()
    unsubscribe_second = bootstrap_progress.async_subscribe_bootstrap_progress(
        hass, second
    )
    second.assert_called_once_with(progress)

    unsubscribe_first()
    bootstrap_progress._async_dispatch_bootstrap_progress(hass)
    assert first.call_count == 1
    assert second.call_count == 2
    assert source.call_count == 3

    unsubscribe_second()
    bootstrap_progress._async_dispatch_bootstrap_progress(hass)
    assert second.call_count == 2
    assert source.call_count == 3


async def test_bootstrap_progress_listener_raises(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test a listener that raises does not stop the progress for the others."""
    progress = {"phase": "setup"}
    bootstrap_progress.async_subscribe_bootstrap_progress(
        hass, Mock(side_effect=ValueError)
    )
    listener = Mock()
    bootstrap_progress.async_subscribe_bootstrap_progress(hass, listener)

    bootstrap_progress._async_set_bootstrap_progress_source(
        hass, Mock(return_value=progress)
    )

    listener.assert_called_once_with(progress)
    assert "Error sending bootstrap progress to" in caplog.text


async def test_bootstrap_progress_late_listener_raises(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test a late listener that raises still gets its unsubscribe callback."""
    bootstrap_progress._async_set_bootstrap_progress_source(
        hass, Mock(return_value={"phase": "setup"})
    )
    listener = Mock(side_effect=ValueError)

    unsubscribe = bootstrap_progress.async_subscribe_bootstrap_progress(hass, listener)

    assert "Error sending bootstrap progress to" in caplog.text
    unsubscribe()
    bootstrap_progress._async_dispatch_bootstrap_progress(hass)
    listener.assert_called_once()


async def test_bootstrap_progress_listener_unsubscribes_itself(
    hass: HomeAssistant,
) -> None:
    """Test a listener unsubscribing itself does not skip the next listener."""
    progress = {"phase": "running"}
    first = Mock(side_effect=lambda _: unsubscribe_first())
    unsubscribe_first = bootstrap_progress.async_subscribe_bootstrap_progress(
        hass, first
    )
    second = Mock()
    bootstrap_progress.async_subscribe_bootstrap_progress(hass, second)

    bootstrap_progress._async_set_bootstrap_progress_source(
        hass, Mock(return_value=progress)
    )
    bootstrap_progress._async_dispatch_bootstrap_progress(hass)

    first.assert_called_once_with(progress)
    assert second.call_count == 2


def _track_bootstrap_progress(
    hass: HomeAssistant,
) -> list[tuple[CoreState, BootstrapProgress]]:
    """Record each bootstrap progress message with the core state it was sent in."""
    progress: list[tuple[CoreState, BootstrapProgress]] = []

    @callback
    def _progress(data: BootstrapProgress) -> None:
        progress.append((hass.state, data))

    async_subscribe_bootstrap_progress(hass, _progress)
    return progress


@pytest.mark.parametrize("load_registries", [False])
@patch("homeassistant.bootstrap.DEFAULT_INTEGRATIONS", set())
async def test_bootstrap_progress_concurrent_setup(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test progress lists concurrent setups as active and counts finished ones."""
    hass.set_state(CoreState.not_running)
    release = asyncio.Event()
    all_started = asyncio.Event()
    started: set[str] = set()

    def gen_domain_setup(domain: str):
        async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
            started.add(domain)
            if len(started) == 2:
                all_started.set()
            await release.wait()
            return True

        return async_setup

    for domain in ("integration_a", "integration_b"):
        mock_integration(
            hass, MockModule(domain=domain, async_setup=gen_domain_setup(domain))
        )
    progress = _track_bootstrap_progress(hass)

    setup_task = hass.async_create_task(
        bootstrap._async_set_up_integrations(
            hass, {"integration_a": {}, "integration_b": {}}, monotonic()
        )
    )
    await all_started.wait()
    freezer.tick(bootstrap_progress.SLOW_STARTUP_CHECK_INTERVAL)
    async_fire_time_changed(hass)
    _, blocked = progress[-1]
    release.set()
    await setup_task

    preparing = [
        data for _, data in progress if data["phase"] == BootstrapPhase.PREPARING
    ]
    assert preparing
    assert all(data["integrations"]["total"] is None for data in preparing)

    assert blocked["phase"] == BootstrapPhase.SETUP
    assert set(blocked["active"]) == {"integration_a", "integration_b"}
    assert blocked["integrations"]["done"] == blocked["integrations"]["total"] - 2

    _, final = progress[-1]
    assert final["phase"] == BootstrapPhase.WRAP_UP
    assert final["active"] == {}
    assert final["integrations"]["done"] == final["integrations"]["total"]
    assert final["integrations"]["failed"] == []


@pytest.mark.parametrize("load_registries", [False])
@patch("homeassistant.bootstrap.DEFAULT_INTEGRATIONS", set())
async def test_bootstrap_progress_failures_and_running_summary(
    hass: HomeAssistant,
) -> None:
    """Test failed integrations are reported and the running summary is final."""
    hass.set_state(CoreState.not_running)
    retry_attempt = asyncio.Event()

    async def async_setup_entry_retry(hass: HomeAssistant, entry: ConfigEntry) -> None:
        if not retry_attempt.is_set():
            retry_attempt.set()
            raise ConfigEntryNotReady
        await asyncio.Event().wait()

    async def async_setup_failed(hass: HomeAssistant, config: ConfigType) -> bool:
        return False

    mock_integration(
        hass, MockModule(domain="integration_fail", async_setup=async_setup_failed)
    )
    mock_integration(
        hass,
        MockModule(
            domain="integration_retry", async_setup_entry=async_setup_entry_retry
        ),
    )
    mock_platform(hass, "integration_retry.config_flow", None)
    MockConfigEntry(domain="integration_retry").add_to_hass(hass)
    progress = _track_bootstrap_progress(hass)

    with mock_config_flow("integration_retry", config_entries.ConfigFlow):
        await bootstrap._async_set_up_integrations(
            hass, {"integration_fail": {}, "integration_retry": {}}, monotonic()
        )
        _, final = progress[-1]
        # The entry sets up again once Home Assistant has started.
        await hass.async_start()

    assert final["phase"] == BootstrapPhase.WRAP_UP
    assert final["integrations"]["done"] == final["integrations"]["total"]
    assert final["integrations"]["failed"] == ["integration_fail"]

    _, running = progress[-1]
    assert running["phase"] == BootstrapPhase.RUNNING
    assert running["integrations"] == final["integrations"]
    # A late subscriber gets the summary from when Core started running.
    assert _track_bootstrap_progress(hass) == [(CoreState.running, running)]


@pytest.mark.parametrize("load_registries", [False])
@patch("homeassistant.bootstrap.DEFAULT_INTEGRATIONS", set())
async def test_bootstrap_progress_cancelled_entry_setup(hass: HomeAssistant) -> None:
    """Test a setup cancelled during its config entry setup counts as failed."""
    hass.set_state(CoreState.not_running)

    async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
        # Cancel like a stage timeout, after the domain was added to components.
        task = asyncio.current_task()
        assert task is not None
        task.cancel()
        await asyncio.Event().wait()
        return True

    mock_integration(
        hass,
        MockModule(domain="integration_cancel", async_setup_entry=async_setup_entry),
    )
    mock_platform(hass, "integration_cancel.config_flow", None)
    MockConfigEntry(domain="integration_cancel").add_to_hass(hass)
    progress = _track_bootstrap_progress(hass)

    with mock_config_flow("integration_cancel", config_entries.ConfigFlow):
        await bootstrap._async_set_up_integrations(
            hass, {"integration_cancel": {}}, monotonic()
        )

    _, final = progress[-1]
    assert "integration_cancel" in hass.config.components
    assert final["integrations"] == {
        "total": 1,
        "done": 1,
        "failed": ["integration_cancel"],
    }


@pytest.mark.parametrize("load_registries", [False])
@patch("homeassistant.bootstrap.DEFAULT_INTEGRATIONS", set())
async def test_bootstrap_progress_unscheduled_dependency(hass: HomeAssistant) -> None:
    """Test a dependency no stage sets up does not keep progress below the total."""
    hass.set_state(CoreState.not_running)
    mock_integration(hass, MockModule(domain="dependency_only"))
    # The after dependency cycle drops both from the domains to set up.
    mock_integration(
        hass,
        MockModule(
            domain="cycle_a",
            dependencies=["dependency_only"],
            partial_manifest={"after_dependencies": ["cycle_b"]},
        ),
    )
    mock_integration(
        hass,
        MockModule(
            domain="cycle_b", partial_manifest={"after_dependencies": ["cycle_a"]}
        ),
    )
    progress = _track_bootstrap_progress(hass)

    await bootstrap._async_set_up_integrations(
        hass, {"cycle_a": {}, "cycle_b": {}}, monotonic()
    )

    _, final = progress[-1]
    assert "dependency_only" not in hass.config.components
    assert final["integrations"] == {
        "total": 2,
        "done": 2,
        "failed": ["cycle_a", "cycle_b"],
    }


@pytest.mark.parametrize("load_registries", [False])
@patch("homeassistant.bootstrap.DEFAULT_INTEGRATIONS", set())
@pytest.mark.parametrize(
    ("modules", "total", "failed"),
    [
        pytest.param(
            [
                MockModule(domain="good_integration"),
                MockModule(
                    domain="bad_integration", dependencies=["missing_integration"]
                ),
            ],
            3,
            ["bad_integration", "not_found"],
            id="missing_dependency",
        ),
        pytest.param(
            [
                MockModule(domain="good_integration"),
                MockModule(domain="bad_integration", dependencies=["bad_integration"]),
            ],
            3,
            ["bad_integration", "not_found"],
            id="circular_dependency",
        ),
        pytest.param(
            [
                MockModule(domain="good_integration", dependencies=["intermediate"]),
                MockModule(
                    domain="intermediate",
                    partial_manifest={"after_dependencies": ["bad_integration"]},
                ),
                MockModule(
                    domain="bad_integration",
                    partial_manifest={"after_dependencies": ["intermediate"]},
                ),
            ],
            4,
            ["bad_integration", "good_integration", "intermediate", "not_found"],
            id="dependency_in_after_dependency_cycle",
        ),
    ],
)
async def test_bootstrap_progress_unresolved_dependencies(
    hass: HomeAssistant, modules: list[MockModule], total: int, failed: list[str]
) -> None:
    """Test integrations dropped while resolving dependencies count as failed."""
    hass.set_state(CoreState.not_running)
    for module in modules:
        mock_integration(hass, module)
    progress = _track_bootstrap_progress(hass)

    await bootstrap._async_set_up_integrations(
        hass,
        {"good_integration": {}, "bad_integration": {}, "not_found": {}},
        monotonic(),
    )

    _, final = progress[-1]
    assert final["integrations"] == {
        "total": total,
        "done": total,
        "failed": failed,
    }


@pytest.mark.parametrize("load_registries", [False])
@patch("homeassistant.bootstrap.DEFAULT_INTEGRATIONS", set())
async def test_bootstrap_progress_running_transition(hass: HomeAssistant) -> None:
    """Test progress reports starting and running only on the core state change."""
    hass.set_state(CoreState.not_running)
    mock_integration(hass, MockModule(domain="normal_integration"))
    progress = _track_bootstrap_progress(hass)

    await bootstrap._async_set_up_integrations(
        hass, {"normal_integration": {}}, monotonic() - 100
    )
    # Elapsed counts from the given start of Home Assistant.
    assert progress[0][1]["elapsed"] >= 100
    state, data = progress[-1]
    assert state is CoreState.not_running
    assert data["phase"] == BootstrapPhase.WRAP_UP

    await hass.async_start()

    assert [(state, data["phase"]) for state, data in progress[-2:]] == [
        (CoreState.starting, BootstrapPhase.STARTING),
        (CoreState.running, BootstrapPhase.RUNNING),
    ]
    assert _track_bootstrap_progress(hass) == [progress[-1]]


@pytest.mark.parametrize("load_registries", [False])
@patch("homeassistant.bootstrap.DEFAULT_INTEGRATIONS", set())
async def test_bootstrap_progress_while_starting(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test progress keeps updating while starting."""
    hass.set_state(CoreState.not_running)
    entry_setup_started = asyncio.Event()
    release_entry = asyncio.Event()
    start_listener_running = asyncio.Event()
    release_start = asyncio.Event()

    async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
        entry_setup_started.set()
        await release_entry.wait()

    async def slow_start_listener(event: Event) -> None:
        start_listener_running.set()
        await release_start.wait()

    mock_integration(
        hass, MockModule(domain="integration_new", async_setup_entry=async_setup_entry)
    )
    mock_platform(hass, "integration_new.config_flow", None)
    progress = _track_bootstrap_progress(hass)

    with mock_config_flow("integration_new", config_entries.ConfigFlow):
        await bootstrap._async_set_up_integrations(
            hass, {"integration_new": {}}, monotonic()
        )
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, slow_start_listener)
        start_task = hass.async_create_task(hass.async_start())
        await start_listener_running.wait()

        entry = MockConfigEntry(domain="integration_new")
        entry.add_to_hass(hass)
        add_task = hass.async_create_background_task(
            hass.config_entries.async_setup(entry.entry_id), "set up new entry"
        )
        await entry_setup_started.wait()

        message_count = len(progress)
        freezer.tick(bootstrap_progress.SLOW_STARTUP_CHECK_INTERVAL)
        async_fire_time_changed(hass)
        assert len(progress) == message_count + 1
        state, data = progress[-1]
        assert state is CoreState.starting
        assert data["phase"] == BootstrapPhase.STARTING
        assert "integration_new" in data["active"]

        release_start.set()
        await start_task
        _, running = progress[-1]
        assert running["phase"] == BootstrapPhase.RUNNING
        # The kept running summary does not list the entry still setting up.
        assert running["active"] == {}

        message_count = len(progress)
        freezer.tick(bootstrap_progress.SLOW_STARTUP_CHECK_INTERVAL)
        async_fire_time_changed(hass)
        assert len(progress) == message_count

        release_entry.set()
        await add_task


@pytest.mark.parametrize("load_registries", [False])
@pytest.mark.usefixtures("enable_custom_integrations")
@patch("homeassistant.bootstrap.DEFAULT_INTEGRATIONS", set())
@pytest.mark.parametrize(
    ("safe_mode", "total"),
    [
        pytest.param(False, 2, id="normal_mode"),
        pytest.param(True, 0, id="safe_mode"),
    ],
)
async def test_bootstrap_progress_custom_integrations(
    hass: HomeAssistant, safe_mode: bool, total: int
) -> None:
    """Test custom integrations skipped in safe mode do not count as failed."""
    hass.set_state(CoreState.not_running)
    hass.config.safe_mode = safe_mode
    MockConfigEntry(domain="test_package_loaded_executor").add_to_hass(hass)
    progress = _track_bootstrap_progress(hass)

    await bootstrap._async_set_up_integrations(hass, {"test_package": {}}, monotonic())

    _, final = progress[-1]
    assert final["integrations"] == {"total": total, "done": total, "failed": []}


@pytest.mark.parametrize("load_registries", [False])
@patch("homeassistant.bootstrap.DEFAULT_INTEGRATIONS", set())
async def test_bootstrap_progress_late_subscriber(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test progress is only built for subscribers, a late one gets it right away."""
    hass.set_state(CoreState.not_running)
    setup_started = asyncio.Event()
    release = asyncio.Event()

    async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
        setup_started.set()
        await release.wait()
        return True

    mock_integration(
        hass, MockModule(domain="slow_integration", async_setup=async_setup)
    )

    with patch.object(
        bootstrap_progress.WatchPendingSetups,
        "_async_progress",
        autospec=True,
        side_effect=bootstrap_progress.WatchPendingSetups._async_progress,
    ) as build_progress:
        setup_task = hass.async_create_task(
            bootstrap._async_set_up_integrations(
                hass, {"slow_integration": {}}, monotonic()
            )
        )
        await setup_started.wait()
        freezer.tick(bootstrap_progress.SLOW_STARTUP_CHECK_INTERVAL)
        async_fire_time_changed(hass)
        build_progress.assert_not_called()

        progress = _track_bootstrap_progress(hass)
        build_progress.assert_called_once()
        freezer.tick(bootstrap_progress.SLOW_STARTUP_CHECK_INTERVAL)
        async_fire_time_changed(hass)
        release.set()
        await setup_task

    (_, current), (_, tick), *_ = progress
    assert current["phase"] == BootstrapPhase.SETUP
    assert set(current["active"]) == {"slow_integration"}
    assert current["integrations"] == {"total": 1, "done": 0, "failed": []}
    assert tick["active"]["slow_integration"] > current["active"]["slow_integration"]
    _, final = progress[-1]
    assert final["integrations"] == {"total": 1, "done": 1, "failed": []}


@pytest.mark.parametrize("load_registries", [False])
@patch("homeassistant.bootstrap.DEFAULT_INTEGRATIONS", set())
async def test_bootstrap_progress_listener_raises_during_bootstrap(
    hass: HomeAssistant,
) -> None:
    """Test a progress listener that raises does not stop bootstrap."""
    hass.set_state(CoreState.not_running)
    mock_integration(hass, MockModule(domain="normal_integration"))
    async_subscribe_bootstrap_progress(hass, Mock(side_effect=ValueError))
    progress = _track_bootstrap_progress(hass)

    await bootstrap._async_set_up_integrations(
        hass, {"normal_integration": {}}, monotonic()
    )
    await hass.async_start()

    assert "normal_integration" in hass.config.components
    _, running = progress[-1]
    assert running["phase"] == BootstrapPhase.RUNNING


@pytest.mark.parametrize("load_registries", [False])
@patch("homeassistant.bootstrap.DEFAULT_INTEGRATIONS", set())
async def test_bootstrap_progress_stopped_while_starting(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test progress stops updating when Core stops while starting."""
    hass.set_state(CoreState.not_running)
    start_listener_running = asyncio.Event()

    async def slow_start_listener(event: Event) -> None:
        start_listener_running.set()
        await asyncio.Event().wait()

    mock_integration(hass, MockModule(domain="normal_integration"))
    progress = _track_bootstrap_progress(hass)

    await bootstrap._async_set_up_integrations(
        hass, {"normal_integration": {}}, monotonic()
    )
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, slow_start_listener)
    start_task = hass.async_create_task(hass.async_start())
    await start_listener_running.wait()

    await hass.async_stop()
    assert start_task.cancelled()
    assert hass.state is CoreState.stopped

    message_count = len(progress)
    freezer.tick(bootstrap_progress.SLOW_STARTUP_CHECK_INTERVAL)
    async_fire_time_changed(hass)
    assert len(progress) == message_count

"""Test the recorder keeps retrying a database that is not ready at startup."""

import asyncio
from functools import partial
import threading
import time
from typing import Any
from unittest.mock import Mock, patch

import pytest
from pytest_homeassistant.typing import RecorderInstanceContextManager
from sqlalchemy import exc

from homeassistant.components.recorder import Recorder, get_instance, migration
from homeassistant.components.recorder.const import DB_SETUP_RETRY_WAIT_MAX
from homeassistant.components.recorder.db_schema import SCHEMA_VERSION
from homeassistant.components.recorder.models import UnsupportedDialect
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers import recorder as recorder_helper
from homeassistant.setup import async_setup_component


@pytest.fixture
async def mock_recorder_before_hass(
    async_test_recorder: RecorderInstanceContextManager,
) -> None:
    """Set up recorder."""


def _unstarted_recorder(hass: HomeAssistant) -> Recorder:
    """Return a recorder whose thread was never started.

    Its thread methods can be called directly without touching a live one.
    """
    recorder_helper.async_initialize_recorder(hass)
    return Recorder(
        hass=hass,
        auto_purge=False,
        auto_repack=False,
        keep_days=10,
        commit_interval=1,
        uri="postgresql://u@db/ha",
        db_max_retries=1,
        db_retry_wait=0,
        entity_filter=None,
        exclude_event_types=set(),
    )


class _FakeClock:
    """A clock where sleeping advances time and nothing else does."""

    START = 1000.0

    def __init__(self) -> None:
        self.now = self.START

    def monotonic(self) -> float:
        """Return the fake time."""
        return self.now

    def sleep(self, seconds: float) -> None:
        """Advance the fake time."""
        self.now += seconds

    def __getattr__(self, name: str) -> Any:
        """Delegate everything else to the real time module."""
        return getattr(time, name)


@pytest.mark.parametrize("state", [CoreState.not_running, CoreState.running])
async def test_extends_retries_past_db_max_retries(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    state: CoreState,
) -> None:
    """A database that appears after db_max_retries is still picked up.

    not_running is the state integration setup actually runs in: async_run()
    only moves to starting once bootstrap has set every integration up.
    """
    instance = _unstarted_recorder(hass)
    instance.db_url = "postgresql://u@db/ha"
    instance.db_max_retries = 2
    instance.db_retry_wait = 0

    hass.set_state(state)
    try:
        with (
            patch.object(instance, "_close_connection"),
            patch("homeassistant.components.recorder.core.DB_SETUP_RETRY_WAIT_MIN", 0),
            patch.object(
                instance,
                "_try_setup_recorder_once",
                side_effect=[(None, True), (None, True), (True, False)],
            ) as attempt,
        ):
            assert (
                await hass.async_add_executor_job(
                    partial(instance._setup_recorder, extended_retry=True)
                )
                is True
            )
    finally:
        hass.set_state(CoreState.running)

    assert attempt.call_count == 3
    assert "retrying for up to" in caplog.text
    assert "Database is reachable again" in caplog.text


async def test_extended_retry_wait_is_capped(
    hass: HomeAssistant,
) -> None:
    """db_retry_wait has no upper bound, the extended backoff does."""
    instance = _unstarted_recorder(hass)
    instance.db_retry_wait = 600

    with (
        patch.object(instance, "_close_connection"),
        patch.object(instance, "_sleep_unless_stopping", return_value=False) as sleep,
    ):
        assert (
            await hass.async_add_executor_job(
                instance._setup_recorder_extended, time.monotonic() + 600
            )
            is False
        )

    assert sleep.call_args[0][0] == DB_SETUP_RETRY_WAIT_MAX


async def test_setup_returns_before_the_retrying_finishes(
    hass: HomeAssistant,
) -> None:
    """Setup is released once the retrying starts, not when it ends."""
    instance = _unstarted_recorder(hass)
    instance.db_url = "postgresql://u@db/ha"
    instance.db_max_retries = 1
    instance.db_retry_wait = 0
    instance.async_setup_complete = hass.loop.create_future()

    retrying = asyncio.Event()
    release = threading.Event()

    def _block_until_released(wait: float) -> bool:
        hass.loop.call_soon_threadsafe(retrying.set)
        # Hold the retry loop open until the assertion below has run
        release.wait(10)
        return False

    with (
        patch.object(instance, "_close_connection"),
        patch.object(instance, "_try_setup_recorder_once", return_value=(None, True)),
        patch.object(
            instance, "_sleep_unless_stopping", side_effect=_block_until_released
        ),
    ):
        task = hass.async_add_executor_job(
            partial(instance._setup_recorder, extended_retry=True)
        )
        await retrying.wait()
        # The point of the change: this resolves while the recorder thread is
        # still inside the retry loop, rather than after it gives up.
        assert not task.done()
        assert await instance.async_setup_complete is True
        assert not task.done()
        release.set()
        assert await task is False


async def test_gives_up_after_max_db_setup_wait(
    hass: HomeAssistant,
) -> None:
    """A database that never appears still fails, as it did before."""
    instance = _unstarted_recorder(hass)
    instance.db_url = "postgresql://u@db/ha"
    instance.db_max_retries = 1
    instance.db_retry_wait = 0
    clock = _FakeClock()

    with (
        patch.object(instance, "_close_connection"),
        patch("homeassistant.components.recorder.core.time", clock),
        patch("homeassistant.components.recorder.core.MAX_DB_SETUP_WAIT", 12),
        patch.object(
            instance, "_try_setup_recorder_once", return_value=(None, True)
        ) as attempt,
    ):
        assert (
            await hass.async_add_executor_job(
                partial(instance._setup_recorder, extended_retry=True)
            )
            is False
        )

    # The fast attempt at 0s, then 5s, then the clamped 7s wait lands on the
    # 12s deadline, where one last attempt may still start; nothing after it.
    assert attempt.call_count == 3
    assert clock.now == _FakeClock.START + 12


async def test_corruption_recovery_does_not_extend(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The sqlite-corruption path keeps the original fast budget."""
    instance = _unstarted_recorder(hass)
    # A network URL, so only the extended_retry flag keeps this on the fast path
    instance.db_url = "postgresql://u@db/ha"
    instance.db_max_retries = 2
    instance.db_retry_wait = 0
    caplog.clear()

    with (
        patch.object(instance, "_close_connection"),
        patch.object(
            instance, "_try_setup_recorder_once", return_value=(None, True)
        ) as attempt,
    ):
        assert await hass.async_add_executor_job(instance._setup_recorder) is False

    assert attempt.call_count == 2
    assert "retrying for up to" not in caplog.text


async def test_expired_budget_does_not_release_setup(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A fast phase that used up the window neither logs nor releases setup."""
    instance = _unstarted_recorder(hass)
    instance.db_url = "postgresql://u@db/ha"
    instance.db_max_retries = 1
    instance.db_retry_wait = 0
    instance.async_setup_complete = hass.loop.create_future()
    caplog.clear()

    with (
        patch.object(instance, "_close_connection"),
        patch("homeassistant.components.recorder.core.MAX_DB_SETUP_WAIT", -1),
        patch.object(
            instance, "_try_setup_recorder_once", return_value=(None, True)
        ) as attempt,
    ):
        assert (
            await hass.async_add_executor_job(
                partial(instance._setup_recorder, extended_retry=True)
            )
            is False
        )

    assert attempt.call_count == 1
    assert "retrying for up to" not in caplog.text
    assert not instance.async_setup_complete.done()


@pytest.mark.parametrize(
    ("result", "cancelled", "expected"),
    [
        (None, False, False),
        (True, False, True),
        (False, False, False),
        (None, True, False),
    ],
    ids=["pending", "ready", "gave_up", "cancelled"],
)
async def test_database_ready_property(
    hass: HomeAssistant,
    result: bool | None,
    cancelled: bool,
    expected: bool,
) -> None:
    """database_ready is only True once the database resolved as ready."""
    instance = _unstarted_recorder(hass)
    instance.async_db_ready = hass.loop.create_future()
    if result is not None:
        instance.async_db_ready.set_result(result)
    if cancelled:
        instance.async_db_ready.cancel()

    assert instance.database_ready is expected


@pytest.mark.parametrize(
    ("error", "connect_failed"),
    [
        (exc.OperationalError("stmt", {}, Exception("refused")), True),
        (exc.InterfaceError("stmt", {}, Exception("closed")), True),
        (exc.ProgrammingError("stmt", {}, Exception("no privilege")), False),
        (ModuleNotFoundError("psycopg2"), False),
    ],
)
async def test_only_connection_errors_count_as_unreachable(
    hass: HomeAssistant,
    error: Exception,
    connect_failed: bool,
) -> None:
    """URL, driver and privilege errors do not enter the extended phase."""
    instance = _unstarted_recorder(hass)

    with patch.object(instance, "_setup_connection", side_effect=error):
        result = await hass.async_add_executor_job(
            partial(instance._try_setup_recorder_once, log_exception=False)
        )

    assert result == (None, connect_failed)


@pytest.mark.parametrize(
    ("connected_first", "connect_failed"),
    [(False, True), (True, False)],
    ids=["before_connect", "after_connect"],
)
async def test_operational_error_after_connecting_is_not_unreachable(
    hass: HomeAssistant, connected_first: bool, connect_failed: bool
) -> None:
    """An OperationalError once the first connect completed is not a retry."""
    instance = _unstarted_recorder(hass)

    def _fail(*args: Any) -> None:
        # The connect hook has run when schema inspection or DDL fails
        instance._completed_first_database_setup = connected_first
        raise exc.OperationalError("stmt", {}, Exception("failed"))

    with patch.object(instance, "_setup_connection", side_effect=_fail):
        result = await hass.async_add_executor_job(
            partial(instance._try_setup_recorder_once, log_exception=False)
        )

    assert result == (None, connect_failed)


async def test_extended_retry_stops_on_a_non_connection_error(
    hass: HomeAssistant,
) -> None:
    """A database that came up but fails for another reason is not waited on."""
    instance = _unstarted_recorder(hass)

    with (
        patch.object(instance, "_close_connection"),
        patch.object(instance, "_sleep_unless_stopping", return_value=True),
        patch.object(
            instance, "_try_setup_recorder_once", return_value=(None, False)
        ) as attempt,
    ):
        assert (
            await hass.async_add_executor_job(
                instance._setup_recorder_extended, time.monotonic() + 600
            )
            is False
        )

    assert attempt.call_count == 1


@pytest.mark.parametrize(
    ("released_early", "current_version", "refused"),
    [
        (True, 1, True),
        (False, 1, False),
        # Live-compatible upgrades still recover after an early release
        (True, migration.LIVE_MIGRATION_MIN_SCHEMA_VERSION, False),
    ],
)
async def test_late_database_needing_offline_migration(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    released_early: bool,
    current_version: int,
    refused: bool,
) -> None:
    """A database reached after setup was released is not migrated offline."""
    instance = _unstarted_recorder(hass)
    instance._setup_released_early = released_early
    status = migration.SchemaValidationStatus(
        current_version=current_version,
        initial_version=1,
        migration_needed=True,
        non_live_data_migration_needed=False,
        schema_errors=set(),
        start_version=1,
    )
    caplog.clear()

    with (
        patch.object(instance, "_setup_recorder", return_value=True),
        patch.object(migration, "validate_db_schema", return_value=status),
        patch.object(
            instance, "_migrate_schema_offline", return_value=(False, status)
        ) as migrate,
        patch.object(instance, "_notify_migration_failed"),
        patch.object(instance, "_setup_run"),
        patch.object(instance, "async_connection_success"),
    ):
        await hass.async_add_executor_job(instance._run)

    assert migrate.called is (not refused)
    assert ("needs an offline migration" in caplog.text) is refused


@pytest.mark.parametrize("stop_via", ["event", "hass_state", None])
@pytest.mark.parametrize("released_early", [True, False])
async def test_restart_during_the_retry_window_is_not_a_failure(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    stop_via: str | None,
    released_early: bool,
) -> None:
    """A stop while retrying neither logs a setup failure nor notifies.

    Outside the retry window (setup never released) behaviour is the base one.
    """
    instance = _unstarted_recorder(hass)
    instance._setup_released_early = released_early
    quiet = released_early and stop_via is not None
    if stop_via == "event":
        instance._shutdown_requested.set()
    if stop_via == "hass_state":
        hass.set_state(CoreState.stopping)
    caplog.clear()

    try:
        with (
            patch.object(instance, "_setup_recorder", return_value=False),
            patch.object(instance, "_end_session"),
            patch.object(instance, "_close_connection"),
            patch.object(instance, "_async_startup_done") as startup_done,
        ):
            await hass.async_add_executor_job(instance.run)
            await hass.async_block_till_done()
    finally:
        hass.set_state(CoreState.running)

    assert ("Recorder setup failed" in caplog.text) is not quiet
    startup_done.assert_called_once_with(not quiet)


async def test_a_refused_late_database_still_reports_the_failure(
    hass: HomeAssistant,
) -> None:
    """Refusing an offline migration raises the could-not-start notification.

    The schema is already current, only a non-live data migration is needed,
    so schema_version must not be recorded as a good state first.
    """
    instance = _unstarted_recorder(hass)
    instance._setup_released_early = True
    status = migration.SchemaValidationStatus(
        current_version=SCHEMA_VERSION,
        initial_version=1,
        migration_needed=False,
        non_live_data_migration_needed=True,
        schema_errors=set(),
        start_version=1,
    )

    with (
        patch.object(instance, "_setup_recorder", return_value=True),
        patch.object(migration, "validate_db_schema", return_value=status),
        patch.object(instance, "_end_session"),
        patch.object(instance, "_close_connection"),
        patch.object(instance, "_async_startup_done") as startup_done,
    ):
        await hass.async_add_executor_job(instance.run)
        await hass.async_block_till_done()

    startup_done.assert_called_once_with(True)


async def test_a_stop_before_the_release_does_not_announce_the_retrying(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shutdown that began during the fast phase releases nothing."""
    instance = _unstarted_recorder(hass)
    instance._shutdown_requested.set()

    with (
        patch.object(instance, "_close_connection"),
        patch.object(
            instance, "_try_setup_recorder_once", return_value=(None, True)
        ) as attempt,
        patch.object(instance, "_setup_recorder_extended") as extended,
    ):
        assert (
            await hass.async_add_executor_job(
                partial(instance._setup_recorder, extended_retry=True)
            )
            is False
        )

    assert attempt.call_count == 1
    extended.assert_not_called()
    assert not instance._setup_released_early
    assert "retrying for up to" not in caplog.text


async def test_queries_wait_for_a_database_that_arrives_late(
    hass: HomeAssistant,
) -> None:
    """After an early release a job waits for db ready instead of failing."""
    instance = _unstarted_recorder(hass)
    instance._setup_released_early = True
    instance.async_db_ready = hass.loop.create_future()

    job = instance.async_add_executor_job(lambda: "ran")
    await asyncio.sleep(0)
    assert not job.done()

    instance.async_db_ready.set_result(True)
    assert await job == "ran"


async def test_cancelling_a_waiting_job_does_not_stop_the_database(
    hass: HomeAssistant,
) -> None:
    """Cancelling one queued job leaves readiness and the other jobs alone."""
    instance = _unstarted_recorder(hass)
    instance._setup_released_early = True
    instance.async_db_ready = hass.loop.create_future()

    cancelled = instance.async_add_executor_job(lambda: "cancelled")
    waiting = instance.async_add_executor_job(lambda: "ran")
    await asyncio.sleep(0)
    cancelled.cancel()
    await asyncio.sleep(0)

    assert not instance.async_db_ready.cancelled()
    instance.async_db_ready.set_result(True)
    assert await waiting == "ran"


async def test_queries_fail_cleanly_when_the_database_never_arrives(
    hass: HomeAssistant,
) -> None:
    """A recorder that gave up fails queued jobs with a plain error."""
    instance = _unstarted_recorder(hass)
    instance._setup_released_early = True
    instance.async_db_ready = hass.loop.create_future()

    job = instance.async_add_executor_job(lambda: "ran")
    instance.async_db_ready.set_result(False)

    with pytest.raises(RuntimeError, match="has not been established"):
        await job


async def test_queries_after_give_up_never_run(
    hass: HomeAssistant,
) -> None:
    """A job queued after the retrying gave up fails without running at all."""
    instance = _unstarted_recorder(hass)
    instance._setup_released_early = True
    instance.async_db_ready = hass.loop.create_future()
    instance.async_db_ready.set_result(False)
    target = Mock(return_value="ran")

    with pytest.raises(RuntimeError, match="has not been established"):
        await instance.async_add_executor_job(target)

    target.assert_not_called()


async def test_queries_run_at_once_without_an_early_release(
    hass: HomeAssistant,
) -> None:
    """The normal path is untouched: no waiting when setup was not released."""
    instance = _unstarted_recorder(hass)
    instance.async_db_ready = hass.loop.create_future()

    assert await instance.async_add_executor_job(lambda: "ran") == "ran"


async def test_async_setup_returns_while_the_database_is_unreachable(
    hass: HomeAssistant,
) -> None:
    """recorder.async_setup returns while the retrying is still going on."""
    recorder_helper.async_initialize_recorder(hass)
    gate = threading.Event()
    attempts = 0

    def _connect(self: Recorder) -> None:
        nonlocal attempts
        attempts += 1
        if attempts > 1:
            # Hold the extended retrying open until the assertions have run
            gate.wait(10)
        raise exc.OperationalError("stmt", {}, Exception("refused"))

    with (
        patch(
            "homeassistant.components.recorder.core.Recorder._setup_connection",
            _connect,
        ),
        patch("homeassistant.components.recorder.core.Recorder._close_connection"),
        patch("homeassistant.components.recorder.core.DB_SETUP_RETRY_WAIT_MIN", 0),
    ):
        async with asyncio.timeout(10):
            assert await async_setup_component(
                hass,
                "recorder",
                {
                    "recorder": {
                        "db_url": "postgresql://u@db/ha",
                        "db_max_retries": 1,
                        "db_retry_wait": 0,
                    }
                },
            )
        instance = get_instance(hass)
        assert instance._setup_released_early
        assert not instance.async_db_ready.done()

        gate.set()
        async with asyncio.timeout(10):
            assert await instance.async_db_ready is False
            # Do not leave the recorder thread running past the test
            await hass.async_add_executor_job(instance.join)


async def test_stop_signal_outlives_the_hass_state(
    hass: HomeAssistant,
) -> None:
    """Once close or final write was seen, the retrying stays stopped.

    hass.is_stopping goes back to false after final write, so a connect that
    outlasts the stop stages would otherwise keep retrying into teardown.
    """
    instance = _unstarted_recorder(hass)
    assert hass.state is CoreState.running
    instance._shutdown_requested.set()

    assert (
        await hass.async_add_executor_job(instance._sleep_unless_stopping, 60) is False
    )

    with (
        patch.object(instance, "_close_connection"),
        patch.object(
            instance, "_try_setup_recorder_once", return_value=(None, True)
        ) as attempt,
    ):
        assert (
            await hass.async_add_executor_job(
                instance._setup_recorder_extended, time.monotonic() + 600
            )
            is False
        )

    assert attempt.call_count == 0


async def test_reaching_the_database_during_teardown_does_not_start_up(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A late connect that finishes after shutdown began is abandoned."""
    instance = _unstarted_recorder(hass)
    caplog.clear()

    def _connect_during_shutdown(*, log_exception: bool) -> tuple[bool, bool]:
        instance._shutdown_requested.set()
        return True, False

    with (
        patch.object(instance, "_close_connection"),
        patch.object(instance, "_sleep_unless_stopping", return_value=True),
        patch.object(
            instance, "_try_setup_recorder_once", side_effect=_connect_during_shutdown
        ),
    ):
        assert (
            await hass.async_add_executor_job(
                instance._setup_recorder_extended, time.monotonic() + 600
            )
            is False
        )

    assert "reachable again" not in caplog.text


async def test_terminal_failures_name_their_cause(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The failure that ends the extended phase is logged where it is seen."""
    instance = _unstarted_recorder(hass)
    caplog.set_level("INFO")

    for error in (
        exc.OperationalError("stmt", {}, Exception("refused")),
        exc.ProgrammingError("stmt", {}, Exception("permission denied for create")),
    ):
        with patch.object(instance, "_setup_connection", side_effect=error):
            await hass.async_add_executor_job(
                partial(instance._try_setup_recorder_once, log_exception=False)
            )

    info = [r for r in caplog.records if "Database still unreachable" in r.message]
    failed = [r for r in caplog.records if "not retrying" in r.message]
    assert [r.levelname for r in info] == ["INFO"]
    assert [r.levelname for r in failed] == ["ERROR"]
    assert "permission denied for create" in failed[0].message

    caplog.clear()
    with patch.object(instance, "_close_connection"):
        await hass.async_add_executor_job(
            instance._setup_recorder_extended, time.monotonic() - 1
        )
    assert "giving up" in caplog.text


async def test_sqlite_does_not_extend(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A local sqlite file that will not open fails fast, as it did before."""
    instance = _unstarted_recorder(hass)
    instance.db_url = "sqlite://no_file"
    instance.db_max_retries = 2
    instance.db_retry_wait = 0
    caplog.clear()

    with (
        patch.object(instance, "_close_connection"),
        patch.object(
            instance, "_try_setup_recorder_once", return_value=(None, True)
        ) as attempt,
    ):
        assert (
            await hass.async_add_executor_job(
                partial(instance._setup_recorder, extended_retry=True)
            )
            is False
        )

    assert attempt.call_count == 2
    assert "retrying for up to" not in caplog.text


async def test_unsupported_dialect_returns_false(
    hass: HomeAssistant,
) -> None:
    """UnsupportedDialect is a settled failure, not a retryable one."""
    instance = _unstarted_recorder(hass)

    with patch.object(instance, "_setup_connection", side_effect=UnsupportedDialect):
        result = await hass.async_add_executor_job(
            partial(instance._try_setup_recorder_once, log_exception=False)
        )

    assert result == (False, False)


async def test_unsupported_dialect_does_not_extend(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An unsupported dialect fails immediately rather than retrying."""
    instance = _unstarted_recorder(hass)
    instance.db_max_retries = 5
    instance.db_retry_wait = 0
    caplog.clear()

    with (
        patch.object(instance, "_close_connection"),
        patch.object(
            instance, "_try_setup_recorder_once", return_value=(False, False)
        ) as attempt,
    ):
        assert await hass.async_add_executor_job(instance._setup_recorder) is False

    assert attempt.call_count == 1
    assert "retrying for up to" not in caplog.text


async def test_extended_retry_aborts_when_hass_is_stopping(
    hass: HomeAssistant,
) -> None:
    """Shutdown is not held up for the remainder of the retry window."""
    instance = _unstarted_recorder(hass)
    instance.db_retry_wait = 60

    hass.set_state(CoreState.stopping)
    try:
        with (
            patch.object(instance, "_close_connection"),
            patch.object(
                instance, "_try_setup_recorder_once", return_value=(None, True)
            ) as attempt,
        ):
            result = await hass.async_add_executor_job(
                instance._setup_recorder_extended, time.monotonic() + 60
            )
    finally:
        hass.set_state(CoreState.running)

    assert result is False
    assert attempt.call_count == 0


@pytest.mark.parametrize("state", [CoreState.stopping, CoreState.final_write])
async def test_sleep_unless_stopping_reports_shutdown(
    hass: HomeAssistant,
    state: CoreState,
) -> None:
    """The sliced sleep returns False without waiting out the interval."""
    instance = _unstarted_recorder(hass)

    assert await hass.async_add_executor_job(instance._sleep_unless_stopping, 0) is True

    hass.set_state(state)
    try:
        assert (
            await hass.async_add_executor_job(instance._sleep_unless_stopping, 60)
            is False
        )
    finally:
        hass.set_state(CoreState.running)

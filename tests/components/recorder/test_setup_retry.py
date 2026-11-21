"""Test the recorder keeps retrying a database that is not ready at startup."""

import asyncio
from functools import partial
import threading
import time
from unittest.mock import patch

import pytest
from pytest_homeassistant.components.recorder.common import async_wait_recording_done
from pytest_homeassistant.typing import (
    RecorderInstanceContextManager,
    RecorderInstanceGenerator,
)
from sqlalchemy import exc

from homeassistant.components.recorder import Recorder, migration
from homeassistant.components.recorder.const import (
    DB_SETUP_RETRY_WAIT_MAX,
    MAX_DB_SETUP_RETRIES,
)
from homeassistant.components.recorder.models import UnsupportedDialect
from homeassistant.core import CoreState, HomeAssistant


@pytest.fixture
async def mock_recorder_before_hass(
    async_test_recorder: RecorderInstanceContextManager,
) -> None:
    """Set up recorder."""


async def _make_instance(
    async_setup_recorder_instance: RecorderInstanceGenerator,
    hass: HomeAssistant,
) -> Recorder:
    """Return a started recorder instance."""
    instance = await async_setup_recorder_instance(hass)
    await async_wait_recording_done(hass)
    return instance


@pytest.mark.parametrize("state", [CoreState.not_running, CoreState.running])
async def test_extends_retries_past_db_max_retries(
    hass: HomeAssistant,
    async_setup_recorder_instance: RecorderInstanceGenerator,
    caplog: pytest.LogCaptureFixture,
    state: CoreState,
) -> None:
    """A database that appears after db_max_retries is still picked up.

    not_running is the state integration setup actually runs in: async_run()
    only moves to starting once bootstrap has set every integration up.
    """
    instance = await _make_instance(async_setup_recorder_instance, hass)
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
    async_setup_recorder_instance: RecorderInstanceGenerator,
) -> None:
    """db_retry_wait has no upper bound, the extended backoff does."""
    instance = await _make_instance(async_setup_recorder_instance, hass)
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
    async_setup_recorder_instance: RecorderInstanceGenerator,
) -> None:
    """Setup is released once the retrying starts, not when it ends."""
    instance = await _make_instance(async_setup_recorder_instance, hass)
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
    async_setup_recorder_instance: RecorderInstanceGenerator,
) -> None:
    """A database that never appears still fails, as it did before."""
    instance = await _make_instance(async_setup_recorder_instance, hass)
    instance.db_url = "postgresql://u@db/ha"
    instance.db_max_retries = 1
    instance.db_retry_wait = 0

    with (
        patch.object(instance, "_close_connection"),
        patch(
            "homeassistant.components.recorder.core.MAX_DB_SETUP_WAIT",
            0.2,
        ),
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

    # One inside the fast budget, at least one more inside the extended window,
    # and never more than the extended phase's own attempt bound.
    assert 2 <= attempt.call_count <= 1 + MAX_DB_SETUP_RETRIES


async def test_corruption_recovery_does_not_extend(
    hass: HomeAssistant,
    async_setup_recorder_instance: RecorderInstanceGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The sqlite-corruption path keeps the original fast budget."""
    instance = await _make_instance(async_setup_recorder_instance, hass)
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
    async_setup_recorder_instance: RecorderInstanceGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A fast phase that used up the window neither logs nor releases setup."""
    instance = await _make_instance(async_setup_recorder_instance, hass)
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
    async_setup_recorder_instance: RecorderInstanceGenerator,
    error: Exception,
    connect_failed: bool,
) -> None:
    """URL, driver and privilege errors do not enter the extended phase."""
    instance = await _make_instance(async_setup_recorder_instance, hass)

    with patch.object(instance, "_setup_connection", side_effect=error):
        result = await hass.async_add_executor_job(
            partial(instance._try_setup_recorder_once, log_exception=False)
        )

    assert result == (None, connect_failed)


async def test_extended_retry_stops_on_a_non_connection_error(
    hass: HomeAssistant,
    async_setup_recorder_instance: RecorderInstanceGenerator,
) -> None:
    """A database that came up but fails for another reason is not waited on."""
    instance = await _make_instance(async_setup_recorder_instance, hass)

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


@pytest.mark.parametrize("released_early", [True, False])
async def test_late_database_needing_offline_migration(
    hass: HomeAssistant,
    async_setup_recorder_instance: RecorderInstanceGenerator,
    caplog: pytest.LogCaptureFixture,
    released_early: bool,
) -> None:
    """A database reached after setup was released is not migrated offline."""
    instance = await _make_instance(async_setup_recorder_instance, hass)
    instance._setup_released_early = released_early
    status = migration.SchemaValidationStatus(
        current_version=1,
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
        # The started instance already resolved these futures
        patch.object(instance, "async_connection_success"),
        patch.object(instance, "_async_startup_done"),
    ):
        await hass.async_add_executor_job(instance._run)

    assert migrate.called is (not released_early)
    assert ("needs an offline schema migration" in caplog.text) is released_early


async def test_sqlite_does_not_extend(
    hass: HomeAssistant,
    async_setup_recorder_instance: RecorderInstanceGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A local sqlite file that will not open fails fast, as it did before."""
    instance = await _make_instance(async_setup_recorder_instance, hass)
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
    async_setup_recorder_instance: RecorderInstanceGenerator,
) -> None:
    """UnsupportedDialect is a settled failure, not a retryable one."""
    instance = await _make_instance(async_setup_recorder_instance, hass)

    with patch.object(instance, "_setup_connection", side_effect=UnsupportedDialect):
        result = await hass.async_add_executor_job(
            partial(instance._try_setup_recorder_once, log_exception=False)
        )

    assert result == (False, False)


async def test_unsupported_dialect_does_not_extend(
    hass: HomeAssistant,
    async_setup_recorder_instance: RecorderInstanceGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An unsupported dialect fails immediately rather than retrying."""
    instance = await _make_instance(async_setup_recorder_instance, hass)
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
    async_setup_recorder_instance: RecorderInstanceGenerator,
) -> None:
    """Shutdown is not held up for the remainder of the retry window."""
    instance = await _make_instance(async_setup_recorder_instance, hass)
    instance.db_retry_wait = 60

    hass.set_state(CoreState.stopping)
    with (
        patch.object(instance, "_close_connection"),
        patch.object(
            instance, "_try_setup_recorder_once", return_value=(None, True)
        ) as attempt,
    ):
        result = await hass.async_add_executor_job(
            instance._setup_recorder_extended, time.monotonic() + 60
        )
    hass.set_state(CoreState.running)

    assert result is False
    assert attempt.call_count == 0


@pytest.mark.parametrize("state", [CoreState.stopping, CoreState.final_write])
async def test_sleep_unless_stopping_reports_shutdown(
    hass: HomeAssistant,
    async_setup_recorder_instance: RecorderInstanceGenerator,
    state: CoreState,
) -> None:
    """The sliced sleep returns False without waiting out the interval."""
    instance = await _make_instance(async_setup_recorder_instance, hass)

    assert await hass.async_add_executor_job(instance._sleep_unless_stopping, 0) is True

    hass.set_state(state)
    try:
        assert (
            await hass.async_add_executor_job(instance._sleep_unless_stopping, 60)
            is False
        )
    finally:
        hass.set_state(CoreState.running)

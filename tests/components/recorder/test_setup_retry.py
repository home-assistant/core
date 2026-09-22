"""Test the recorder keeps retrying a database that is not ready at startup."""

from functools import partial
import time
from unittest.mock import patch

import pytest

from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.const import MAX_DB_SETUP_RETRIES
from homeassistant.components.recorder.models import UnsupportedDialect
from homeassistant.core import CoreState, HomeAssistant

from .common import async_wait_recording_done

from tests.typing import RecorderInstanceContextManager, RecorderInstanceGenerator


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


async def test_extends_retries_past_db_max_retries(
    hass: HomeAssistant,
    async_setup_recorder_instance: RecorderInstanceGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A database that appears after db_max_retries is still picked up."""
    instance = await _make_instance(async_setup_recorder_instance, hass)
    instance.db_url = "postgresql://u@db/ha"
    instance.db_max_retries = 2
    instance.db_retry_wait = 0

    with (
        patch.object(instance, "_close_connection"),
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

    assert attempt.call_count == 3
    assert "retrying for up to" in caplog.text
    assert "Database is reachable again" in caplog.text


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


@pytest.mark.parametrize(
    "state", [CoreState.stopping, CoreState.final_write, CoreState.not_running]
)
async def test_sleep_unless_stopping_reports_shutdown(
    hass: HomeAssistant,
    async_setup_recorder_instance: RecorderInstanceGenerator,
    state: CoreState,
) -> None:
    """The sliced sleep returns False without waiting out the interval.

    not_running is included because hass.is_stopping excludes it.
    """
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

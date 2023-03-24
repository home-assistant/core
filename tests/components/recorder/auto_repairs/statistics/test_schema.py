"""The test repairing statistics schema."""

# pylint: disable=invalid-name
from datetime import datetime
from unittest.mock import ANY, DEFAULT, MagicMock, patch

import pytest
from sqlalchemy.exc import OperationalError

from homeassistant.components.recorder.auto_repairs.statistics.schema import (
    _get_future_year,
)
from homeassistant.components.recorder.statistics import (
    _statistics_during_period_with_session,
)
from homeassistant.components.recorder.table_managers.statistics_meta import (
    StatisticsMetaManager,
)
from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util

from ...common import async_wait_recording_done

from tests.typing import RecorderInstanceGenerator


@pytest.mark.parametrize("enable_statistics_table_validation", [True])
@pytest.mark.parametrize("db_engine", ("mysql", "postgresql"))
async def test_validate_db_schema(
    async_setup_recorder_instance: RecorderInstanceGenerator,
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    db_engine,
) -> None:
    """Test validating DB schema with MySQL and PostgreSQL.

    Note: The test uses SQLite, the purpose is only to exercise the code.
    """
    with patch(
        "homeassistant.components.recorder.core.Recorder.dialect_name", db_engine
    ):
        await async_setup_recorder_instance(hass)
        await async_wait_recording_done(hass)
    assert "Schema validation failed" not in caplog.text
    assert "Detected statistics schema errors" not in caplog.text
    assert "Database is about to correct DB schema errors" not in caplog.text


@pytest.mark.parametrize("enable_statistics_table_validation", [True])
async def test_validate_db_schema_fix_utf8_issue(
    async_setup_recorder_instance: RecorderInstanceGenerator,
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test validating DB schema with MySQL.

    Note: The test uses SQLite, the purpose is only to exercise the code.
    """
    orig_error = MagicMock()
    orig_error.args = [1366]
    utf8_error = OperationalError("", "", orig=orig_error)
    with patch(
        "homeassistant.components.recorder.core.Recorder.dialect_name", "mysql"
    ), patch(
        "homeassistant.components.recorder.table_managers.statistics_meta.StatisticsMetaManager.update_or_add",
        wraps=StatisticsMetaManager.update_or_add,
        side_effect=[utf8_error, DEFAULT, DEFAULT],
    ):
        await async_setup_recorder_instance(hass)
        await async_wait_recording_done(hass)

    assert "Schema validation failed" not in caplog.text
    assert (
        "Database is about to correct DB schema errors: statistics_meta.4-byte UTF-8"
        in caplog.text
    )
    assert (
        "Updating character set and collation of table statistics_meta to utf8mb4"
        in caplog.text
    )


@pytest.mark.parametrize("enable_statistics_table_validation", [True])
@pytest.mark.parametrize("db_engine", ("mysql", "postgresql"))
@pytest.mark.parametrize(
    ("table", "replace_index"), (("statistics", 0), ("statistics_short_term", 1))
)
@pytest.mark.parametrize(
    ("column", "value"),
    (("max", 1.0), ("mean", 1.0), ("min", 1.0), ("state", 1.0), ("sum", 1.0)),
)
async def test_validate_db_schema_fix_float_issue(
    async_setup_recorder_instance: RecorderInstanceGenerator,
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    db_engine,
    table,
    replace_index,
    column,
    value,
) -> None:
    """Test validating DB schema with MySQL.

    Note: The test uses SQLite, the purpose is only to exercise the code.
    """
    orig_error = MagicMock()
    orig_error.args = [1366]
    precise_number = 1.000000000000001
    fixed_future_year = _get_future_year()
    precise_time = datetime(fixed_future_year, 10, 6, microsecond=1, tzinfo=dt_util.UTC)
    statistics = {
        "recorder.db_test": [
            {
                "last_reset": precise_time.timestamp(),
                "max": precise_number,
                "mean": precise_number,
                "min": precise_number,
                "start": precise_time.timestamp(),
                "state": precise_number,
                "sum": precise_number,
            }
        ]
    }
    statistics["recorder.db_test"][0][column] = value
    fake_statistics = [DEFAULT, DEFAULT]
    fake_statistics[replace_index] = statistics

    with patch(
        "homeassistant.components.recorder.core.Recorder.dialect_name", db_engine
    ), patch(
        "homeassistant.components.recorder.auto_repairs.statistics.schema._get_future_year",
        return_value=fixed_future_year,
    ), patch(
        "homeassistant.components.recorder.auto_repairs.statistics.schema._statistics_during_period_with_session",
        side_effect=fake_statistics,
        wraps=_statistics_during_period_with_session,
    ), patch(
        "homeassistant.components.recorder.migration._modify_columns"
    ) as modify_columns_mock:
        await async_setup_recorder_instance(hass)
        await async_wait_recording_done(hass)

    assert "Schema validation failed" not in caplog.text
    assert (
        f"Database is about to correct DB schema errors: {table}.double precision"
        in caplog.text
    )
    modification = [
        "mean DOUBLE PRECISION",
        "min DOUBLE PRECISION",
        "max DOUBLE PRECISION",
        "state DOUBLE PRECISION",
        "sum DOUBLE PRECISION",
    ]
    modify_columns_mock.assert_called_once_with(ANY, ANY, table, modification)


@pytest.mark.parametrize("enable_statistics_table_validation", [True])
@pytest.mark.parametrize(
    ("db_engine", "modification"),
    (
        ("mysql", ["last_reset_ts DOUBLE PRECISION", "start_ts DOUBLE PRECISION"]),
        (
            "postgresql",
            [
                "last_reset_ts DOUBLE PRECISION",
                "start_ts DOUBLE PRECISION",
            ],
        ),
    ),
)
@pytest.mark.parametrize(
    ("table", "replace_index"), (("statistics", 0), ("statistics_short_term", 1))
)
@pytest.mark.parametrize(
    ("column", "value"),
    (
        ("last_reset", "2020-10-06T00:00:00+00:00"),
        ("start", "2020-10-06T00:00:00+00:00"),
    ),
)
async def test_validate_db_schema_fix_statistics_datetime_issue(
    async_setup_recorder_instance: RecorderInstanceGenerator,
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    db_engine,
    modification,
    table,
    replace_index,
    column,
    value,
) -> None:
    """Test validating DB schema with MySQL.

    Note: The test uses SQLite, the purpose is only to exercise the code.
    """
    orig_error = MagicMock()
    orig_error.args = [1366]
    precise_number = 1.000000000000001
    precise_time = datetime(2020, 10, 6, microsecond=1, tzinfo=dt_util.UTC)
    statistics = {
        "recorder.db_test": [
            {
                "last_reset": precise_time,
                "max": precise_number,
                "mean": precise_number,
                "min": precise_number,
                "start": precise_time,
                "state": precise_number,
                "sum": precise_number,
            }
        ]
    }
    statistics["recorder.db_test"][0][column] = value
    fake_statistics = [DEFAULT, DEFAULT]
    fake_statistics[replace_index] = statistics

    with patch(
        "homeassistant.components.recorder.core.Recorder.dialect_name", db_engine
    ), patch(
        "homeassistant.components.recorder.auto_repairs.statistics.schema._statistics_during_period_with_session",
        side_effect=fake_statistics,
        wraps=_statistics_during_period_with_session,
    ), patch(
        "homeassistant.components.recorder.migration._modify_columns"
    ) as modify_columns_mock:
        await async_setup_recorder_instance(hass)
        await async_wait_recording_done(hass)

    assert "Schema validation failed" not in caplog.text
    assert (
        f"Database is about to correct DB schema errors: {table}.µs precision"
        in caplog.text
    )
    modify_columns_mock.assert_called_once_with(ANY, ANY, table, modification)

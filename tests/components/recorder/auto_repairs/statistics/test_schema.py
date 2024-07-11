"""The test repairing statistics schema."""

from unittest.mock import ANY, patch

import pytest

from homeassistant.core import HomeAssistant

from ...common import async_wait_recording_done

from tests.typing import RecorderInstanceGenerator


@pytest.fixture
async def mock_recorder_before_hass(
    async_test_recorder: RecorderInstanceGenerator,
) -> None:
    """Set up recorder."""


@pytest.mark.parametrize("db_engine", ["mysql"])
@pytest.mark.parametrize("enable_schema_validation", [True])
async def test_validate_db_schema_fix_utf8_issue(
    hass: HomeAssistant,
    async_test_recorder: RecorderInstanceGenerator,
    caplog: pytest.LogCaptureFixture,
    db_engine: str,
    recorder_dialect_name: None,
) -> None:
    """Test validating DB schema with MySQL.

    Note: The test uses SQLite, the purpose is only to exercise the code.
    """
    with (
        patch(
            "homeassistant.components.recorder.auto_repairs.schema._validate_table_schema_supports_utf8",
            return_value={"statistics_meta.4-byte UTF-8"},
        ),
    ):
        async with async_test_recorder(hass):
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


@pytest.mark.parametrize("enable_schema_validation", [True])
@pytest.mark.parametrize("table", ["statistics_short_term", "statistics"])
@pytest.mark.parametrize("db_engine", ["mysql", "postgresql"])
async def test_validate_db_schema_fix_float_issue(
    hass: HomeAssistant,
    async_test_recorder: RecorderInstanceGenerator,
    caplog: pytest.LogCaptureFixture,
    table: str,
    db_engine: str,
    recorder_dialect_name: None,
) -> None:
    """Test validating DB schema with postgresql and mysql.

    Note: The test uses SQLite, the purpose is only to exercise the code.
    """
    with (
        patch(
            "homeassistant.components.recorder.auto_repairs.schema._validate_db_schema_precision",
            return_value={f"{table}.double precision"},
        ),
        patch(
            "homeassistant.components.recorder.migration._modify_columns"
        ) as modify_columns_mock,
    ):
        async with async_test_recorder(hass):
            await async_wait_recording_done(hass)

    assert "Schema validation failed" not in caplog.text
    assert (
        f"Database is about to correct DB schema errors: {table}.double precision"
        in caplog.text
    )
    modification = [
        "created_ts DOUBLE PRECISION",
        "start_ts DOUBLE PRECISION",
        "mean DOUBLE PRECISION",
        "min DOUBLE PRECISION",
        "max DOUBLE PRECISION",
        "last_reset_ts DOUBLE PRECISION",
        "state DOUBLE PRECISION",
        "sum DOUBLE PRECISION",
    ]
    modify_columns_mock.assert_called_once_with(ANY, ANY, table, modification)


@pytest.mark.parametrize("enable_schema_validation", [True])
@pytest.mark.parametrize("db_engine", ["mysql"])
async def test_validate_db_schema_fix_collation_issue(
    hass: HomeAssistant,
    async_test_recorder: RecorderInstanceGenerator,
    caplog: pytest.LogCaptureFixture,
    recorder_dialect_name: None,
    db_engine: str,
) -> None:
    """Test validating DB schema with MySQL.

    Note: The test uses SQLite, the purpose is only to exercise the code.
    """
    with (
        patch(
            "homeassistant.components.recorder.auto_repairs.schema._validate_table_schema_has_correct_collation",
            return_value={"statistics.utf8mb4_unicode_ci"},
        ),
    ):
        async with async_test_recorder(hass):
            await async_wait_recording_done(hass)

    assert "Schema validation failed" not in caplog.text
    assert (
        "Database is about to correct DB schema errors: statistics.utf8mb4_unicode_ci"
        in caplog.text
    )
    assert (
        "Updating character set and collation of table statistics to utf8mb4"
        in caplog.text
    )

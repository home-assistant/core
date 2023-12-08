"""The test repairing states schema."""

from unittest.mock import ANY, patch

import pytest

from homeassistant.core import HomeAssistant

from ...common import async_wait_recording_done

from tests.typing import RecorderInstanceGenerator


@pytest.mark.parametrize("enable_schema_validation", [True])
@pytest.mark.parametrize("db_engine", ("mysql", "postgresql"))
async def test_validate_db_schema_fix_float_issue(
    async_setup_recorder_instance: RecorderInstanceGenerator,
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    db_engine,
) -> None:
    """Test validating DB schema with postgresql and mysql.

    Note: The test uses SQLite, the purpose is only to exercise the code.
    """
    with patch(
        "homeassistant.components.recorder.core.Recorder.dialect_name", db_engine
    ), patch(
        "homeassistant.components.recorder.auto_repairs.schema._validate_db_schema_precision",
        return_value={"states.double precision"},
    ), patch(
        "homeassistant.components.recorder.migration._modify_columns"
    ) as modify_columns_mock:
        await async_setup_recorder_instance(hass)
        await async_wait_recording_done(hass)

    assert "Schema validation failed" not in caplog.text
    assert (
        "Database is about to correct DB schema errors: states.double precision"
        in caplog.text
    )
    modification = [
        "last_changed_ts DOUBLE PRECISION",
        "last_updated_ts DOUBLE PRECISION",
    ]
    modify_columns_mock.assert_called_once_with(ANY, ANY, "states", modification)


@pytest.mark.parametrize("enable_schema_validation", [True])
async def test_validate_db_schema_fix_utf8_issue_states(
    async_setup_recorder_instance: RecorderInstanceGenerator,
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test validating DB schema with MySQL.

    Note: The test uses SQLite, the purpose is only to exercise the code.
    """
    with patch(
        "homeassistant.components.recorder.core.Recorder.dialect_name", "mysql"
    ), patch(
        "homeassistant.components.recorder.auto_repairs.schema._validate_table_schema_supports_utf8",
        return_value={"states.4-byte UTF-8"},
    ):
        await async_setup_recorder_instance(hass)
        await async_wait_recording_done(hass)

    assert "Schema validation failed" not in caplog.text
    assert (
        "Database is about to correct DB schema errors: states.4-byte UTF-8"
        in caplog.text
    )
    assert (
        "Updating character set and collation of table states to utf8mb4" in caplog.text
    )


@pytest.mark.parametrize("enable_schema_validation", [True])
async def test_validate_db_schema_fix_utf8_issue_state_attributes(
    async_setup_recorder_instance: RecorderInstanceGenerator,
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test validating DB schema with MySQL.

    Note: The test uses SQLite, the purpose is only to exercise the code.
    """
    with patch(
        "homeassistant.components.recorder.core.Recorder.dialect_name", "mysql"
    ), patch(
        "homeassistant.components.recorder.auto_repairs.schema._validate_table_schema_supports_utf8",
        return_value={"state_attributes.4-byte UTF-8"},
    ):
        await async_setup_recorder_instance(hass)
        await async_wait_recording_done(hass)

    assert "Schema validation failed" not in caplog.text
    assert (
        "Database is about to correct DB schema errors: state_attributes.4-byte UTF-8"
        in caplog.text
    )
    assert (
        "Updating character set and collation of table state_attributes to utf8mb4"
        in caplog.text
    )


@pytest.mark.parametrize("enable_schema_validation", [True])
async def test_validate_db_schema_fix_collation_issue(
    async_setup_recorder_instance: RecorderInstanceGenerator,
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test validating DB schema with MySQL.

    Note: The test uses SQLite, the purpose is only to exercise the code.
    """
    with patch(
        "homeassistant.components.recorder.core.Recorder.dialect_name", "mysql"
    ), patch(
        "homeassistant.components.recorder.auto_repairs.schema._validate_table_schema_has_correct_collation",
        return_value={"states.utf8mb4_unicode_ci"},
    ):
        await async_setup_recorder_instance(hass)
        await async_wait_recording_done(hass)

    assert "Schema validation failed" not in caplog.text
    assert (
        "Database is about to correct DB schema errors: states.utf8mb4_unicode_ci"
        in caplog.text
    )
    assert (
        "Updating character set and collation of table states to utf8mb4" in caplog.text
    )

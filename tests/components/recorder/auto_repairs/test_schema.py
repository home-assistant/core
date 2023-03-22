"""The test repairing states schema."""

# pylint: disable=invalid-name
from unittest.mock import patch

import pytest
from sqlalchemy import text

from homeassistant.components.recorder.auto_repairs.schema import (
    validate_table_schema_supports_utf8,
)
from homeassistant.components.recorder.db_schema import States
from homeassistant.components.recorder.util import get_instance, session_scope
from homeassistant.core import HomeAssistant

from ..common import async_wait_recording_done

from tests.typing import RecorderInstanceGenerator


async def test_validate_db_schema_fix_utf8_issue_no_errors(
    async_setup_recorder_instance: RecorderInstanceGenerator,
    hass: HomeAssistant,
    recorder_db_url: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test validating DB schema with MySQL."""
    if not recorder_db_url.startswith("mysql://"):
        # This problem only happens on MySQL
        return
    await async_setup_recorder_instance(hass)
    await async_wait_recording_done(hass)
    instance = get_instance(hass)
    session_maker = instance.get_session
    schema_errors = await instance.async_add_executor_job(
        validate_table_schema_supports_utf8, instance, States, ("state",), session_maker
    )
    assert schema_errors == set()


async def test_validate_db_schema_fix_utf8_issue_with_broken_schema(
    async_setup_recorder_instance: RecorderInstanceGenerator,
    hass: HomeAssistant,
    recorder_db_url: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test validating DB schema with MySQL."""
    if not recorder_db_url.startswith("mysql://"):
        # This problem only happens on MySQL
        return
    await async_setup_recorder_instance(hass)
    await async_wait_recording_done(hass)
    instance = get_instance(hass)
    session_maker = instance.get_session

    def _break_states_schema():
        with session_scope(session=session_maker()) as session:
            session.execute(
                text(
                    "ALTER TABLE states MODIFY state VARCHAR(255) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL;"
                )
            )

    await instance.async_add_executor_job(_break_states_schema)
    schema_errors = await instance.async_add_executor_job(
        validate_table_schema_supports_utf8, instance, States, ("state",), session_maker
    )
    assert schema_errors == {"states.4-byte UTF-8"}


@pytest.mark.parametrize("enable_schema_validation", [True])
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

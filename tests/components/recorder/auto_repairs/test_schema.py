"""The test validating and repairing schema."""

# pylint: disable=invalid-name
from unittest.mock import patch

import pytest
from sqlalchemy import text

from homeassistant.components.recorder.auto_repairs.schema import (
    correct_db_schema_precision,
    correct_db_schema_utf8,
    validate_db_schema_precision,
    validate_table_schema_has_correct_collation,
    validate_table_schema_supports_utf8,
)
from homeassistant.components.recorder.db_schema import States
from homeassistant.components.recorder.migration import _modify_columns
from homeassistant.components.recorder.util import get_instance, session_scope
from homeassistant.core import HomeAssistant

from ..common import async_wait_recording_done

from tests.typing import RecorderInstanceGenerator


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


async def test_validate_db_schema_fix_utf8_issue_good_schema(
    async_setup_recorder_instance: RecorderInstanceGenerator,
    hass: HomeAssistant,
    recorder_db_url: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test validating DB schema with MySQL when the schema is correct."""
    if not recorder_db_url.startswith("mysql://"):
        # This problem only happens on MySQL
        return
    await async_setup_recorder_instance(hass)
    await async_wait_recording_done(hass)
    instance = get_instance(hass)
    schema_errors = await instance.async_add_executor_job(
        validate_table_schema_supports_utf8, instance, States, (States.state,)
    )
    assert schema_errors == set()


async def test_validate_db_schema_fix_utf8_issue_with_broken_schema(
    async_setup_recorder_instance: RecorderInstanceGenerator,
    hass: HomeAssistant,
    recorder_db_url: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test validating DB schema with MySQL when the schema is broken and repairing it."""
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
                    "ALTER TABLE states MODIFY state VARCHAR(255) "
                    "CHARACTER SET ascii COLLATE ascii_general_ci, "
                    "LOCK=EXCLUSIVE;"
                )
            )

    await instance.async_add_executor_job(_break_states_schema)
    schema_errors = await instance.async_add_executor_job(
        validate_table_schema_supports_utf8, instance, States, (States.state,)
    )
    assert schema_errors == {"states.4-byte UTF-8"}

    # Now repair the schema
    await instance.async_add_executor_job(
        correct_db_schema_utf8, instance, States, schema_errors
    )

    # Now validate the schema again
    schema_errors = await instance.async_add_executor_job(
        validate_table_schema_supports_utf8, instance, States, ("state",)
    )
    assert schema_errors == set()


async def test_validate_db_schema_fix_incorrect_collation(
    async_setup_recorder_instance: RecorderInstanceGenerator,
    hass: HomeAssistant,
    recorder_db_url: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test validating DB schema with MySQL when the collation is incorrect."""
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
                    "ALTER TABLE states CHARACTER SET utf8mb3 COLLATE utf8_general_ci, "
                    "LOCK=EXCLUSIVE;"
                )
            )

    await instance.async_add_executor_job(_break_states_schema)
    schema_errors = await instance.async_add_executor_job(
        validate_table_schema_has_correct_collation, instance, States
    )
    assert schema_errors == {"states.utf8mb4_unicode_ci"}

    # Now repair the schema
    await instance.async_add_executor_job(
        correct_db_schema_utf8, instance, States, schema_errors
    )

    # Now validate the schema again
    schema_errors = await instance.async_add_executor_job(
        validate_table_schema_has_correct_collation, instance, States
    )
    assert schema_errors == set()


async def test_validate_db_schema_precision_correct_collation(
    async_setup_recorder_instance: RecorderInstanceGenerator,
    hass: HomeAssistant,
    recorder_db_url: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test validating DB schema when the schema is correct with the correct collation."""
    if not recorder_db_url.startswith("mysql://"):
        # This problem only happens on MySQL
        return
    await async_setup_recorder_instance(hass)
    await async_wait_recording_done(hass)
    instance = get_instance(hass)
    schema_errors = await instance.async_add_executor_job(
        validate_table_schema_has_correct_collation,
        instance,
        States,
    )
    assert schema_errors == set()


async def test_validate_db_schema_fix_utf8_issue_with_broken_schema_unrepairable(
    async_setup_recorder_instance: RecorderInstanceGenerator,
    hass: HomeAssistant,
    recorder_db_url: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test validating DB schema with MySQL when the schema is broken and cannot be repaired."""
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
                    "ALTER TABLE states MODIFY state VARCHAR(255) "
                    "CHARACTER SET ascii COLLATE ascii_general_ci, "
                    "LOCK=EXCLUSIVE;"
                )
            )
            _modify_columns(
                session_maker,
                instance.engine,
                "states",
                [
                    "entity_id VARCHAR(255) NOT NULL",
                ],
            )

    await instance.async_add_executor_job(_break_states_schema)
    schema_errors = await instance.async_add_executor_job(
        validate_table_schema_supports_utf8, instance, States, ("state",)
    )
    assert schema_errors == set()
    assert "Error when validating DB schema" in caplog.text


async def test_validate_db_schema_precision_good_schema(
    async_setup_recorder_instance: RecorderInstanceGenerator,
    hass: HomeAssistant,
    recorder_db_url: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test validating DB schema when the schema is correct."""
    if not recorder_db_url.startswith(("mysql://", "postgresql://")):
        # This problem only happens on MySQL and PostgreSQL
        return
    await async_setup_recorder_instance(hass)
    await async_wait_recording_done(hass)
    instance = get_instance(hass)
    schema_errors = await instance.async_add_executor_job(
        validate_db_schema_precision,
        instance,
        States,
    )
    assert schema_errors == set()


async def test_validate_db_schema_precision_with_broken_schema(
    async_setup_recorder_instance: RecorderInstanceGenerator,
    hass: HomeAssistant,
    recorder_db_url: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test validating DB schema when the schema is broken and than repair it."""
    if not recorder_db_url.startswith(("mysql://", "postgresql://")):
        # This problem only happens on MySQL and PostgreSQL
        return
    await async_setup_recorder_instance(hass)
    await async_wait_recording_done(hass)
    instance = get_instance(hass)
    session_maker = instance.get_session

    def _break_states_schema():
        _modify_columns(
            session_maker,
            instance.engine,
            "states",
            [
                "last_updated_ts FLOAT(4)",
                "last_changed_ts FLOAT(4)",
            ],
        )

    await instance.async_add_executor_job(_break_states_schema)
    schema_errors = await instance.async_add_executor_job(
        validate_db_schema_precision,
        instance,
        States,
    )
    assert schema_errors == {"states.double precision"}

    # Now repair the schema
    await instance.async_add_executor_job(
        correct_db_schema_precision, instance, States, schema_errors
    )

    # Now validate the schema again
    schema_errors = await instance.async_add_executor_job(
        validate_db_schema_precision,
        instance,
        States,
    )
    assert schema_errors == set()


async def test_validate_db_schema_precision_with_unrepairable_broken_schema(
    async_setup_recorder_instance: RecorderInstanceGenerator,
    hass: HomeAssistant,
    recorder_db_url: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test validating DB schema when the schema is broken and cannot be repaired."""
    if not recorder_db_url.startswith("mysql://"):
        # This problem only happens on MySQL
        return
    await async_setup_recorder_instance(hass)
    await async_wait_recording_done(hass)
    instance = get_instance(hass)
    session_maker = instance.get_session

    def _break_states_schema():
        _modify_columns(
            session_maker,
            instance.engine,
            "states",
            [
                "state VARCHAR(255) NOT NULL",
                "last_updated_ts FLOAT(4)",
                "last_changed_ts FLOAT(4)",
            ],
        )

    await instance.async_add_executor_job(_break_states_schema)
    schema_errors = await instance.async_add_executor_job(
        validate_db_schema_precision,
        instance,
        States,
    )
    assert "Error when validating DB schema" in caplog.text
    assert schema_errors == set()

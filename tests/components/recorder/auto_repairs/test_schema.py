"""The test validating and repairing schema."""

import pytest
from sqlalchemy import text

from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.auto_repairs.schema import (
    correct_db_schema_precision,
    correct_db_schema_utf8,
    validate_db_schema_precision,
    validate_table_schema_has_correct_collation,
    validate_table_schema_supports_utf8,
)
from homeassistant.components.recorder.db_schema import States
from homeassistant.components.recorder.migration import _modify_columns
from homeassistant.components.recorder.util import session_scope
from homeassistant.core import HomeAssistant

from ..common import async_wait_recording_done

from tests.typing import RecorderInstanceContextManager


@pytest.fixture
async def mock_recorder_before_hass(
    async_test_recorder: RecorderInstanceContextManager,
) -> None:
    """Set up recorder."""


@pytest.mark.parametrize("enable_schema_validation", [True])
@pytest.mark.parametrize("db_engine", ["mysql", "postgresql"])
async def test_validate_db_schema(
    hass: HomeAssistant,
    recorder_mock: Recorder,
    caplog: pytest.LogCaptureFixture,
    db_engine: str,
    recorder_dialect_name: None,
) -> None:
    """Test validating DB schema with MySQL and PostgreSQL.

    Note: The test uses SQLite, the purpose is only to exercise the code.
    """
    await async_wait_recording_done(hass)
    assert "Schema validation failed" not in caplog.text
    assert "Detected statistics schema errors" not in caplog.text
    assert "Database is about to correct DB schema errors" not in caplog.text


@pytest.mark.skip_on_db_engine(["postgresql", "sqlite"])
@pytest.mark.usefixtures("skip_by_db_engine")
async def test_validate_db_schema_fix_utf8_issue_good_schema(
    hass: HomeAssistant,
    recorder_mock: Recorder,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test validating DB schema with MySQL when the schema is correct."""
    await async_wait_recording_done(hass)
    schema_errors = await recorder_mock.async_add_executor_job(
        validate_table_schema_supports_utf8, recorder_mock, States, (States.state,)
    )
    assert schema_errors == set()


@pytest.mark.skip_on_db_engine(["postgresql", "sqlite"])
@pytest.mark.usefixtures("skip_by_db_engine")
async def test_validate_db_schema_fix_utf8_issue_with_broken_schema(
    hass: HomeAssistant,
    recorder_mock: Recorder,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test validating DB schema with MySQL when the schema is broken and repairing it."""
    await async_wait_recording_done(hass)
    session_maker = recorder_mock.get_session

    def _break_states_schema():
        with session_scope(session=session_maker()) as session:
            session.execute(
                text(
                    "ALTER TABLE states MODIFY state VARCHAR(255) "
                    "CHARACTER SET ascii COLLATE ascii_general_ci, "
                    "LOCK=EXCLUSIVE;"
                )
            )

    await recorder_mock.async_add_executor_job(_break_states_schema)
    schema_errors = await recorder_mock.async_add_executor_job(
        validate_table_schema_supports_utf8, recorder_mock, States, (States.state,)
    )
    assert schema_errors == {"states.4-byte UTF-8"}

    # Now repair the schema
    await recorder_mock.async_add_executor_job(
        correct_db_schema_utf8, recorder_mock, States, schema_errors
    )

    # Now validate the schema again
    schema_errors = await recorder_mock.async_add_executor_job(
        validate_table_schema_supports_utf8, recorder_mock, States, ("state",)
    )
    assert schema_errors == set()


@pytest.mark.skip_on_db_engine(["postgresql", "sqlite"])
@pytest.mark.usefixtures("skip_by_db_engine")
async def test_validate_db_schema_fix_incorrect_collation(
    hass: HomeAssistant,
    recorder_mock: Recorder,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test validating DB schema with MySQL when the collation is incorrect."""
    await async_wait_recording_done(hass)
    session_maker = recorder_mock.get_session

    def _break_states_schema():
        with session_scope(session=session_maker()) as session:
            session.execute(
                text(
                    "ALTER TABLE states CHARACTER SET utf8mb3 COLLATE utf8_general_ci, "
                    "LOCK=EXCLUSIVE;"
                )
            )

    await recorder_mock.async_add_executor_job(_break_states_schema)
    schema_errors = await recorder_mock.async_add_executor_job(
        validate_table_schema_has_correct_collation, recorder_mock, States
    )
    assert schema_errors == {"states.utf8mb4_unicode_ci"}

    # Now repair the schema
    await recorder_mock.async_add_executor_job(
        correct_db_schema_utf8, recorder_mock, States, schema_errors
    )

    # Now validate the schema again
    schema_errors = await recorder_mock.async_add_executor_job(
        validate_table_schema_has_correct_collation, recorder_mock, States
    )
    assert schema_errors == set()


@pytest.mark.skip_on_db_engine(["postgresql", "sqlite"])
@pytest.mark.usefixtures("skip_by_db_engine")
async def test_validate_db_schema_precision_correct_collation(
    hass: HomeAssistant,
    recorder_mock: Recorder,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test validating DB schema when the schema is correct with the correct collation."""
    await async_wait_recording_done(hass)
    schema_errors = await recorder_mock.async_add_executor_job(
        validate_table_schema_has_correct_collation,
        recorder_mock,
        States,
    )
    assert schema_errors == set()


@pytest.mark.skip_on_db_engine(["postgresql", "sqlite"])
@pytest.mark.usefixtures("skip_by_db_engine")
async def test_validate_db_schema_fix_utf8_issue_with_broken_schema_unrepairable(
    hass: HomeAssistant,
    recorder_mock: Recorder,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test validating DB schema with MySQL when the schema is broken and cannot be repaired."""
    await async_wait_recording_done(hass)
    session_maker = recorder_mock.get_session

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
            recorder_mock.engine,
            "states",
            [
                "entity_id VARCHAR(255) NOT NULL",
            ],
        )

    await recorder_mock.async_add_executor_job(_break_states_schema)
    schema_errors = await recorder_mock.async_add_executor_job(
        validate_table_schema_supports_utf8, recorder_mock, States, ("state",)
    )
    assert schema_errors == set()
    assert "Error when validating DB schema" in caplog.text


@pytest.mark.skip_on_db_engine(["sqlite"])
@pytest.mark.usefixtures("skip_by_db_engine")
async def test_validate_db_schema_precision_good_schema(
    hass: HomeAssistant,
    recorder_mock: Recorder,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test validating DB schema when the schema is correct."""
    await async_wait_recording_done(hass)
    schema_errors = await recorder_mock.async_add_executor_job(
        validate_db_schema_precision,
        recorder_mock,
        States,
    )
    assert schema_errors == set()


@pytest.mark.skip_on_db_engine(["sqlite"])
@pytest.mark.usefixtures("skip_by_db_engine")
async def test_validate_db_schema_precision_with_broken_schema(
    hass: HomeAssistant,
    recorder_mock: Recorder,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test validating DB schema when the schema is broken and than repair it."""
    await async_wait_recording_done(hass)
    session_maker = recorder_mock.get_session

    def _break_states_schema():
        _modify_columns(
            session_maker,
            recorder_mock.engine,
            "states",
            [
                "last_updated_ts FLOAT(4)",
                "last_changed_ts FLOAT(4)",
            ],
        )

    await recorder_mock.async_add_executor_job(_break_states_schema)
    schema_errors = await recorder_mock.async_add_executor_job(
        validate_db_schema_precision,
        recorder_mock,
        States,
    )
    assert schema_errors == {"states.double precision"}

    # Now repair the schema
    await recorder_mock.async_add_executor_job(
        correct_db_schema_precision, recorder_mock, States, schema_errors
    )

    # Now validate the schema again
    schema_errors = await recorder_mock.async_add_executor_job(
        validate_db_schema_precision,
        recorder_mock,
        States,
    )
    assert schema_errors == set()


@pytest.mark.skip_on_db_engine(["postgresql", "sqlite"])
@pytest.mark.usefixtures("skip_by_db_engine")
async def test_validate_db_schema_precision_with_unrepairable_broken_schema(
    hass: HomeAssistant,
    recorder_mock: Recorder,
    recorder_db_url: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test validating DB schema when the schema is broken and cannot be repaired."""
    await async_wait_recording_done(hass)
    session_maker = recorder_mock.get_session

    def _break_states_schema():
        _modify_columns(
            session_maker,
            recorder_mock.engine,
            "states",
            [
                "state VARCHAR(255) NOT NULL",
                "last_updated_ts FLOAT(4)",
                "last_changed_ts FLOAT(4)",
            ],
        )

    await recorder_mock.async_add_executor_job(_break_states_schema)
    schema_errors = await recorder_mock.async_add_executor_job(
        validate_db_schema_precision,
        recorder_mock,
        States,
    )
    assert "Error when validating DB schema" in caplog.text
    assert schema_errors == set()

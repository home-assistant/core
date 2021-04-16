"""The tests for the Recorder component."""
# pylint: disable=protected-access
from unittest.mock import Mock, PropertyMock, call, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import InternalError, OperationalError, ProgrammingError
from sqlalchemy.pool import StaticPool

from homeassistant.bootstrap import async_setup_component
from homeassistant.components.recorder import RecorderRuns, const, migration, models
import homeassistant.util.dt as dt_util

from tests.components.recorder import models_original


def create_engine_test(*args, **kwargs):
    """Test version of create_engine that initializes with old schema.

    This simulates an existing db with the old schema.
    """
    engine = create_engine(*args, **kwargs)
    models_original.Base.metadata.create_all(engine)
    return engine


async def test_schema_update_calls(hass):
    """Test that schema migrations occur in correct order."""
    with patch(
        "homeassistant.components.recorder.create_engine", new=create_engine_test
    ), patch(
        "homeassistant.components.recorder.migration._apply_update",
        wraps=migration._apply_update,
    ) as update:
        await async_setup_component(
            hass, "recorder", {"recorder": {"db_url": "sqlite://"}}
        )
        await hass.async_block_till_done()

    update.assert_has_calls(
        [
            call(hass.data[const.DATA_INSTANCE].engine, version + 1, 0)
            for version in range(0, models.SCHEMA_VERSION)
        ]
    )


async def test_schema_migrate(hass):
    """Test the full schema migration logic.

    We're just testing that the logic can execute successfully here without
    throwing exceptions. Maintaining a set of assertions based on schema
    inspection could quickly become quite cumbersome.
    """

    def _mock_setup_run(self):
        self.run_info = RecorderRuns(
            start=self.recording_start, created=dt_util.utcnow()
        )

    with patch("sqlalchemy.create_engine", new=create_engine_test), patch(
        "homeassistant.components.recorder.Recorder._setup_run",
        side_effect=_mock_setup_run,
        autospec=True,
    ) as setup_run:
        await async_setup_component(
            hass, "recorder", {"recorder": {"db_url": "sqlite://"}}
        )
        await hass.async_block_till_done()
        assert setup_run.called


def test_invalid_update():
    """Test that an invalid new version raises an exception."""
    with pytest.raises(ValueError):
        migration._apply_update(None, -1, 0)


def test_forgiving_add_column():
    """Test that add column will continue if column exists."""
    engine = create_engine("sqlite://", poolclass=StaticPool)
    engine.execute("CREATE TABLE hello (id int)")
    migration._add_columns(engine, "hello", ["context_id CHARACTER(36)"])
    migration._add_columns(engine, "hello", ["context_id CHARACTER(36)"])


def test_forgiving_add_index():
    """Test that add index will continue if index exists."""
    engine = create_engine("sqlite://", poolclass=StaticPool)
    models.Base.metadata.create_all(engine)
    migration._create_index(engine, "states", "ix_states_context_id")


@pytest.mark.parametrize(
    "exception_type", [OperationalError, ProgrammingError, InternalError]
)
def test_forgiving_add_index_with_other_db_types(caplog, exception_type):
    """Test that add index will continue if index exists on mysql and postgres."""
    mocked_index = Mock()
    type(mocked_index).name = "ix_states_context_id"
    mocked_index.create = Mock(
        side_effect=exception_type(
            "CREATE INDEX ix_states_old_state_id ON states (old_state_id);",
            [],
            'relation "ix_states_old_state_id" already exists',
        )
    )

    mocked_table = Mock()
    type(mocked_table).indexes = PropertyMock(return_value=[mocked_index])

    with patch(
        "homeassistant.components.recorder.migration.Table", return_value=mocked_table
    ):
        migration._create_index(Mock(), "states", "ix_states_context_id")

    assert "already exists on states" in caplog.text
    assert "continuing" in caplog.text

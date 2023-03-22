"""The test repairing states schema."""

# pylint: disable=invalid-name
from unittest.mock import patch

import pytest

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

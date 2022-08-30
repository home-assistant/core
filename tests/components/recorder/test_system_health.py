"""Test recorder system health."""

from unittest.mock import ANY, Mock, patch

import pytest

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.const import SupportedDialect
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .common import async_wait_recording_done

from tests.common import SetupRecorderInstanceT, get_system_health_info


async def test_recorder_system_health(hass, recorder_mock):
    """Test recorder system health."""
    assert await async_setup_component(hass, "system_health", {})
    await async_wait_recording_done(hass)
    info = await get_system_health_info(hass, "recorder")
    instance = get_instance(hass)
    assert info == {
        "current_recorder_run": instance.run_history.current.start,
        "oldest_recorder_run": instance.run_history.first.start,
        "estimated_db_size": ANY,
        "database_engine": SupportedDialect.SQLITE.value,
        "database_version": ANY,
    }


@pytest.mark.parametrize(
    "dialect_name", [SupportedDialect.MYSQL, SupportedDialect.POSTGRESQL]
)
async def test_recorder_system_health_alternate_dbms(hass, recorder_mock, dialect_name):
    """Test recorder system health."""
    assert await async_setup_component(hass, "system_health", {})
    await async_wait_recording_done(hass)
    with patch(
        "homeassistant.components.recorder.core.Recorder.dialect_name", dialect_name
    ), patch(
        "sqlalchemy.orm.session.Session.execute",
        return_value=Mock(first=Mock(return_value=("1048576",))),
    ):
        info = await get_system_health_info(hass, "recorder")
    instance = get_instance(hass)
    assert info == {
        "current_recorder_run": instance.run_history.current.start,
        "oldest_recorder_run": instance.run_history.first.start,
        "estimated_db_size": "1.00 MiB",
        "database_engine": dialect_name.value,
        "database_version": ANY,
    }


@pytest.mark.parametrize(
    "dialect_name", [SupportedDialect.MYSQL, SupportedDialect.POSTGRESQL]
)
async def test_recorder_system_health_db_url_missing_host(
    hass, recorder_mock, dialect_name
):
    """Test recorder system health with a db_url without a hostname."""
    assert await async_setup_component(hass, "system_health", {})
    await async_wait_recording_done(hass)

    instance = get_instance(hass)
    with patch(
        "homeassistant.components.recorder.core.Recorder.dialect_name", dialect_name
    ), patch.object(
        instance,
        "db_url",
        "postgresql://homeassistant:blabla@/home_assistant?host=/config/socket",
    ), patch(
        "sqlalchemy.orm.session.Session.execute",
        return_value=Mock(first=Mock(return_value=("1048576",))),
    ):
        info = await get_system_health_info(hass, "recorder")
    assert info == {
        "current_recorder_run": instance.run_history.current.start,
        "oldest_recorder_run": instance.run_history.first.start,
        "estimated_db_size": "1.00 MiB",
        "database_engine": dialect_name.value,
        "database_version": ANY,
    }


async def test_recorder_system_health_crashed_recorder_runs_table(
    hass: HomeAssistant, async_setup_recorder_instance: SetupRecorderInstanceT
):
    """Test recorder system health with crashed recorder runs table."""
    with patch("homeassistant.components.recorder.run_history.RunHistory.load_from_db"):
        assert await async_setup_component(hass, "system_health", {})
        instance = await async_setup_recorder_instance(hass)
        await async_wait_recording_done(hass)
    info = await get_system_health_info(hass, "recorder")
    assert info == {
        "current_recorder_run": instance.run_history.current.start,
        "oldest_recorder_run": instance.run_history.current.start,
        "estimated_db_size": ANY,
        "database_engine": SupportedDialect.SQLITE.value,
        "database_version": ANY,
    }

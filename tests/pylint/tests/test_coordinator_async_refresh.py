"""Tests for the coordinator async_refresh checker."""

import astroid
from pylint.testutils import UnittestLinter
from pylint_home_assistant.checkers.tests.coordinator_async_refresh import (
    CoordinatorAsyncRefresh,
)
import pytest

from tests.pylint import assert_no_messages, walk_checker

# Pre-load so astroid can resolve ``DataUpdateCoordinator`` in parsed snippets.
astroid.MANAGER.ast_from_module_name("homeassistant.helpers.update_coordinator")


@pytest.fixture(name="checker")
def checker_fixture(linter: UnittestLinter) -> CoordinatorAsyncRefresh:
    """Fixture to provide a coordinator async_refresh checker."""
    return CoordinatorAsyncRefresh(linter)


@pytest.mark.parametrize(
    ("code", "module_name"),
    [
        pytest.param(
            """
async def test_refresh(hass, freezer):
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
""",
            "tests.components.sun.test_sensor",
            id="freezer",
        ),
        pytest.param(
            """
async def test_refresh(coordinator):
    await coordinator.async_refresh()
""",
            "tests.helpers.test_update_coordinator",
            id="not_an_integration_test",
        ),
        pytest.param(
            """
async def test_refresh(mock_coordinator):
    mock_coordinator.async_refresh.assert_called_once()
""",
            "tests.components.sun.test_sensor",
            id="mock_assertion",
        ),
        pytest.param(
            """
def test_refresh(info, now):
    info.async_refresh(now)
""",
            "tests.components.sun.test_sensor",
            id="with_arguments",
        ),
        pytest.param(
            """
def test_refresh(info, now):
    info.async_refresh(now=now)
""",
            "tests.components.sun.test_sensor",
            id="with_keyword_arguments",
        ),
        pytest.param(
            """
class MockRefresh:
    async def async_refresh(self):
        pass

async def test_refresh(hass):
    await MockRefresh().async_refresh()
""",
            "tests.components.sun.test_sensor",
            id="not_a_coordinator",
        ),
        pytest.param(
            """
from unittest.mock import MagicMock

async def test_refresh(hass):
    coordinator = MagicMock()
    await coordinator.async_refresh()
""",
            "tests.components.sun.test_sensor",
            id="mock",
        ),
    ],
)
def test_no_warning(
    linter: UnittestLinter,
    checker: CoordinatorAsyncRefresh,
    code: str,
    module_name: str,
) -> None:
    """Test cases that should not trigger a warning."""
    root_node = astroid.parse(code, module_name)

    with assert_no_messages(linter):
        walk_checker(linter, checker, root_node)


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
async def test_refresh(hass, mock_config_entry):
    await mock_config_entry.runtime_data.async_refresh()
""",
            id="runtime_data",
        ),
        pytest.param(
            """
async def test_refresh(hass, coordinator):
    await coordinator.async_refresh()
""",
            id="fixture",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

async def test_refresh(hass):
    coordinator = DataUpdateCoordinator(hass, None, name="test")
    await coordinator.async_refresh()
""",
            id="coordinator",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

class MyCoordinator(DataUpdateCoordinator):
    pass

async def test_refresh(hass):
    await MyCoordinator(hass, None, name="test").async_refresh()
""",
            id="coordinator_subclass",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

def get_coordinator(hass) -> DataUpdateCoordinator | None:
    if hass.data:
        return DataUpdateCoordinator(hass, None, name="test")
    return None

async def test_refresh(hass):
    await get_coordinator(hass).async_refresh()
""",
            id="optional_getter",
        ),
        pytest.param(
            """
async def test_refresh(hass, coordinator):
    refresh = hass.async_create_task(coordinator.async_refresh())
    await refresh
""",
            id="not_awaited",
        ),
        pytest.param(
            """
async def test_refresh(coordinator):
    await coordinator.async_request_refresh()
""",
            id="request_refresh",
        ),
        pytest.param(
            """
async def test_refresh(coordinator):
    await coordinator._async_refresh(log_failures=False)
""",
            id="private_refresh",
        ),
        pytest.param(
            """
async def test_refresh(coordinator):
    await coordinator._async_refresh(False)
""",
            id="private_refresh_positional",
        ),
        pytest.param(
            """
async def test_refresh(hass, coordinator):
    hass.async_add_job(coordinator.async_refresh)
""",
            id="method_reference",
        ),
        pytest.param(
            """
from unittest.mock import MagicMock

async def test_refresh(hass, mock_config_entry, use_mock):
    coordinator = MagicMock() if use_mock else mock_config_entry.runtime_data
    await coordinator.async_refresh()
""",
            id="partly_inferred",
        ),
    ],
)
def test_warning(
    linter: UnittestLinter,
    checker: CoordinatorAsyncRefresh,
    code: str,
) -> None:
    """Test cases that should trigger a warning."""
    root_node = astroid.parse(code, "tests.components.sun.test_sensor")
    walk_checker(linter, checker, root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "home-assistant-tests-coordinator-async-refresh"

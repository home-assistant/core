"""Tests for the direct async_setup_entry checker."""

import astroid
from pylint.testutils import UnittestLinter
from pylint.utils.ast_walker import ASTWalker
from pylint_home_assistant.checkers.tests.direct_async_setup_entry import (
    DirectAsyncSetupEntry,
)
import pytest

from tests.pylint import assert_no_messages

# Pre-load so astroid can resolve ``async_setup_entry`` in parsed snippets.
astroid.MANAGER.ast_from_module_name("homeassistant.components.sun")
astroid.MANAGER.ast_from_module_name("homeassistant.components.sun.sensor")


@pytest.fixture(name="checker")
def checker_fixture(linter: UnittestLinter) -> DirectAsyncSetupEntry:
    """Fixture to provide a direct async_setup_entry checker."""
    return DirectAsyncSetupEntry(linter)


@pytest.mark.parametrize(
    ("code", "module_name"),
    [
        pytest.param(
            """
async def test_setup(hass):
    await hass.config_entries.async_setup(entry.entry_id)
""",
            "tests.components.sun.test_init",
            id="proper_setup_call",
        ),
        pytest.param(
            """
from homeassistant.components.sun import async_setup_entry

async def test_setup(hass, mock_config_entry):
    await async_setup_entry(hass, mock_config_entry)
""",
            "homeassistant.components.sun",
            id="not_a_test_module",
        ),
        pytest.param(
            """
async def test_setup(hass, mock_config_entry):
    await some_local.async_setup_entry(hass, mock_config_entry)
""",
            "tests.components.sun.test_init",
            id="unresolved_attribute_call",
        ),
        pytest.param(
            """
async def async_setup_entry(hass, entry):
    return True

async def test_setup(hass, entry):
    await async_setup_entry(hass, entry)
""",
            "tests.components.sun.test_init",
            id="local_async_setup_entry_not_an_integration",
        ),
    ],
)
def test_no_warning(
    linter: UnittestLinter,
    checker: DirectAsyncSetupEntry,
    code: str,
    module_name: str,
) -> None:
    """Test cases that should not trigger a warning."""
    root_node = astroid.parse(code, module_name)
    walker = ASTWalker(linter)
    walker.add_checker(checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


@pytest.mark.parametrize(
    ("code", "module_name", "expected_msg"),
    [
        pytest.param(
            """
from homeassistant.components.sun import async_setup_entry

async def test_setup(hass, mock_config_entry):
    await async_setup_entry(hass, mock_config_entry)
""",
            "tests.components.sun.test_init",
            "home-assistant-tests-direct-async-setup-entry",
            id="direct_name_call_from_init",
        ),
        pytest.param(
            """
from homeassistant.components import sun

async def test_setup(hass, mock_config_entry):
    await sun.async_setup_entry(hass, mock_config_entry)
""",
            "tests.components.sun.test_init",
            "home-assistant-tests-direct-async-setup-entry",
            id="attribute_call_from_init",
        ),
        pytest.param(
            """
from homeassistant.components.sun.sensor import async_setup_entry

async def test_setup(hass, mock_config_entry, add_entities):
    await async_setup_entry(hass, mock_config_entry, add_entities)
""",
            "tests.components.sun.test_sensor",
            "home-assistant-tests-direct-platform-async-setup-entry",
            id="direct_call_from_platform",
        ),
        pytest.param(
            """
from homeassistant.components.sun import sensor

async def test_setup(hass, mock_config_entry, add_entities):
    await sensor.async_setup_entry(hass, mock_config_entry, add_entities)
""",
            "tests.components.sun.test_sensor",
            "home-assistant-tests-direct-platform-async-setup-entry",
            id="attribute_call_from_platform",
        ),
    ],
)
def test_warning(
    linter: UnittestLinter,
    checker: DirectAsyncSetupEntry,
    code: str,
    module_name: str,
    expected_msg: str,
) -> None:
    """Test cases that should trigger a warning."""
    root_node = astroid.parse(code, module_name)
    walker = ASTWalker(linter)
    walker.add_checker(checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == expected_msg


def test_multiple_calls_each_flagged(
    linter: UnittestLinter,
    checker: DirectAsyncSetupEntry,
) -> None:
    """Test that multiple direct calls are each flagged."""
    root_node = astroid.parse(
        """
from homeassistant.components.sun import async_setup_entry

async def test_a(hass, mock_config_entry):
    await async_setup_entry(hass, mock_config_entry)

async def test_b(hass, mock_config_entry):
    await async_setup_entry(hass, mock_config_entry)
""",
        "tests.components.sun.test_init",
    )
    walker = ASTWalker(linter)
    walker.add_checker(checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 2

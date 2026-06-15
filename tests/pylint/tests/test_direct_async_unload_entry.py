"""Tests for the direct async_unload_entry checker."""

import astroid
from pylint.testutils import UnittestLinter
from pylint.utils.ast_walker import ASTWalker
from pylint_home_assistant.checkers.tests.direct_async_unload_entry import (
    DirectAsyncUnloadEntry,
)
import pytest

from tests.pylint import assert_no_messages

# Pre-load so astroid can resolve ``async_unload_entry`` in parsed snippets.
astroid.MANAGER.ast_from_module_name("homeassistant.components.ps4")


@pytest.fixture(name="checker")
def checker_fixture(linter: UnittestLinter) -> DirectAsyncUnloadEntry:
    """Fixture to provide a direct async_unload_entry checker."""
    return DirectAsyncUnloadEntry(linter)


@pytest.mark.parametrize(
    ("code", "module_name"),
    [
        pytest.param(
            """
async def test_unload(hass):
    await hass.config_entries.async_unload(entry.entry_id)
""",
            "tests.components.ps4.test_init",
            id="proper_unload_call",
        ),
        pytest.param(
            """
from homeassistant.components.ps4 import async_unload_entry

async def test_unload(hass, mock_config_entry):
    await async_unload_entry(hass, mock_config_entry)
""",
            "homeassistant.components.ps4",
            id="not_a_test_module",
        ),
        pytest.param(
            """
async def test_unload(hass, mock_config_entry):
    await some_local.async_unload_entry(hass, mock_config_entry)
""",
            "tests.components.ps4.test_init",
            id="unresolved_attribute_call",
        ),
        pytest.param(
            """
async def async_unload_entry(hass, entry):
    return True

async def test_unload(hass, entry):
    await async_unload_entry(hass, entry)
""",
            "tests.components.ps4.test_init",
            id="local_async_unload_entry_not_an_integration",
        ),
    ],
)
def test_no_warning(
    linter: UnittestLinter,
    checker: DirectAsyncUnloadEntry,
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
    ("code", "module_name"),
    [
        pytest.param(
            """
from homeassistant.components.ps4 import async_unload_entry

async def test_unload(hass, mock_config_entry):
    await async_unload_entry(hass, mock_config_entry)
""",
            "tests.components.ps4.test_init",
            id="direct_name_call",
        ),
        pytest.param(
            """
from homeassistant.components import ps4

async def test_unload(hass, mock_config_entry):
    await ps4.async_unload_entry(hass, mock_config_entry)
""",
            "tests.components.ps4.test_init",
            id="attribute_call",
        ),
    ],
)
def test_warning(
    linter: UnittestLinter,
    checker: DirectAsyncUnloadEntry,
    code: str,
    module_name: str,
) -> None:
    """Test cases that should trigger a warning."""
    root_node = astroid.parse(code, module_name)
    walker = ASTWalker(linter)
    walker.add_checker(checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "home-assistant-tests-direct-async-unload-entry"


def test_multiple_calls_each_flagged(
    linter: UnittestLinter,
    checker: DirectAsyncUnloadEntry,
) -> None:
    """Test that multiple direct calls are each flagged."""
    root_node = astroid.parse(
        """
from homeassistant.components.ps4 import async_unload_entry

async def test_a(hass, mock_config_entry):
    await async_unload_entry(hass, mock_config_entry)

async def test_b(hass, mock_config_entry):
    await async_unload_entry(hass, mock_config_entry)
""",
        "tests.components.ps4.test_init",
    )
    walker = ASTWalker(linter)
    walker.add_checker(checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 2

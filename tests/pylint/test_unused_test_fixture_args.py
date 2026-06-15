"""Tests for the unused test fixture arguments checker."""

import astroid
from pylint.testutils import UnittestLinter
from pylint.utils.ast_walker import ASTWalker
from pylint_home_assistant.checkers.unused_test_fixture_args import (
    UnusedTestFixtureArgsChecker,
)
import pytest

from . import assert_no_messages


@pytest.fixture(name="unused_args_checker")
def unused_args_checker_fixture(
    linter: UnittestLinter,
) -> UnusedTestFixtureArgsChecker:
    """Fixture to provide an unused test fixture args checker."""
    return UnusedTestFixtureArgsChecker(linter)


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
def test_something(hass: HomeAssistant) -> None:
    assert hass.state
""",
            id="all_args_used",
        ),
        pytest.param(
            """
def test_something(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    hass.states.async_set("sensor.test", "on")
    config_entry.add_to_hass(hass)
""",
            id="multiple_args_all_used",
        ),
        pytest.param(
            """
@pytest.fixture
def my_fixture(enable_bluetooth: None) -> None:
    pass
""",
            id="fixture_function_ignored",
        ),
        pytest.param(
            """
def helper_function(unused_arg: str) -> None:
    pass
""",
            id="non_test_function_ignored",
        ),
        pytest.param(
            """
def test_empty() -> None:
    pass
""",
            id="no_args",
        ),
    ],
)
def test_no_warning(
    linter: UnittestLinter,
    unused_args_checker: UnusedTestFixtureArgsChecker,
    code: str,
) -> None:
    """Test cases that should not trigger a warning."""
    root_node = astroid.parse(code, "tests.components.test_integration.test_init")
    walker = ASTWalker(linter)
    walker.add_checker(unused_args_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


def test_unused_single_arg(
    linter: UnittestLinter,
    unused_args_checker: UnusedTestFixtureArgsChecker,
) -> None:
    """Test that unused fixture arg is flagged."""
    root_node = astroid.parse(
        """
def test_something(hass: HomeAssistant, enable_bluetooth: None) -> None:
    assert hass.state
""",
        "tests.components.test_integration.test_init",
    )
    walker = ASTWalker(linter)
    walker.add_checker(unused_args_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "home-assistant-unused-test-fixture-argument"
    assert messages[0].args == (
        "enable_bluetooth",
        "test_something",
        "enable_bluetooth",
    )


def test_unused_multiple_args(
    linter: UnittestLinter,
    unused_args_checker: UnusedTestFixtureArgsChecker,
) -> None:
    """Test that multiple unused fixture args are all flagged."""
    root_node = astroid.parse(
        """
def test_something(
    hass: HomeAssistant, enable_bluetooth: None, socket_enabled: None
) -> None:
    assert hass.state
""",
        "tests.components.test_integration.test_init",
    )
    walker = ASTWalker(linter)
    walker.add_checker(unused_args_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 2
    assert messages[0].args[0] == "enable_bluetooth"
    assert messages[1].args[0] == "socket_enabled"


def test_not_test_module(
    linter: UnittestLinter,
    unused_args_checker: UnusedTestFixtureArgsChecker,
) -> None:
    """Test that non-test modules are ignored."""
    root_node = astroid.parse(
        """
def test_something(unused: str) -> None:
    pass
""",
        "homeassistant.components.test_integration",
    )
    walker = ASTWalker(linter)
    walker.add_checker(unused_args_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


def test_async_test_function(
    linter: UnittestLinter,
    unused_args_checker: UnusedTestFixtureArgsChecker,
) -> None:
    """Test that async test functions are also checked."""
    root_node = astroid.parse(
        """
async def test_something(hass: HomeAssistant, enable_bluetooth: None) -> None:
    assert hass.state
""",
        "tests.components.test_integration.test_init",
    )
    walker = ASTWalker(linter)
    walker.add_checker(unused_args_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].args[0] == "enable_bluetooth"

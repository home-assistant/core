"""Tests for the sequential executor jobs checker."""

import astroid
from pylint.testutils import UnittestLinter
from pylint.utils.ast_walker import ASTWalker
from pylint_home_assistant.checkers.sequential_executor_jobs import (
    SequentialExecutorJobsChecker,
)
import pytest

from . import assert_no_messages


@pytest.fixture(name="executor_checker")
def executor_checker_fixture(
    linter: UnittestLinter,
) -> SequentialExecutorJobsChecker:
    """Fixture to provide a sequential executor jobs checker."""
    return SequentialExecutorJobsChecker(linter)


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
async def async_setup(hass, config):
    await hass.async_add_executor_job(blocking_call)
""",
            id="single_call",
        ),
        pytest.param(
            """
async def async_setup(hass, config):
    await hass.async_add_executor_job(call_a)
    result = do_something()
    await hass.async_add_executor_job(call_b)
""",
            id="separated_by_other_statement",
        ),
        pytest.param(
            """
async def async_setup(hass, config):
    await hass.async_add_executor_job(call_a)
    await hass.async_do_something_else()
    await hass.async_add_executor_job(call_b)
""",
            id="separated_by_other_await",
        ),
    ],
)
def test_no_warning(
    linter: UnittestLinter,
    executor_checker: SequentialExecutorJobsChecker,
    code: str,
) -> None:
    """Test cases that should not trigger a warning."""
    root_node = astroid.parse(code, "homeassistant.components.test_integration")
    walker = ASTWalker(linter)
    walker.add_checker(executor_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


def test_two_sequential_flagged(
    linter: UnittestLinter,
    executor_checker: SequentialExecutorJobsChecker,
) -> None:
    """Test that two sequential executor jobs are flagged."""
    root_node = astroid.parse(
        """
async def async_setup(hass, config):
    await hass.async_add_executor_job(call_a)
    await hass.async_add_executor_job(call_b)
""",
        "homeassistant.components.test_integration",
    )
    walker = ASTWalker(linter)
    walker.add_checker(executor_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "home-assistant-sequential-executor-jobs"


def test_three_sequential_flagged(
    linter: UnittestLinter,
    executor_checker: SequentialExecutorJobsChecker,
) -> None:
    """Test that three sequential executor jobs flag the second and third."""
    root_node = astroid.parse(
        """
async def async_setup(hass, config):
    await hass.async_add_executor_job(call_a)
    await hass.async_add_executor_job(call_b)
    await hass.async_add_executor_job(call_c)
""",
        "homeassistant.components.test_integration",
    )
    walker = ASTWalker(linter)
    walker.add_checker(executor_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 2


def test_assigned_sequential_flagged(
    linter: UnittestLinter,
    executor_checker: SequentialExecutorJobsChecker,
) -> None:
    """Test that assigned sequential executor jobs are also flagged."""
    root_node = astroid.parse(
        """
async def async_setup(hass, config):
    result_a = await hass.async_add_executor_job(call_a)
    result_b = await hass.async_add_executor_job(call_b)
""",
        "homeassistant.components.test_integration",
    )
    walker = ASTWalker(linter)
    walker.add_checker(executor_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1


def test_inside_try_block_flagged(
    linter: UnittestLinter,
    executor_checker: SequentialExecutorJobsChecker,
) -> None:
    """Test that sequential calls inside a try block are flagged."""
    root_node = astroid.parse(
        """
async def async_setup(hass, config):
    try:
        await hass.async_add_executor_job(call_a)
        await hass.async_add_executor_job(call_b)
    except Exception:
        pass
""",
        "homeassistant.components.test_integration",
    )
    walker = ASTWalker(linter)
    walker.add_checker(executor_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1


def test_inside_except_block_flagged(
    linter: UnittestLinter,
    executor_checker: SequentialExecutorJobsChecker,
) -> None:
    """Test that sequential calls inside an except block are flagged."""
    root_node = astroid.parse(
        """
async def async_setup(hass, config):
    try:
        pass
    except Exception:
        await hass.async_add_executor_job(call_a)
        await hass.async_add_executor_job(call_b)
""",
        "homeassistant.components.test_integration",
    )
    walker = ASTWalker(linter)
    walker.add_checker(executor_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "home-assistant-sequential-executor-jobs"


def test_inside_finally_block_flagged(
    linter: UnittestLinter,
    executor_checker: SequentialExecutorJobsChecker,
) -> None:
    """Test that sequential calls inside a finally block are flagged."""
    root_node = astroid.parse(
        """
async def async_setup(hass, config):
    try:
        pass
    finally:
        await hass.async_add_executor_job(call_a)
        await hass.async_add_executor_job(call_b)
""",
        "homeassistant.components.test_integration",
    )
    walker = ASTWalker(linter)
    walker.add_checker(executor_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "home-assistant-sequential-executor-jobs"


def test_inside_for_else_block_flagged(
    linter: UnittestLinter,
    executor_checker: SequentialExecutorJobsChecker,
) -> None:
    """Test that sequential calls inside a for/else block are flagged."""
    root_node = astroid.parse(
        """
async def async_setup(hass, config):
    for item in items:
        pass
    else:
        await hass.async_add_executor_job(call_a)
        await hass.async_add_executor_job(call_b)
""",
        "homeassistant.components.test_integration",
    )
    walker = ASTWalker(linter)
    walker.add_checker(executor_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "home-assistant-sequential-executor-jobs"


def test_return_await_sequential_flagged(
    linter: UnittestLinter,
    executor_checker: SequentialExecutorJobsChecker,
) -> None:
    """Test that return await following an executor job is flagged."""
    root_node = astroid.parse(
        """
async def async_setup(hass, config):
    await hass.async_add_executor_job(call_a)
    return await hass.async_add_executor_job(call_b)
""",
        "homeassistant.components.test_integration",
    )
    walker = ASTWalker(linter)
    walker.add_checker(executor_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "home-assistant-sequential-executor-jobs"


def test_not_integration_module_ignored(
    linter: UnittestLinter,
    executor_checker: SequentialExecutorJobsChecker,
) -> None:
    """Test that non-integration modules are ignored."""
    root_node = astroid.parse(
        """
async def async_setup(hass, config):
    await hass.async_add_executor_job(call_a)
    await hass.async_add_executor_job(call_b)
""",
        "tests.components.test_integration",
    )
    walker = ASTWalker(linter)
    walker.add_checker(executor_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)

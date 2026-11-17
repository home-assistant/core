"""Tests for the redundant caplog level checker."""

import astroid
from pylint.testutils import UnittestLinter
from pylint_home_assistant.checkers.tests.redundant_caplog_level import (
    RedundantCaplogLevelChecker,
)
import pytest

from tests.pylint import assert_no_messages, walk_checker

TEST_MODULE = "tests.components.pylint_test.test_init"


@pytest.fixture(name="checker")
def checker_fixture(linter: UnittestLinter) -> RedundantCaplogLevelChecker:
    """Fixture to provide a redundant caplog level checker."""
    return RedundantCaplogLevelChecker(linter)


@pytest.mark.parametrize(
    ("code", "method"),
    [
        pytest.param(
            """
import logging

def test_something(caplog):
    caplog.set_level(logging.DEBUG)
""",
            "set_level",
            id="set_level_logging_debug",
        ),
        pytest.param(
            """
from logging import DEBUG

def test_something(caplog):
    caplog.set_level(DEBUG)
""",
            "set_level",
            id="set_level_imported_debug",
        ),
        pytest.param(
            """
def test_something(caplog):
    caplog.set_level("DEBUG")
""",
            "set_level",
            id="set_level_string_debug",
        ),
        pytest.param(
            """
import logging

def test_something(caplog):
    caplog.set_level(level=logging.DEBUG, logger=None)
""",
            "set_level",
            id="set_level_keywords_root_logger",
        ),
        pytest.param(
            """
import logging

async def test_something(caplog):
    with caplog.at_level(logging.DEBUG):
        pass
""",
            "at_level",
            id="at_level_async_test",
        ),
        pytest.param(
            """
import logging
import pytest

@pytest.fixture
def my_fixture(caplog):
    caplog.set_level(logging.DEBUG)
""",
            "set_level",
            id="fixture",
        ),
        pytest.param(
            """
import logging

def test_something(caplog):
    with caplog.at_level(logging.WARNING):
        pass
    caplog.set_level(logging.DEBUG)
""",
            "set_level",
            id="after_at_level_block",
        ),
    ],
)
def test_redundant_debug_level(
    linter: UnittestLinter,
    checker: RedundantCaplogLevelChecker,
    code: str,
    method: str,
) -> None:
    """Test that setting the root caplog level to DEBUG is flagged."""
    walk_checker(linter, checker, astroid.parse(code, TEST_MODULE))

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "home-assistant-tests-redundant-caplog-level"
    assert messages[0].args == (method,)


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
import logging

def test_something(caplog):
    caplog.set_level(logging.INFO)
    caplog.set_level(logging.WARNING)
    with caplog.at_level(logging.ERROR):
        pass
""",
            id="other_levels",
        ),
        pytest.param(
            """
import logging

def test_something(caplog):
    caplog.set_level(logging.DEBUG, logger="homeassistant.components.hue")
    caplog.set_level(logging.DEBUG, "homeassistant.components.hue")
    with caplog.at_level(logging.DEBUG, logger="homeassistant.components.hue"):
        pass
""",
            id="named_logger",
        ),
        pytest.param(
            """
import logging

def test_something(caplog):
    caplog.set_level(logging.WARNING)
    caplog.set_level(logging.DEBUG)
""",
            id="restores_debug",
        ),
        pytest.param(
            """
import logging

def test_something(caplog):
    with caplog.at_level(logging.WARNING):
        with caplog.at_level(logging.DEBUG):
            pass
""",
            id="nested_at_level",
        ),
        pytest.param(
            """
def test_something(caplog, level):
    with caplog.at_level(level):
        pass
""",
            id="unknown_level",
        ),
        pytest.param(
            """
import logging

def test_something(other):
    other.set_level(logging.DEBUG)
""",
            id="not_caplog",
        ),
    ],
)
def test_no_warning(
    linter: UnittestLinter,
    checker: RedundantCaplogLevelChecker,
    code: str,
) -> None:
    """Test cases that should not be flagged."""
    with assert_no_messages(linter):
        walk_checker(linter, checker, astroid.parse(code, TEST_MODULE))


def test_not_test_module(
    linter: UnittestLinter,
    checker: RedundantCaplogLevelChecker,
) -> None:
    """Test that non-test modules are ignored."""
    code = """
import logging

def setup(caplog):
    caplog.set_level(logging.DEBUG)
"""
    with assert_no_messages(linter):
        walk_checker(
            linter, checker, astroid.parse(code, "homeassistant.components.hue")
        )

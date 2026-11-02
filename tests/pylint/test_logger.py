"""Tests for the logger checker."""

import astroid
from pylint.checkers import BaseChecker
from pylint.interfaces import UNDEFINED
from pylint.testutils import MessageTest
from pylint.testutils.unittest_linter import UnittestLinter
from pylint_home_assistant.checkers.logger import HassLoggerFormatChecker
import pytest

from . import assert_adds_messages, assert_no_messages, walk_checker


@pytest.fixture(name="logger_checker")
def logger_checker_fixture(linter: UnittestLinter) -> BaseChecker:
    """Fixture to provide a logger checker."""
    return HassLoggerFormatChecker(linter)


@pytest.mark.parametrize(
    ("code", "module_name"),
    [
        pytest.param(
            """
            import logging
            LOGGER = logging.getLogger(__package__)
            """,
            "homeassistant.components.pylint_test.const",
            id="const_package",
        ),
        pytest.param(
            """
            from logging import getLogger
            LOGGER = getLogger(__package__)
            """,
            "homeassistant.components.pylint_test.const",
            id="const_package_imported_function",
        ),
        pytest.param(
            """
            import logging
            LOGGER = logging.getLogger(name=__package__)
            """,
            "homeassistant.components.pylint_test.const",
            id="const_package_keyword",
        ),
        pytest.param(
            """
            import logging
            LIB_LOGGER = logging.getLogger("library")
            """,
            "homeassistant.components.pylint_test.const",
            id="const_library_logger",
        ),
        pytest.param(
            """
            import logging
            _LOGGER = logging.getLogger(__name__)
            """,
            "homeassistant.components.pylint_test.sensor",
            id="other_module_name",
        ),
        pytest.param(
            """
            import logging
            _LOGGER = logging.getLogger(__name__)
            """,
            "homeassistant.components.pylint_test.sub.const",
            id="nested_const_name",
        ),
        pytest.param(
            """
            import logging
            _LOGGER = logging.getLogger(__name__)
            """,
            "homeassistant.const",
            id="core_const_name",
        ),
    ],
)
def test_logger_const_name_good(
    linter: UnittestLinter,
    logger_checker: BaseChecker,
    code: str,
    module_name: str,
) -> None:
    """Test loggers that are allowed."""
    root_node = astroid.parse(code, module_name)

    with assert_no_messages(linter):
        walk_checker(linter, logger_checker, root_node)


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
            import logging
            LOGGER = logging.getLogger(__name__)
            """,
            id="logging_module",
        ),
        pytest.param(
            """
            from logging import getLogger
            LOGGER = getLogger(__name__)
            """,
            id="imported_function",
        ),
        pytest.param(
            """
            import logging
            LOGGER = logging.getLogger(name=__name__)
            """,
            id="keyword_argument",
        ),
    ],
)
def test_logger_const_name_bad(
    linter: UnittestLinter,
    logger_checker: BaseChecker,
    code: str,
) -> None:
    """Test loggers named after the const module."""
    root_node = astroid.parse(code, "homeassistant.components.pylint_test.const")
    call_node = root_node.body[1].value

    with assert_adds_messages(
        linter,
        MessageTest(
            msg_id="home-assistant-logger-const-name",
            line=3,
            node=call_node,
            args=None,
            confidence=UNDEFINED,
            col_offset=9,
            end_line=3,
            end_col_offset=call_node.end_col_offset,
        ),
    ):
        walk_checker(linter, logger_checker, root_node)

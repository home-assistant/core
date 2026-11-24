"""Tests for the config flow no CONNECTION_CLASS checker."""

from __future__ import annotations

import astroid
from pylint.checkers import BaseChecker
from pylint.testutils.unittest_linter import UnittestLinter
import pytest

from tests.pylint import assert_no_messages, walk_checker

CONFIG_FLOW_MODULE = "homeassistant.components.test.config_flow"


@pytest.mark.parametrize(
    ("code", "module_name"),
    [
        pytest.param(
            """
        class TestFlow:
            VERSION = 1
        """,
            CONFIG_FLOW_MODULE,
            id="no_connection_class",
        ),
        pytest.param(
            """
        class TestFlow:
            CONNECTION_CLASS = "local_polling"
        """,
            "homeassistant.components.test.sensor",
            id="other_module",
        ),
        pytest.param(
            """
        CONNECTION_CLASS = "local_polling"
        """,
            CONFIG_FLOW_MODULE,
            id="module_level",
        ),
    ],
)
def test_no_connection_class(
    linter: UnittestLinter,
    enforce_config_flow_no_connection_class_checker: BaseChecker,
    code: str,
    module_name: str,
) -> None:
    """Good test cases."""
    root_node = astroid.parse(code, module_name)

    with assert_no_messages(linter):
        walk_checker(linter, enforce_config_flow_no_connection_class_checker, root_node)


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
        class TestFlow:
            CONNECTION_CLASS = "local_polling"
        """,
            id="assign",
        ),
        pytest.param(
            """
        class TestFlow:
            CONNECTION_CLASS: str = "local_polling"
        """,
            id="annotated_assign",
        ),
    ],
)
def test_no_connection_class_bad(
    linter: UnittestLinter,
    enforce_config_flow_no_connection_class_checker: BaseChecker,
    code: str,
) -> None:
    """Bad test cases."""
    root_node = astroid.parse(code, CONFIG_FLOW_MODULE)

    walk_checker(linter, enforce_config_flow_no_connection_class_checker, root_node)
    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "home-assistant-config-flow-connection-class"

"""Tests for the flow manager internals checker."""

import astroid
from astroid import nodes
from pylint.testutils import MessageTest, UnittestLinter
from pylint_home_assistant.checkers.tests.flow_manager_internals import (
    FlowManagerInternalsChecker,
)
import pytest

from tests.pylint import assert_adds_messages, assert_no_messages, walk_checker

TEST_MODULE = "tests.components.test_integration.test_config_flow"
MSG_ID = "home-assistant-tests-flow-manager-internals"


@pytest.fixture(name="checker")
def checker_fixture(linter: UnittestLinter) -> FlowManagerInternalsChecker:
    """Fixture to provide a flow manager internals checker."""
    return FlowManagerInternalsChecker(linter)


@pytest.mark.parametrize(
    ("code", "module"),
    [
        pytest.param(
            """
result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
flows = hass.config_entries.flow.async_progress()
""",
            TEST_MODULE,
            id="public_api",
        ),
        pytest.param(
            "entries = hass.config_entries._entries",
            TEST_MODULE,
            id="not_a_flow_manager",
        ),
        pytest.param(
            "handler = flow._progress[flow_id]",
            TEST_MODULE,
            id="unrelated_name",
        ),
        pytest.param(
            "hass.config_entries.flow.__class__",
            TEST_MODULE,
            id="dunder",
        ),
        pytest.param(
            'handler = hass.config_entries.flow._progress["abc"]',
            "tests.test_config_entries",
            id="core_tests",
        ),
        pytest.param(
            'handler = hass.config_entries.flow._progress["abc"]',
            "homeassistant.components.test_integration.config_flow",
            id="integration_code",
        ),
    ],
)
def test_no_warning(
    linter: UnittestLinter,
    checker: FlowManagerInternalsChecker,
    code: str,
    module: str,
) -> None:
    """Test cases that should not trigger a warning."""
    root_node = astroid.parse(code, module)

    with assert_no_messages(linter):
        walk_checker(linter, checker, root_node)


@pytest.mark.parametrize(
    ("code", "attrname"),
    [
        pytest.param(
            'handler = hass.config_entries.flow._progress[result["flow_id"]]',
            "_progress",
            id="flow_progress",
        ),
        pytest.param(
            'handler = hass.config_entries.options._progress[result["flow_id"]]',
            "_progress",
            id="options_progress",
        ),
        pytest.param(
            'handler = hass.config_entries.subentries._progress[result["flow_id"]]',
            "_progress",
            id="subentries_progress",
        ),
        pytest.param(
            "flows = hass.config_entries.flow._handler_progress_index[DOMAIN]",
            "_handler_progress_index",
            id="handler_index",
        ),
        pytest.param(
            'hass.config_entries.flow._async_remove_flow_progress(result["flow_id"])',
            "_async_remove_flow_progress",
            id="private_method",
        ),
        pytest.param(
            "hass.config_entries.flow._progress = {}",
            "_progress",
            id="assignment",
        ),
        pytest.param(
            """
manager = hass.config_entries.flow
handler = manager._progress[flow_id]
""",
            "_progress",
            id="alias",
        ),
    ],
)
def test_warning(
    linter: UnittestLinter,
    checker: FlowManagerInternalsChecker,
    code: str,
    attrname: str,
) -> None:
    """Test cases that should trigger a warning."""
    root_node = astroid.parse(code, TEST_MODULE)
    node = next(
        node
        for node in root_node.nodes_of_class((nodes.Attribute, nodes.AssignAttr))
        if node.attrname == attrname
    )

    with assert_adds_messages(
        linter,
        MessageTest(
            msg_id=MSG_ID,
            node=node,
            args=(attrname,),
            line=node.lineno,
            col_offset=node.col_offset,
            end_line=node.end_lineno,
            end_col_offset=node.end_col_offset,
        ),
    ):
        walk_checker(linter, checker, root_node)

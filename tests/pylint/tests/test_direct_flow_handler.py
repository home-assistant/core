"""Tests for the direct flow handler checker."""

import astroid
from astroid import nodes
from pylint.testutils import MessageTest, UnittestLinter
from pylint_home_assistant.checkers.tests.direct_flow_handler import (
    DirectFlowHandlerChecker,
)
import pytest

from tests.pylint import assert_adds_messages, assert_no_messages, walk_checker

TEST_MODULE = "tests.components.pylint_test.test_config_flow"


@pytest.fixture(name="checker")
def checker_fixture(linter: UnittestLinter) -> DirectFlowHandlerChecker:
    """Fixture to provide a direct flow handler checker."""
    return DirectFlowHandlerChecker(linter)


def _module(code: str, module: str = TEST_MODULE) -> nodes.Module:
    """Parse *code* with a fake flow handler hierarchy available."""
    astroid.parse(
        """
class FlowHandler:
    pass
""",
        "homeassistant.data_entry_flow",
    )
    astroid.parse(
        """
from homeassistant.data_entry_flow import FlowHandler

class ConfigFlow(FlowHandler):
    pass
""",
        "homeassistant.config_entries",
    )
    astroid.parse(
        """
from homeassistant.config_entries import ConfigFlow

class PylintTestConfigFlow(ConfigFlow):
    pass

class NotAFlow:
    pass
""",
        "homeassistant.components.pylint_test.config_flow",
    )
    return astroid.parse(code, module)


def _expect(node: nodes.Call, msg_id: str, arg: str) -> MessageTest:
    """Build the expected message."""
    return MessageTest(
        msg_id=msg_id,
        node=node,
        args=(arg,),
        line=node.lineno,
        col_offset=node.col_offset,
        end_line=node.end_lineno,
        end_col_offset=node.end_col_offset,
    )


@pytest.mark.parametrize(
    ("code", "module"),
    [
        pytest.param(
            """
result = await hass.config_entries.flow.async_init(
    DOMAIN, context={"source": SOURCE_USER}
)
result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
""",
            TEST_MODULE,
            id="flow_manager",
        ),
        pytest.param(
            """
from homeassistant.components.pylint_test.config_flow import NotAFlow

thing = NotAFlow()
""",
            TEST_MODULE,
            id="not_a_flow_handler",
        ),
        pytest.param(
            """
from homeassistant.components.pylint_test.config_flow import PylintTestConfigFlow

flow = PylintTestConfigFlow()
""",
            "tests.test_config_entries",
            id="core_tests",
        ),
        pytest.param(
            """
from homeassistant.components.pylint_test.config_flow import PylintTestConfigFlow

flow = PylintTestConfigFlow()
""",
            "homeassistant.components.other.config_flow",
            id="integration_code",
        ),
        pytest.param(
            """
from homeassistant.components.pylint_test.config_flow import PylintTestConfigFlow

patch.object(PylintTestConfigFlow, "async_step_user")
""",
            TEST_MODULE,
            id="not_instantiated",
        ),
    ],
)
def test_no_warning(
    linter: UnittestLinter,
    checker: DirectFlowHandlerChecker,
    code: str,
    module: str,
) -> None:
    """Test cases that should not trigger a warning."""
    root_node = _module(code, module)

    with assert_no_messages(linter):
        walk_checker(linter, checker, root_node)


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
from homeassistant.components.pylint_test.config_flow import PylintTestConfigFlow

flow = PylintTestConfigFlow()
""",
            id="from_import",
        ),
        pytest.param(
            """
import homeassistant.components.pylint_test.config_flow as config_flow

flow = config_flow.PylintTestConfigFlow()
""",
            id="module_import",
        ),
    ],
)
def test_flow_handler_created(
    linter: UnittestLinter,
    checker: DirectFlowHandlerChecker,
    code: str,
) -> None:
    """Test creating an integration flow handler is flagged."""
    root_node = _module(code)
    call = next(root_node.nodes_of_class(nodes.Call))

    with assert_adds_messages(
        linter,
        _expect(
            call, "home-assistant-tests-direct-flow-handler", "PylintTestConfigFlow"
        ),
    ):
        walk_checker(linter, checker, root_node)

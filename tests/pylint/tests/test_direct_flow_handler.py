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
class MockFlow(ConfigFlow):
    async def async_step_user(self, user_input=None):
        return await self.async_step_confirm()

    async def async_step_reauth(self, entry_data):
        return await super().async_step_reauth(entry_data)
""",
            TEST_MODULE,
            id="own_steps_in_test_flow",
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
await flow.async_step_user()
""",
            "tests.test_config_entries",
            id="core_tests",
        ),
        pytest.param(
            """
from homeassistant.components.pylint_test.config_flow import PylintTestConfigFlow

flow = PylintTestConfigFlow()
await flow.async_step_user()
""",
            "homeassistant.components.other.config_flow",
            id="integration_code",
        ),
        pytest.param(
            """
mock_flow.async_step_user.assert_called_once()
patch.object(PylintTestConfigFlow, "async_step_user")
""",
            TEST_MODULE,
            id="not_called",
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


@pytest.mark.parametrize(
    ("code", "step"),
    [
        pytest.param(
            "result = await flow.async_step_user()",
            "async_step_user",
            id="user",
        ),
        pytest.param(
            "result = await handler.async_step_reauth_confirm({CONF_PASSWORD: 'x'})",
            "async_step_reauth_confirm",
            id="other_receiver",
        ),
        pytest.param(
            'result = await hass.config_entries.flow._progress["abc"].async_step_user()',
            "async_step_user",
            id="handler_from_progress",
        ),
    ],
)
def test_step_called(
    linter: UnittestLinter,
    checker: DirectFlowHandlerChecker,
    code: str,
    step: str,
) -> None:
    """Test calling a flow step directly is flagged."""
    root_node = _module(code)
    call = next(
        call
        for call in root_node.nodes_of_class(nodes.Call)
        if isinstance(call.func, nodes.Attribute) and call.func.attrname == step
    )

    with assert_adds_messages(
        linter, _expect(call, "home-assistant-tests-direct-flow-step", step)
    ):
        walk_checker(linter, checker, root_node)

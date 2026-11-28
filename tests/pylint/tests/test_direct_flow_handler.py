"""Tests for the direct flow handler checker."""

from collections.abc import Generator

import astroid
from astroid import nodes
from pylint.testutils import MessageTest, UnittestLinter
from pylint_home_assistant.checkers.tests.direct_flow_handler import (
    DirectFlowHandlerChecker,
)
import pytest

from tests.pylint import assert_adds_messages, assert_no_messages, walk_checker

astroid.MANAGER.ast_from_module_name("homeassistant.config_entries")
astroid.MANAGER.ast_from_module_name("homeassistant.components.repairs")

TEST_MODULE = "tests.components.direct_flow_handler_test.test_config_flow"
INTEGRATION_MODULE = "homeassistant.components.direct_flow_handler_test.config_flow"


@pytest.fixture(autouse=True)
def integration_module() -> Generator[None]:
    """Make a fake integration config flow module importable for the test."""
    # Other tests cache modules under shared names, and cache_module() never
    # replaces an existing entry, so set and restore the entry explicitly.
    cache = astroid.MANAGER.astroid_cache
    previous = cache.get(INTEGRATION_MODULE)
    cache[INTEGRATION_MODULE] = astroid.parse(
        """
from homeassistant.components.repairs import RepairsFlow
from homeassistant.config_entries import ConfigFlow, ConfigSubentryFlow, OptionsFlow

class PylintTestConfigFlow(ConfigFlow):
    pass

class PylintTestOptionsFlow(OptionsFlow):
    pass

class PylintTestSubentryFlow(ConfigSubentryFlow):
    pass

class PylintTestRepairFlow(RepairsFlow):
    pass

class NotAFlow:
    pass
""",
        INTEGRATION_MODULE,
    )
    yield
    if previous is None:
        cache.pop(INTEGRATION_MODULE, None)
    else:
        cache[INTEGRATION_MODULE] = previous


@pytest.fixture(name="checker")
def checker_fixture(linter: UnittestLinter) -> DirectFlowHandlerChecker:
    """Fixture to provide a direct flow handler checker."""
    return DirectFlowHandlerChecker(linter)


def _module(code: str, module: str = TEST_MODULE) -> nodes.Module:
    """Parse *code* as the given module."""
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
from homeassistant.components.direct_flow_handler_test.config_flow import NotAFlow

thing = NotAFlow()
""",
            TEST_MODULE,
            id="not_a_flow_handler",
        ),
        pytest.param(
            """
from homeassistant.components.direct_flow_handler_test.config_flow import PylintTestConfigFlow

flow = PylintTestConfigFlow()
""",
            "tests.test_config_entries",
            id="core_tests",
        ),
        pytest.param(
            """
from homeassistant.components.direct_flow_handler_test.config_flow import PylintTestConfigFlow

flow = PylintTestConfigFlow()
""",
            "homeassistant.components.other.config_flow",
            id="integration_code",
        ),
        pytest.param(
            """
from homeassistant.components.direct_flow_handler_test.config_flow import PylintTestConfigFlow

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
    "class_name",
    [
        "PylintTestConfigFlow",
        "PylintTestOptionsFlow",
        "PylintTestSubentryFlow",
        "PylintTestRepairFlow",
    ],
)
@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            f"""
from {INTEGRATION_MODULE} import {{class_name}}

flow = {{class_name}}()
""",
            id="from_import",
        ),
        pytest.param(
            f"""
import {INTEGRATION_MODULE} as config_flow

flow = config_flow.{{class_name}}()
""",
            id="module_import",
        ),
    ],
)
def test_flow_handler_created(
    linter: UnittestLinter,
    checker: DirectFlowHandlerChecker,
    code: str,
    class_name: str,
) -> None:
    """Test creating an integration flow handler is flagged."""
    root_node = _module(code.format(class_name=class_name))
    call = next(root_node.nodes_of_class(nodes.Call))

    with assert_adds_messages(
        linter,
        _expect(call, "home-assistant-tests-direct-flow-handler", class_name),
    ):
        walk_checker(linter, checker, root_node)

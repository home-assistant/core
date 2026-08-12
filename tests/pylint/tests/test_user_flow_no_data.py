"""Tests for the user flow no-data checker."""

import astroid
from astroid import nodes
from pylint.testutils import MessageTest, UnittestLinter
from pylint_home_assistant.checkers.tests.user_flow_no_data import UserFlowNoDataChecker
import pytest

from tests.pylint import assert_adds_messages, assert_no_messages, walk_checker


@pytest.fixture(name="user_flow_no_data_checker")
def user_flow_no_data_checker_fixture(
    linter: UnittestLinter,
) -> UserFlowNoDataChecker:
    """Fixture to provide a user flow no-data checker."""
    return UserFlowNoDataChecker(linter)


def _find_async_init_call(root_node: nodes.Module) -> nodes.Call:
    """Find the first ``*.async_init(...)`` call node."""
    for call in root_node.nodes_of_class(nodes.Call):
        func = call.func
        if isinstance(func, nodes.Attribute) and func.attrname == "async_init":
            return call
    raise AssertionError("no async_init call found")


def _expect_message(node: nodes.Call) -> MessageTest:
    """Build the expected MessageTest for a user flow no-data violation."""
    return MessageTest(
        msg_id="home-assistant-tests-user-flow-no-data",
        node=node,
        line=node.lineno,
        col_offset=node.col_offset,
        end_line=node.end_lineno,
        end_col_offset=node.end_col_offset,
    )


@pytest.mark.parametrize(
    "context",
    [
        '{"source": SOURCE_USER}',
        '{"source": config_entries.SOURCE_USER}',
        '{"source": "user"}',
        "ConfigFlowContext(source=SOURCE_USER)",
        "config_entries.ConfigFlowContext(source=config_entries.SOURCE_USER)",
    ],
    ids=[
        "dict_const",
        "dict_attribute",
        "dict_literal",
        "context_call",
        "context_attr",
    ],
)
@pytest.mark.parametrize(
    "manager",
    ["flow", "subentries"],
)
def test_user_flow_with_data_flagged(
    linter: UnittestLinter,
    user_flow_no_data_checker: UserFlowNoDataChecker,
    context: str,
    manager: str,
) -> None:
    """A user flow init with a data argument is flagged."""
    root_node = astroid.parse(
        f"""
async def test_something(hass) -> None:
    result = await hass.config_entries.{manager}.async_init(
        DOMAIN,
        context={context},
        data={{"host": "127.0.0.1"}},
    )
""",
        "tests.components.test_integration.test_config_flow",
    )
    call_node = _find_async_init_call(root_node)

    with assert_adds_messages(linter, _expect_message(call_node)):
        walk_checker(linter, user_flow_no_data_checker, root_node)


@pytest.mark.parametrize(
    ("code", "module_name"),
    [
        pytest.param(
            """
async def test_something(hass) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
""",
            "tests.components.test_integration.test_config_flow",
            id="user_flow_without_data",
        ),
        pytest.param(
            """
async def test_something(hass) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data={"host": "127.0.0.1"},
    )
""",
            "tests.components.test_integration.test_config_flow",
            id="zeroconf_flow_with_data",
        ),
        pytest.param(
            """
async def test_something(client) -> None:
    result = await client.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={"host": "127.0.0.1"},
    )
""",
            "tests.components.test_integration.test_config_flow",
            id="unrelated_async_init_receiver",
        ),
        pytest.param(
            """
async def test_something(hass) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context=Other(source=SOURCE_USER),
        data={"host": "127.0.0.1"},
    )
""",
            "tests.components.test_integration.test_config_flow",
            id="non_config_flow_context_call",
        ),
        pytest.param(
            """
async def test_something(hass) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "dhcp"},
        data={"host": "127.0.0.1"},
    )
""",
            "tests.components.test_integration.test_config_flow",
            id="dhcp_literal_flow_with_data",
        ),
        pytest.param(
            """
async def test_something(hass) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": source},
        data={"host": "127.0.0.1"},
    )
""",
            "tests.components.test_integration.test_config_flow",
            id="dynamic_source_with_data",
        ),
        pytest.param(
            """
async def test_something(hass) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data={"host": "127.0.0.1"},
    )
""",
            "tests.components.test_integration.test_config_flow",
            id="no_context",
        ),
        pytest.param(
            """
async def test_something(hass) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={"host": "127.0.0.1"},
    )
""",
            "homeassistant.components.test_integration.config_flow",
            id="not_a_test_module",
        ),
    ],
)
def test_no_warning(
    linter: UnittestLinter,
    user_flow_no_data_checker: UserFlowNoDataChecker,
    code: str,
    module_name: str,
) -> None:
    """Cases that should not produce a warning."""
    root_node = astroid.parse(code, module_name)

    with assert_no_messages(linter):
        walk_checker(linter, user_flow_no_data_checker, root_node)

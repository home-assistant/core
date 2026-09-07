"""Tests for the pylint config_flow menu_options checker."""

from __future__ import annotations

import astroid
from astroid import nodes
from pylint.testutils import MessageTest, UnittestLinter
from pylint_home_assistant.checkers.config_flow.menu_options import (
    HassConfigFlowMenuOptionsChecker,
)
import pytest

from tests.pylint import assert_adds_messages, assert_no_messages, walk_checker

CONFIG_FLOW_MODULE = "homeassistant.components.test.config_flow"


@pytest.fixture(name="checker")
def checker_fixture(linter: UnittestLinter) -> HassConfigFlowMenuOptionsChecker:
    """Fixture to provide a config_flow menu_options checker."""
    checker = HassConfigFlowMenuOptionsChecker(linter)
    checker.module = "homeassistant.components.pylint_test"
    return checker


def _find_menu_options_node(root_node: nodes.Module) -> nodes.NodeNG:
    """Find the ``menu_options`` value node of the ``async_show_menu`` call."""
    for call in root_node.nodes_of_class(nodes.Call):
        if (
            isinstance(call.func, nodes.Attribute)
            and call.func.attrname == "async_show_menu"
        ):
            for keyword in call.keywords:
                if keyword.arg == "menu_options":
                    return keyword.value
    raise AssertionError("no async_show_menu(menu_options=...) call found")


def _expect_missing_step(node: nodes.NodeNG, step_id: str) -> MessageTest:
    """Build the expected MessageTest for a missing ``async_step`` handler."""
    return MessageTest(
        msg_id="home-assistant-config-flow-menu-missing-step",
        node=node,
        line=node.lineno,
        col_offset=node.col_offset,
        end_line=node.end_lineno,
        end_col_offset=node.end_col_offset,
        args=(step_id, step_id),
    )


@pytest.mark.parametrize(
    ("code", "module_name"),
    [
        pytest.param(
            """
    class TestFlow:
        async def async_step_user(self, user_input=None):
            return self.async_show_menu(
                step_id="user",
                menu_options=["local", "cloud"],
            )

        async def async_step_local(self, user_input=None):
            pass

        async def async_step_cloud(self, user_input=None):
            pass
    """,
            CONFIG_FLOW_MODULE,
            id="list_all_present",
        ),
        pytest.param(
            """
    class TestFlow:
        async def async_step_user(self, user_input=None):
            return self.async_show_menu(
                menu_options={"local": "Local", "cloud": "Cloud"},
            )

        async def async_step_local(self, user_input=None):
            pass

        async def async_step_cloud(self, user_input=None):
            pass
    """,
            CONFIG_FLOW_MODULE,
            id="dict_all_present",
        ),
        pytest.param(
            """
    _MENU_OPTIONS = ["local", "cloud"]

    class TestFlow:
        async def async_step_user(self, user_input=None):
            return self.async_show_menu(menu_options=_MENU_OPTIONS)

        async def async_step_local(self, user_input=None):
            pass

        async def async_step_cloud(self, user_input=None):
            pass
    """,
            CONFIG_FLOW_MODULE,
            id="inferred_constant_all_present",
        ),
        pytest.param(
            """
    class BaseFlow:
        async def async_step_pick_implementation(self, user_input=None):
            pass

    class TestFlow(BaseFlow):
        async def async_step_user(self, user_input=None):
            return self.async_show_menu(
                menu_options=["pick_implementation", "manual"],
            )

        async def async_step_manual(self, user_input=None):
            pass
    """,
            CONFIG_FLOW_MODULE,
            id="inherited_step_present",
        ),
        pytest.param(
            """
    class TestFlow:
        async def async_step_user(self, user_input=None):
            return self.async_show_menu(
                menu_options=["location", "reconfigure"],
            )

        async def async_step_location(self, user_input=None):
            pass

        async_step_reconfigure = async_step_location
    """,
            CONFIG_FLOW_MODULE,
            id="aliased_step_present",
        ),
        pytest.param(
            """
    class TestFlow:
        async def async_step_init(self, user_input=None):
            return self.async_show_menu(
                menu_options=[option.value for option in SomeEnum],
            )
    """,
            CONFIG_FLOW_MODULE,
            id="comprehension_skipped",
        ),
        pytest.param(
            """
    class TestFlow:
        async def async_step_user(self, user_input=None):
            if self.show_cloud:
                options = ["local", "cloud"]
            else:
                options = ["local"]
            return self.async_show_menu(menu_options=options)

        async def async_step_local(self, user_input=None):
            pass
    """,
            CONFIG_FLOW_MODULE,
            id="ambiguous_inference_skipped",
        ),
        pytest.param(
            """
    class TestFlow:
        async def async_step_init(self, user_input=None):
            options = self._build_options()
            return self.async_show_menu(menu_options=options)
    """,
            CONFIG_FLOW_MODULE,
            id="unresolved_variable_skipped",
        ),
        pytest.param(
            """
    class TestFlow(SomeUnresolvedBase):
        async def async_step_user(self, user_input=None):
            return self.async_show_menu(menu_options=["from_base"])
    """,
            CONFIG_FLOW_MODULE,
            id="unresolved_base_skipped",
        ),
        pytest.param(
            """
    class BaseFlow(SomeUnresolvedBase):
        async def async_step_from_base(self, user_input=None):
            pass

    class TestFlow(BaseFlow):
        async def async_step_user(self, user_input=None):
            return self.async_show_menu(
                menu_options=["from_base", "cloud"],
            )
    """,
            CONFIG_FLOW_MODULE,
            id="unresolved_ancestor_skipped",
        ),
        pytest.param(
            """
    class TestFlow:
        async def async_step_user(self, user_input=None):
            return self.async_show_menu(menu_options=["only"])

        async def async_step_only(self, user_input=None):
            pass
    """,
            "homeassistant.components.test.options_flow",
            id="non_config_flow_module_skipped",
        ),
    ],
)
def test_menu_options_good(
    linter: UnittestLinter,
    checker: HassConfigFlowMenuOptionsChecker,
    code: str,
    module_name: str,
) -> None:
    """Good test cases that should not raise a message."""
    root_node = astroid.parse(code, module_name)

    with assert_no_messages(linter):
        walk_checker(linter, checker, root_node)


@pytest.mark.parametrize(
    ("code", "expected_steps"),
    [
        pytest.param(
            """
    class TestFlow:
        async def async_step_user(self, user_input=None):
            return self.async_show_menu(menu_options=["local", "cloud"])

        async def async_step_local(self, user_input=None):
            pass
    """,
            ["cloud"],
            id="list_missing_one",
        ),
        pytest.param(
            """
    class TestFlow:
        async def async_step_user(self, user_input=None):
            return self.async_show_menu(menu_options=["local", "cloud"])
    """,
            ["cloud", "local"],
            id="list_missing_all",
        ),
        pytest.param(
            """
    class TestFlow:
        async def async_step_user(self, user_input=None):
            return self.async_show_menu(
                menu_options={"local": "Local", "cloud": "Cloud"},
            )

        async def async_step_local(self, user_input=None):
            pass
    """,
            ["cloud"],
            id="dict_missing_one",
        ),
        pytest.param(
            """
    _MENU_OPTIONS = ["local", "cloud"]

    class TestFlow:
        async def async_step_user(self, user_input=None):
            return self.async_show_menu(menu_options=_MENU_OPTIONS)

        async def async_step_local(self, user_input=None):
            pass
    """,
            ["cloud"],
            id="inferred_constant_missing_one",
        ),
    ],
)
def test_menu_options_bad(
    linter: UnittestLinter,
    checker: HassConfigFlowMenuOptionsChecker,
    code: str,
    expected_steps: list[str],
) -> None:
    """Bad test cases that should raise a message per missing step."""
    root_node = astroid.parse(code, CONFIG_FLOW_MODULE)
    menu_options_node = _find_menu_options_node(root_node)

    with assert_adds_messages(
        linter,
        *(_expect_missing_step(menu_options_node, step) for step in expected_steps),
    ):
        walk_checker(linter, checker, root_node)

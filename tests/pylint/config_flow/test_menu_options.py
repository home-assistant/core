"""Tests for the pylint config_flow menu_options checker."""

from __future__ import annotations

import astroid
from pylint.checkers import BaseChecker
from pylint.testutils.unittest_linter import UnittestLinter
from pylint.utils.ast_walker import ASTWalker
import pytest

from tests.pylint import assert_no_messages

CONFIG_FLOW_MODULE = "homeassistant.components.test.config_flow"


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
    config_flow_menu_options_checker: BaseChecker,
    code: str,
    module_name: str,
) -> None:
    """Good test cases that should not raise a message."""
    root_node = astroid.parse(code, module_name)
    walker = ASTWalker(linter)
    walker.add_checker(config_flow_menu_options_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


def test_menu_options_inherited_step(
    linter: UnittestLinter,
    config_flow_menu_options_checker: BaseChecker,
) -> None:
    """A step defined on a resolvable base class should not be flagged."""
    code = """
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
    """
    root_node = astroid.parse(code, CONFIG_FLOW_MODULE)
    walker = ASTWalker(linter)
    walker.add_checker(config_flow_menu_options_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


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
    ],
)
def test_menu_options_bad(
    linter: UnittestLinter,
    config_flow_menu_options_checker: BaseChecker,
    code: str,
    expected_steps: list[str],
) -> None:
    """Bad test cases that should raise a message per missing step."""
    root_node = astroid.parse(code, CONFIG_FLOW_MODULE)
    walker = ASTWalker(linter)
    walker.add_checker(config_flow_menu_options_checker)

    walker.walk(root_node)
    messages = linter.release_messages()
    assert [message.args[0] for message in messages] == expected_steps
    for message in messages:
        assert message.msg_id == "home-assistant-config-flow-menu-missing-step"

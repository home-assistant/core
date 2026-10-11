"""Tests for pylint home-assistant-step_id-match-method plugin."""

import astroid
from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.testutils import MessageTest
from pylint.testutils.unittest_linter import UnittestLinter
from pylint_home_assistant.checkers.config_flow.step_id_match_method import CALLERS
import pytest

from tests.pylint import assert_adds_messages, assert_no_messages, walk_checker


def _find_step_call_node(root_node: nodes.Module) -> nodes.Call:
    """Find the call that takes a ``step_id`` argument."""
    for call in root_node.nodes_of_class(nodes.Call):
        if isinstance(call.func, nodes.Attribute) and call.func.attrname in CALLERS:
            return call
    raise AssertionError("no call with step_id found")


@pytest.mark.parametrize(
    ("code", "module_name"),
    [
        pytest.param(
            """
        async def async_step_user() -> FlowResult:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_USERNAME): str,
                }),
            )
        """,
            "homeassistant.components.test.config_flow",
            id="correct_method_user",
        ),
        pytest.param(
            """
        async def async_step_reconfigure() -> FlowResult:
            return self.async_show_form(
                step_id="reconfigure",
                data_schema=vol.Schema({
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_USERNAME): str,
                }),
            )
        """,
            "homeassistant.components.test.config_flow",
            id="correct_method_reconfigure",
        ),
        pytest.param(
            """
        async def async_step_custom() -> FlowResult:
            return self.async_show_form(
                step_id="custom",
                data_schema=vol.Schema({
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_USERNAME): str,
                }),
            )
        """,
            "homeassistant.components.test.config_flow",
            id="correct_method_custom",
        ),
        pytest.param(
            """
        async def async_common_step() -> FlowResult:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_USERNAME): str,
                }),
            )
        """,
            "homeassistant.components.test.config_flow",
            id="common_step_method",
        ),
        pytest.param(
            """
        async def async_common_step() -> FlowResult:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_USERNAME): str,
                }),
            )

        async def async_step_user() -> FlowResult:
            return await self.async_common_step()
        """,
            "homeassistant.components.test.config_flow",
            id="using_common_step_from_user",
        ),
        pytest.param(
            """
        async def async_common_step() -> FlowResult:
            return self.async_show_form(
                step_id=some_function(),
                data_schema=vol.Schema({
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_USERNAME): str,
                }),
            )
        """,
            "homeassistant.components.test.config_flow",
            id="using_a_function",
        ),
        pytest.param(
            """
        async def async_common_step() -> FlowResult:
            return self.async_show_form(
                step_id=await some_function(),
                data_schema=vol.Schema({
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_USERNAME): str,
                }),
            )
        """,
            "homeassistant.components.test.config_flow",
            id="using_an_async_function",
        ),
        pytest.param(
            """
                async def async_step_user() -> FlowResult:
                    return self.async_external_step(
                        step_id="user",
                        url="http://example.com"
                    )
                """,
            "homeassistant.components.test.config_flow",
            id="correct_method_external_step",
        ),
        pytest.param(
            """
                async def async_step_user() -> FlowResult:
                    return self.async_show_progress(
                        step_id="user",
                        progress_action="action",
                        progress_task=SomeTask()
                    )
                """,
            "homeassistant.components.test.config_flow",
            id="correct_method_show_progress",
        ),
        pytest.param(
            """
                async def async_step_user() -> FlowResult:
                    return self.async_show_menu(
                        step_id="user",
                        menu_options=["option1", "option2"]
                    )
                """,
            "homeassistant.components.test.config_flow",
            id="correct_method_show_menu",
        ),
        pytest.param(
            """
        async def async_step_user() -> FlowResult:
            return self.async_show_form(step_id="other")
        """,
            "homeassistant.components.test.sensor",
            id="not_config_flow_module",
        ),
        pytest.param(
            """
        async def async_step_user() -> FlowResult:
            return self.async_show_form(data_schema=vol.Schema({}))
        """,
            "homeassistant.components.test.config_flow",
            id="no_step_id",
        ),
        pytest.param(
            """
        async def async_step_user(**kwargs) -> FlowResult:
            return self.async_show_form(**kwargs)
        """,
            "homeassistant.components.test.config_flow",
            id="step_id_in_kwargs",
        ),
        pytest.param(
            """
        async def async_step_user() -> FlowResult:
            return self.async_show_form(step_id=None)
        """,
            "homeassistant.components.test.config_flow",
            id="step_id_none",
        ),
        pytest.param(
            """
        async def async_step_user(prefix: str) -> FlowResult:
            return self.async_show_form(step_id=f"{prefix}_other")
        """,
            "homeassistant.components.test.config_flow",
            id="step_id_fstring",
        ),
        pytest.param(
            """
        async def async_step_user() -> FlowResult:
            return self.async_abort(step_id="other", reason="reason")
        """,
            "homeassistant.components.test.config_flow",
            id="not_a_step_id_method",
        ),
        pytest.param(
            """
        async def async_step_user() -> FlowResult:
            return async_show_form(step_id="other")
        """,
            "homeassistant.components.test.config_flow",
            id="not_an_attribute_call",
        ),
        pytest.param(
            """
        def async_step_user() -> FlowResult:
            return self.async_show_form(step_id="other")
        """,
            "homeassistant.components.test.config_flow",
            id="sync_step_method",
        ),
        pytest.param(
            """
        class TestConfigFlow(ConfigFlow, domain=DOMAIN):
            async def async_step_user(
                self, user_input: dict[str, Any] | None = None
            ) -> ConfigFlowResult:
                return self.async_show_form(step_id="user")
        """,
            "homeassistant.components.test.config_flow",
            id="config_flow_class",
        ),
        pytest.param(
            """
        class TestOptionsFlow(OptionsFlow):
            async def async_step_init(
                self, user_input: dict[str, Any] | None = None
            ) -> ConfigFlowResult:
                return self.async_show_form(step_id="init")
        """,
            "homeassistant.components.test.config_flow",
            id="options_flow_class",
        ),
        pytest.param(
            """
        async def async_step_user() -> FlowResult:
            return self.async_show_form(step_id="user" if value else "user")
        """,
            "homeassistant.components.test.config_flow",
            id="duplicate_inferred_step_ids",
        ),
        pytest.param(
            """
        async def async_step_user() -> FlowResult:
            return self.async_show_form(step_id="user" if value else ["user"])
        """,
            "homeassistant.components.test.config_flow",
            id="unsupported_inferred_alternative",
        ),
        pytest.param(
            """
        async def async_step_user(value: Any) -> FlowResult:
            return self.async_show_form(step_id="user" if value else value.attr)
        """,
            "homeassistant.components.test.config_flow",
            id="uninferable_alternative",
        ),
    ],
)
def test_step_id_match_method(
    linter: UnittestLinter,
    step_id_match_method_checker: BaseChecker,
    code: str,
    module_name: str,
) -> None:
    """Good test cases."""
    root_node = astroid.parse(code, module_name)

    with assert_no_messages(linter):
        walk_checker(linter, step_id_match_method_checker, root_node)


@pytest.mark.parametrize(
    ("code", "module_name", "expected_args"),
    [
        pytest.param(
            """
        async def async_step_user() -> FlowResult:
            return self.async_show_form(
                step_id="reconfigure",
                data_schema=vol.Schema({
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_USERNAME): str,
                }),
            )
        """,
            "homeassistant.components.test.config_flow",
            ("reconfigure", "async_step_user"),
            id="incorrect_method_user",
        ),
        pytest.param(
            """
        async def async_step_reconfigure() -> FlowResult:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_USERNAME): str,
                }),
            )
        """,
            "homeassistant.components.test.config_flow",
            ("user", "async_step_reconfigure"),
            id="incorrect_method_reconfigure",
        ),
        pytest.param(
            """
        async def async_step_custom() -> FlowResult:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_USERNAME): str,
                }),
            )
        """,
            "homeassistant.components.test.config_flow",
            ("user", "async_step_custom"),
            id="incorrect_method_custom",
        ),
        pytest.param(
            """
        async def async_step_custom() -> FlowResult:
            return self.async_show_form(
                step_id="custom" if value is False else "user",
                data_schema=vol.Schema({
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_USERNAME): str,
                }),
            )
        """,
            "homeassistant.components.test.config_flow",
            ("custom, user", "async_step_custom"),
            id="incorrect_method_if_statement",
        ),
        pytest.param(
            """
                async def async_step_user() -> FlowResult:
                    return self.async_external_step(
                        step_id="other",
                        url="http://example.com"
                    )
                """,
            "homeassistant.components.test.config_flow",
            ("other", "async_step_user"),
            id="incorrect_method_external_step",
        ),
        pytest.param(
            """
                async def async_step_user() -> FlowResult:
                    return self.async_show_progress(
                        step_id="other",
                        progress_action="action",
                        progress_task=SomeTask()
                    )
                """,
            "homeassistant.components.test.config_flow",
            ("other", "async_step_user"),
            id="incorrect_method_show_progress",
        ),
        pytest.param(
            """
                async def async_step_user() -> FlowResult:
                    return self.async_show_menu(
                        step_id="other",
                        menu_options=["option1", "option2"]
                    )
                """,
            "homeassistant.components.test.config_flow",
            ("other", "async_step_user"),
            id="incorrect_method_show_menu",
        ),
        pytest.param(
            """
        async def async_step_user() -> FlowResult:
            step_id = "other"
            return self.async_show_form(step_id=step_id)
        """,
            "homeassistant.components.test.config_flow",
            ("other", "async_step_user"),
            id="incorrect_method_local_variable",
        ),
        pytest.param(
            """
        async def async_step_user() -> FlowResult:
            step_id = "user"
            if self.source == SOURCE_RECONFIGURE:
                step_id = "reconfigure"
            return self.async_show_form(step_id=step_id)
        """,
            "homeassistant.components.test.config_flow",
            ("user, reconfigure", "async_step_user"),
            id="incorrect_method_reassigned_variable",
        ),
        pytest.param(
            """
        STEP_ID = "other"

        async def async_step_user() -> FlowResult:
            return self.async_show_form(step_id=STEP_ID)
        """,
            "homeassistant.components.test.config_flow",
            ("other", "async_step_user"),
            id="incorrect_method_module_constant",
        ),
        pytest.param(
            """
        async def async_step_user() -> FlowResult:
            def _show_form() -> FlowResult:
                return self.async_show_form(step_id="other")

            return _show_form()
        """,
            "homeassistant.components.test.config_flow",
            ("other", "async_step_user"),
            id="incorrect_method_nested_function",
        ),
        pytest.param(
            """
        class TestConfigFlow(ConfigFlow, domain=DOMAIN):
            async def async_step_user(
                self, user_input: dict[str, Any] | None = None
            ) -> ConfigFlowResult:
                return self.async_show_form(step_id="other")
        """,
            "homeassistant.components.test.config_flow",
            ("other", "async_step_user"),
            id="incorrect_method_config_flow_class",
        ),
        pytest.param(
            """
        async def async_step_user() -> FlowResult:
            return self.async_show_form(step_id="other" if value else ["user"])
        """,
            "homeassistant.components.test.config_flow",
            ("other", "async_step_user"),
            id="incorrect_method_unsupported_alternative",
        ),
        pytest.param(
            """
        async def async_step_user(value: Any) -> FlowResult:
            return self.async_show_form(step_id="other" if value else value.attr)
        """,
            "homeassistant.components.test.config_flow",
            ("other", "async_step_user"),
            id="incorrect_method_uninferable_alternative",
        ),
        pytest.param(
            """
        async def async_step_custom() -> FlowResult:
            return self.async_show_form(
                step_id="user" if value else "user" if other else "custom"
            )
        """,
            "homeassistant.components.test.config_flow",
            ("user, custom", "async_step_custom"),
            id="incorrect_method_duplicate_alternatives",
        ),
    ],
)
def test_step_id_match_method_bad(
    linter: UnittestLinter,
    step_id_match_method_checker: BaseChecker,
    code: str,
    module_name: str,
    expected_args: tuple[str, str],
) -> None:
    """Bad test cases."""
    root_node = astroid.parse(code, module_name)
    call_node = _find_step_call_node(root_node)

    with assert_adds_messages(
        linter,
        MessageTest(
            msg_id="home-assistant-step_id-match-method",
            node=call_node,
            line=call_node.lineno,
            col_offset=call_node.col_offset,
            end_line=call_node.end_lineno,
            end_col_offset=call_node.end_col_offset,
            args=expected_args,
        ),
    ):
        walk_checker(linter, step_id_match_method_checker, root_node)

"""Tests for the flow call in try checker."""

import astroid
from astroid import nodes
from pylint.testutils import MessageTest, UnittestLinter
from pylint_home_assistant.checkers.config_flow.flow_call_in_try import (
    FlowCallInTryChecker,
)
import pytest

from tests.pylint import assert_adds_messages, assert_no_messages, walk_checker

# Pre-load so astroid can resolve the flow classes in parsed snippets
astroid.MANAGER.ast_from_module_name("homeassistant.config_entries")

_MODULE = "homeassistant.components.test_int.config_flow"


@pytest.fixture(name="checker")
def checker_fixture(linter: UnittestLinter) -> FlowCallInTryChecker:
    """Fixture to provide a flow call in try checker."""
    return FlowCallInTryChecker(linter)


def _expected_messages(root: nodes.Module, *names: str) -> list[MessageTest]:
    """Return the expected messages for the flow calls named *names*, in order."""
    calls = [
        next(
            call
            for call in root.nodes_of_class(nodes.Call)
            if isinstance(call.func, nodes.Attribute) and call.func.attrname == name
        )
        for name in names
    ]
    return [
        MessageTest(
            msg_id="home-assistant-flow-call-in-try",
            node=call,
            args=(call.func.attrname,),
            line=call.lineno,
            col_offset=call.col_offset,
            end_line=call.end_lineno,
            end_col_offset=call.end_col_offset,
        )
        for call in calls
    ]


@pytest.mark.parametrize(
    ("code", "module_name"),
    [
        pytest.param(
            """
from homeassistant.config_entries import ConfigFlow

class MyFlow(ConfigFlow, domain="test_int"):
    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                info = await validate(user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(info.serial_number)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info.title, data=user_input)
        return self.async_show_form(step_id="user", errors=errors)
""",
            _MODULE,
            id="else_block",
        ),
        pytest.param(
            """
from homeassistant.config_entries import ConfigFlow

class MyFlow(ConfigFlow, domain="test_int"):
    async def async_step_user(self, user_input=None):
        try:
            await self.async_set_unique_id(user_input["serial_number"])
            return self.async_create_entry(title="Test", data=user_input)
        finally:
            await close()
""",
            _MODULE,
            id="try_finally",
        ),
        pytest.param(
            """
from homeassistant.config_entries import ConfigFlow
from homeassistant.data_entry_flow import AbortFlow

class MyFlow(ConfigFlow, domain="test_int"):
    async def async_step_user(self, user_input=None):
        try:
            await self.async_set_unique_id(user_input["serial_number"])
            self._abort_if_unique_id_configured()
        except AbortFlow:
            await close()
            raise
        return self.async_create_entry(title="Test", data=user_input)
""",
            _MODULE,
            id="catches_abort_flow",
        ),
        pytest.param(
            """
from homeassistant.config_entries import ConfigFlow
from homeassistant.data_entry_flow import AbortFlow as FlowAbort

class MyFlow(ConfigFlow, domain="test_int"):
    async def async_step_user(self, user_input=None):
        try:
            await self.async_set_unique_id(user_input["serial_number"])
            self._abort_if_unique_id_configured()
        except FlowAbort:
            await close()
            raise
        return self.async_create_entry(title="Test", data=user_input)
""",
            _MODULE,
            id="catches_aliased_abort_flow",
        ),
        pytest.param(
            """
from homeassistant.config_entries import ConfigFlow
from homeassistant.data_entry_flow import AbortFlow

class MyFlow(ConfigFlow, domain="test_int"):
    async def async_step_user(self, user_input=None):
        try:
            await self.async_set_unique_id(user_input["serial_number"])
            self._abort_if_unique_id_configured()
        except (AbortFlow, CannotConnect):
            await close()
            raise
        return self.async_create_entry(title="Test", data=user_input)
""",
            _MODULE,
            id="catches_abort_flow_in_tuple",
        ),
        pytest.param(
            """
from homeassistant.config_entries import ConfigFlow

class MyFlow(ConfigFlow, domain="test_int"):
    async def async_step_user(self, user_input=None):
        try:
            client.register_callback(
                lambda: self.async_create_entry(title="Test", data={})
            )
        except CannotConnect:
            return self.async_abort(reason="cannot_connect")
        return self.async_show_form(step_id="user")
""",
            _MODULE,
            id="nested_lambda",
        ),
        pytest.param(
            """
class MyHelper:
    async def async_step_user(self, user_input=None):
        try:
            return self.async_create_entry(title="Test", data=user_input)
        except CannotConnect:
            return None
""",
            _MODULE,
            id="not_a_flow",
        ),
        pytest.param(
            """
from homeassistant.config_entries import ConfigFlow

class MyFlow(ConfigFlow, domain="test_int"):
    async def async_step_user(self, user_input=None):
        try:
            return self.async_create_entry(title="Test", data=user_input)
        except CannotConnect:
            return self.async_abort(reason="cannot_connect")
""",
            "homeassistant.helpers.my_helper",
            id="not_an_integration",
        ),
    ],
)
def test_no_warning(
    linter: UnittestLinter,
    checker: FlowCallInTryChecker,
    code: str,
    module_name: str,
) -> None:
    """Test cases that should not trigger a warning."""
    root = astroid.parse(code, module_name)

    with assert_no_messages(linter):
        walk_checker(linter, checker, root)


@pytest.mark.parametrize(
    ("code", "names"),
    [
        pytest.param(
            """
from homeassistant.config_entries import ConfigFlow

class MyFlow(ConfigFlow, domain="test_int"):
    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                info = await validate(user_input)
                await self.async_set_unique_id(info.serial_number)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info.title, data=user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
        return self.async_show_form(step_id="user", errors=errors)
""",
            (
                "async_set_unique_id",
                "_abort_if_unique_id_configured",
                "async_create_entry",
            ),
            id="config_flow",
        ),
        pytest.param(
            """
from homeassistant.config_entries import OptionsFlow

class MyOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input=None):
        try:
            await validate(user_input)
            if user_input is not None:
                return self.async_create_entry(data=user_input)
        except CannotConnect:
            return self.async_abort(reason="cannot_connect")
        return self.async_show_form(step_id="init")
""",
            ("async_create_entry",),
            id="options_flow",
        ),
        pytest.param(
            """
from homeassistant.config_entries import ConfigFlow

class MyFlow(ConfigFlow, domain="test_int"):
    async def async_step_reconfigure(self, user_input=None):
        try:
            async with client:
                await client.connect()
                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(), data_updates=user_input
                )
        except Exception:
            return self.async_abort(reason="unknown")
""",
            ("async_update_reload_and_abort",),
            id="nested_in_with_block",
        ),
        pytest.param(
            """
from homeassistant.config_entries import ConfigFlow

class MyFlow(ConfigFlow, domain="test_int"):
    async def async_step_user(self, user_input=None):
        try:
            try:
                await validate(user_input)
                self._async_abort_entries_match({"host": user_input["host"]})
            except InvalidAuth:
                return self.async_show_form(step_id="user")
        except CannotConnect:
            return self.async_abort(reason="cannot_connect")
        return self.async_create_entry(title="Test", data=user_input)
""",
            # The outer try statement is visited first
            ("async_show_form", "_async_abort_entries_match"),
            id="nested_try",
        ),
        pytest.param(
            """
from homeassistant.config_entries import ConfigFlow

class AbortFlow(Exception):
    pass

class MyFlow(ConfigFlow, domain="test_int"):
    async def async_step_user(self, user_input=None):
        try:
            await self.async_set_unique_id(user_input["serial_number"])
        except AbortFlow:
            return self.async_abort(reason="unknown")
        return self.async_create_entry(title="Test", data=user_input)
""",
            ("async_set_unique_id",),
            id="other_class_named_abort_flow",
        ),
        pytest.param(
            """
from homeassistant.config_entries import ConfigFlow
from homeassistant.data_entry_flow import AbortFlow

class MyFlow(ConfigFlow, domain="test_int"):
    async def async_step_user(self, user_input=None):
        try:
            try:
                await self.async_set_unique_id(user_input["serial_number"])
                self._abort_if_unique_id_configured()
            except AbortFlow:
                await close()
                raise
        except Exception:
            return self.async_abort(reason="unknown")
        return self.async_create_entry(title="Test", data=user_input)
""",
            ("async_set_unique_id", "_abort_if_unique_id_configured"),
            id="nested_try_reraises_abort_flow",
        ),
    ],
)
def test_flow_call_in_try(
    linter: UnittestLinter,
    checker: FlowCallInTryChecker,
    code: str,
    names: tuple[str, ...],
) -> None:
    """Test flow calls inside a try block with handlers are flagged."""
    root = astroid.parse(code, _MODULE)

    with assert_adds_messages(linter, *_expected_messages(root, *names)):
        walk_checker(linter, checker, root)

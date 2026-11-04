"""Tests for the init_first pylint checker."""

import astroid
from astroid import nodes
from pylint.testutils import MessageTest, UnittestLinter
from pylint_home_assistant.checkers.init_first import HassInitFirstChecker
import pytest

from . import assert_adds_messages, assert_no_messages, walk_checker

_MSG_ID = "home-assistant-init-not-first"


@pytest.fixture(name="checker")
def checker_fixture(linter: UnittestLinter) -> HassInitFirstChecker:
    """Fixture to provide the init_first checker."""
    return HassInitFirstChecker(linter)


def _find_init(root_node: nodes.Module) -> nodes.FunctionDef:
    """Return the first ``__init__`` in the module."""
    return next(
        func
        for func in root_node.nodes_of_class(nodes.FunctionDef)
        if func.name == "__init__"
    )


@pytest.mark.parametrize(
    ("code", "first_method"),
    [
        pytest.param(
            """
class MyEntity:
    _attr_has_entity_name = True

    @property
    def available(self) -> bool:
        return True

    def __init__(self) -> None:
        pass
""",
            "available",
            id="property_before_init",
        ),
        pytest.param(
            """
class MyEntity:
    def _helper(self) -> None:
        pass

    async def async_update(self) -> None:
        pass

    def __init__(self) -> None:
        pass
""",
            "_helper",
            id="methods_before_init",
        ),
        pytest.param(
            """
class MyEntity:
    @staticmethod
    def factory() -> None:
        pass

    async def async_update(self) -> None:
        pass

    def __init__(self) -> None:
        pass
""",
            "async_update",
            id="async_method_after_staticmethod_before_init",
        ),
    ],
)
def test_init_not_first(
    linter: UnittestLinter,
    checker: HassInitFirstChecker,
    code: str,
    first_method: str,
) -> None:
    """Test ``__init__`` defined after an instance method is flagged."""
    root_node = astroid.parse(code, "homeassistant.components.pylint_test.sensor")
    init_node = _find_init(root_node)
    with assert_adds_messages(
        linter,
        MessageTest(
            msg_id=_MSG_ID,
            node=init_node,
            line=init_node.lineno,
            col_offset=init_node.col_offset,
            end_line=init_node.position.end_lineno,
            end_col_offset=init_node.position.end_col_offset,
            args=("MyEntity", first_method),
        ),
    ):
        walk_checker(linter, checker, root_node)


@pytest.mark.parametrize(
    ("code", "module_name"),
    [
        pytest.param(
            """
class MyEntity:
    _attr_has_entity_name = True

    def __init__(self) -> None:
        pass

    @property
    def available(self) -> bool:
        return True
""",
            "homeassistant.components.pylint_test.sensor",
            id="init_first",
        ),
        pytest.param(
            """
class MyFlow:
    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry) -> None:
        pass

    @classmethod
    def from_config(cls) -> None:
        pass

    def __new__(cls) -> None:
        pass

    def __init_subclass__(cls) -> None:
        pass

    def __init__(self) -> None:
        pass
""",
            "homeassistant.components.pylint_test.config_flow",
            id="static_and_class_methods_before_init",
        ),
        pytest.param(
            """
class MyEntity:
    @property
    def available(self) -> bool:
        return True
""",
            "homeassistant.components.pylint_test.sensor",
            id="no_init",
        ),
        pytest.param(
            """
class MyEntity:
    @property
    def available(self) -> bool:
        return True

    def __init__(self) -> None:
        pass
""",
            "homeassistant.helpers.entity",
            id="not_integration_module",
        ),
        pytest.param(
            """
class Outer:
    def __init__(self) -> None:
        class Inner:
            def __init__(self) -> None:
                pass

    def method(self) -> None:
        pass
""",
            "homeassistant.components.pylint_test.sensor",
            id="nested_class",
        ),
    ],
)
def test_init_first(
    linter: UnittestLinter,
    checker: HassInitFirstChecker,
    code: str,
    module_name: str,
) -> None:
    """Test valid class layouts are not flagged."""
    root_node = astroid.parse(code, module_name)
    with assert_no_messages(linter):
        walk_checker(linter, checker, root_node)

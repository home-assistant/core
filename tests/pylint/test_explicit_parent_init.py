"""Tests for the explicit_parent_init pylint checker."""

import astroid
from astroid import nodes
from pylint.testutils import MessageTest, UnittestLinter
from pylint_home_assistant.checkers.explicit_parent_init import (
    ExplicitParentInitChecker,
)
import pytest

from . import assert_adds_messages, assert_no_messages, walk_checker

# Pre-load the entity module so astroid can resolve the base classes in
# the parsed snippets instead of depending on component-level imports.
astroid.MANAGER.ast_from_module_name("homeassistant.helpers.entity")

_MODULE = "homeassistant.components.pylint_test.sensor"

_BASES = """
from homeassistant.helpers.entity import Entity, ToggleEntity

class MyBaseEntity(Entity):
    def __init__(self, name: str) -> None:
        \"\"\"Initialize.\"\"\"
        self._attr_name = name

class MyImageLikeEntity(Entity):
    def __init__(self, url: str) -> None:
        \"\"\"Initialize, without calling super().__init__.\"\"\"
        self.url = url
"""


@pytest.fixture(name="checker")
def checker_fixture(linter: UnittestLinter) -> ExplicitParentInitChecker:
    """Fixture to provide the R7407 checker."""
    return ExplicitParentInitChecker(linter)


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            f"""
{_BASES}

class MySensor(MyBaseEntity):
    def __init__(self, name: str) -> None:
        \"\"\"Initialize.\"\"\"
        super().__init__(name)
            """,
            id="super_call",
        ),
        pytest.param(
            f"""
{_BASES}

class MyImage(MyBaseEntity, MyImageLikeEntity):
    def __init__(self, name: str, url: str) -> None:
        \"\"\"Initialize.\"\"\"
        MyBaseEntity.__init__(self, name)
        MyImageLikeEntity.__init__(self, url)
            """,
            id="several_explicit_calls",
        ),
        pytest.param(
            f"""
{_BASES}

class MyImage(MyBaseEntity, MyImageLikeEntity):
    def __init__(self, name: str, url: str) -> None:
        \"\"\"Initialize.\"\"\"
        super().__init__(name)
        MyImageLikeEntity.__init__(self, url)
            """,
            id="super_and_explicit_call",
        ),
        pytest.param(
            f"""
{_BASES}

class MyImage(MyBaseEntity, MyImageLikeEntity):
    def __init__(self, url: str) -> None:
        \"\"\"Initialize.\"\"\"
        MyImageLikeEntity.__init__(self, url)
            """,
            id="not_next_in_mro",
        ),
        pytest.param(
            f"""
{_BASES}
from not_installed_library import Device

class MyGenericEntity[_T](MyBaseEntity):
    \"\"\"Generic base astroid drops from the MRO for an uninferable argument.\"\"\"

class MyImage(MyGenericEntity[Device], MyImageLikeEntity):
    def __init__(self, url: str) -> None:
        \"\"\"Initialize.\"\"\"
        MyImageLikeEntity.__init__(self, url)
            """,
            id="unresolvable_mro",
        ),
        pytest.param(
            f"""
{_BASES}

class MySensor(MyBaseEntity):
    def __init__(self, other: MyBaseEntity, name: str) -> None:
        \"\"\"Initialize.\"\"\"
        MyBaseEntity.__init__(other, name)
            """,
            id="not_self",
        ),
        pytest.param(
            f"""
{_BASES}

class MySensor(MyBaseEntity):
    def __init__(self, name: str) -> None:
        \"\"\"Initialize.\"\"\"
        def _init() -> None:
            MyBaseEntity.__init__(self, name)
        _init()
            """,
            id="nested_function",
        ),
        pytest.param(
            f"""
{_BASES}

class MySensor(MyBaseEntity):
    def setup(self, name: str) -> None:
        \"\"\"Set up.\"\"\"
        MyBaseEntity.__init__(self, name)
            """,
            id="not_init",
        ),
        pytest.param(
            """
class MyBase:
    def __init__(self, name: str) -> None:
        \"\"\"Initialize.\"\"\"
        self.name = name

class NotAnEntity(MyBase):
    def __init__(self, name: str) -> None:
        \"\"\"Initialize.\"\"\"
        MyBase.__init__(self, name)
            """,
            id="not_an_entity",
        ),
    ],
)
def test_explicit_parent_init_good(
    linter: UnittestLinter,
    checker: ExplicitParentInitChecker,
    code: str,
) -> None:
    """Explicit calls that super() cannot replace are not flagged."""
    root_node = astroid.parse(code, _MODULE)

    with assert_no_messages(linter):
        walk_checker(linter, checker, root_node)


def test_explicit_parent_init_outside_integration(
    linter: UnittestLinter,
    checker: ExplicitParentInitChecker,
) -> None:
    """An explicit call outside an integration module is not flagged."""
    root_node = astroid.parse(
        f"""
{_BASES}

class MySensor(MyBaseEntity):
    def __init__(self, name: str) -> None:
        \"\"\"Initialize.\"\"\"
        MyBaseEntity.__init__(self, name)
        """,
        "tests.components.pylint_test.test_sensor",
    )

    with assert_no_messages(linter):
        walk_checker(linter, checker, root_node)


@pytest.mark.parametrize(
    ("code", "base_name"),
    [
        pytest.param(
            f"""
{_BASES}

class MySensor(MyBaseEntity):
    def __init__(self, name: str) -> None:
        \"\"\"Initialize.\"\"\"
        MyBaseEntity.__init__(self, name)
            """,
            "MyBaseEntity",
            id="single_base",
        ),
        pytest.param(
            f"""
{_BASES}

class MySwitch(MyBaseEntity, ToggleEntity):
    def __init__(self, name: str) -> None:
        \"\"\"Initialize.\"\"\"
        MyBaseEntity.__init__(self, name)
        self._attr_is_on = False
            """,
            "MyBaseEntity",
            id="platform_base_without_init",
        ),
        pytest.param(
            f"""
{_BASES}

class MySwitch(ToggleEntity, MyBaseEntity):
    def __init__(self, name: str) -> None:
        \"\"\"Initialize.\"\"\"
        MyBaseEntity.__init__(self, name)
            """,
            "MyBaseEntity",
            id="platform_base_first",
        ),
        pytest.param(
            f"""
{_BASES}

class MyMiddleEntity(MyBaseEntity):
    \"\"\"Base without a constructor of its own.\"\"\"

class MySensor(MyMiddleEntity):
    def __init__(self, name: str) -> None:
        \"\"\"Initialize.\"\"\"
        MyBaseEntity.__init__(self, name)
            """,
            "MyBaseEntity",
            id="grandparent_constructor",
        ),
        pytest.param(
            f"""
{_BASES}

class MyGenericEntity[_T](MyBaseEntity):
    def __init__(self, name: str, device: _T) -> None:
        \"\"\"Initialize.\"\"\"
        super().__init__(name)
        self.device = device

class MySwitch(MyGenericEntity[int], ToggleEntity):
    def __init__(self, name: str, device: int) -> None:
        \"\"\"Initialize.\"\"\"
        MyGenericEntity.__init__(self, name, device)
            """,
            "MyGenericEntity",
            id="pep695_generic_base",
        ),
    ],
)
def test_explicit_parent_init_bad(
    linter: UnittestLinter,
    checker: ExplicitParentInitChecker,
    code: str,
    base_name: str,
) -> None:
    """A lone explicit call super() resolves to is flagged."""
    root_node = astroid.parse(code, _MODULE)
    call = next(
        node
        for node in root_node.nodes_of_class(nodes.Call)
        if node.func.as_string() == f"{base_name}.__init__"
    )

    with assert_adds_messages(
        linter,
        MessageTest(
            msg_id="home-assistant-explicit-parent-init",
            node=call,
            line=call.lineno,
            args=(base_name,),
            col_offset=call.col_offset,
            end_line=call.end_lineno,
            end_col_offset=call.end_col_offset,
        ),
    ):
        walk_checker(linter, checker, root_node)

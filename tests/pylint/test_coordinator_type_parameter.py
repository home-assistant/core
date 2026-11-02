"""Tests for the coordinator type parameter checker."""

import astroid
from pylint.testutils import MessageTest, UnittestLinter
from pylint_home_assistant.checkers.coordinator_type_parameter import (
    CoordinatorTypeParameterChecker,
)
import pytest

from . import assert_adds_messages, assert_no_messages, walk_checker

# Pre-load so astroid can resolve the coordinator classes in parsed snippets
astroid.MANAGER.ast_from_module_name("homeassistant.helpers.update_coordinator")

_MODULE = "homeassistant.components.test_int.coordinator"


@pytest.fixture(name="checker")
def checker_fixture(linter: UnittestLinter) -> CoordinatorTypeParameterChecker:
    """Fixture to provide a coordinator type parameter checker."""
    return CoordinatorTypeParameterChecker(linter)


@pytest.mark.parametrize(
    ("code", "module_name"),
    [
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

class MyCoordinator(DataUpdateCoordinator[dict[str, int]]):
    pass
""",
            _MODULE,
            id="coordinator_with_type_parameter",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class MyEntity(CoordinatorEntity[MyCoordinator], Entity):
    pass
""",
            _MODULE,
            id="entity_with_type_parameter",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class MyEntity[_T: MyCoordinator](CoordinatorEntity[_T]):
    pass
""",
            _MODULE,
            id="generic_entity",
        ),
        pytest.param(
            """
class DataUpdateCoordinator:
    pass

class MyCoordinator(DataUpdateCoordinator):
    pass
""",
            _MODULE,
            id="other_class_with_the_same_name",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

class MyCoordinator(DataUpdateCoordinator):
    pass
""",
            "homeassistant.helpers.my_helper",
            id="not_an_integration",
        ),
    ],
)
def test_no_warning(
    linter: UnittestLinter,
    checker: CoordinatorTypeParameterChecker,
    code: str,
    module_name: str,
) -> None:
    """Test cases that should not trigger a warning."""
    root = astroid.parse(code, module_name)

    with assert_no_messages(linter):
        walk_checker(linter, checker, root)


@pytest.mark.parametrize(
    ("code", "expected_args"),
    [
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

class MyCoordinator(DataUpdateCoordinator):
    pass
""",
            ("the type of the coordinator data", "DataUpdateCoordinator"),
            id="coordinator",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import (
    TimestampDataUpdateCoordinator,
)

class MyCoordinator(TimestampDataUpdateCoordinator):
    pass
""",
            ("the type of the coordinator data", "TimestampDataUpdateCoordinator"),
            id="timestamp_coordinator",
        ),
        pytest.param(
            """
from homeassistant.helpers import update_coordinator

class MyCoordinator(update_coordinator.DataUpdateCoordinator):
    pass
""",
            ("the type of the coordinator data", "DataUpdateCoordinator"),
            id="coordinator_module_attribute",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class MyEntity(CoordinatorEntity, Entity):
    pass
""",
            ("the coordinator", "CoordinatorEntity"),
            id="entity",
        ),
    ],
)
def test_missing_type_parameter(
    linter: UnittestLinter,
    checker: CoordinatorTypeParameterChecker,
    code: str,
    expected_args: tuple[str, str],
) -> None:
    """Test a coordinator base class without a type parameter is flagged."""
    root = astroid.parse(code, _MODULE)
    base = root.body[-1].bases[0]

    with assert_adds_messages(
        linter,
        MessageTest(
            msg_id="home-assistant-coordinator-missing-type-parameter",
            node=base,
            args=expected_args,
            line=base.lineno,
            col_offset=base.col_offset,
            end_line=base.end_lineno,
            end_col_offset=base.end_col_offset,
        ),
    ):
        walk_checker(linter, checker, root)


def test_type_parameter_node(
    linter: UnittestLinter, checker: CoordinatorTypeParameterChecker
) -> None:
    """Test only the base class without a type parameter is flagged."""
    root = astroid.parse(
        """
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class MyEntity(Entity, CoordinatorEntity):
    pass
""",
        _MODULE,
    )
    base = root.body[-1].bases[1]

    with assert_adds_messages(
        linter,
        MessageTest(
            msg_id="home-assistant-coordinator-missing-type-parameter",
            node=base,
            args=("the coordinator", "CoordinatorEntity"),
            line=base.lineno,
            col_offset=base.col_offset,
            end_line=base.end_lineno,
            end_col_offset=base.end_col_offset,
        ),
    ):
        walk_checker(linter, checker, root)

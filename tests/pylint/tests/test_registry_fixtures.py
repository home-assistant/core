"""Tests for the registry fixtures checker."""

from pathlib import Path

import astroid
from astroid import nodes
from pylint.testutils import MessageTest, UnittestLinter
from pylint_home_assistant.checkers.tests.registry_fixtures import (
    RegistryFixturesChecker,
)
import pytest

from tests.pylint import assert_adds_messages, assert_no_messages, walk_checker


@pytest.fixture(name="registry_fixtures_checker")
def registry_fixtures_checker_fixture(
    linter: UnittestLinter,
) -> RegistryFixturesChecker:
    """Fixture to provide a registry fixtures checker."""
    return RegistryFixturesChecker(linter)


def _find_async_get_call(root_node: nodes.Module) -> nodes.Call:
    """Find the first ``<alias>.async_get(...)`` call node."""
    for call in root_node.nodes_of_class(nodes.Call):
        func = call.func
        if isinstance(func, nodes.Attribute) and func.attrname == "async_get":
            return call
    raise AssertionError("no async_get call found")


def _expect_registry_fixture(node: nodes.Call, helper: str) -> MessageTest:
    """Build the expected MessageTest for a registry fixture violation."""
    return MessageTest(
        msg_id="home-assistant-tests-registry-fixtures",
        node=node,
        args=(helper, helper),
        line=node.lineno,
        col_offset=node.col_offset,
        end_line=node.end_lineno,
        end_col_offset=node.end_col_offset,
    )


@pytest.mark.parametrize(
    ("helper", "alias"),
    [
        ("area_registry", "ar"),
        ("category_registry", "cr"),
        ("device_registry", "dr"),
        ("entity_registry", "er"),
        ("floor_registry", "fr"),
        ("issue_registry", "ir"),
        ("label_registry", "lr"),
    ],
)
def test_aliased_import_in_test_function_flagged(
    linter: UnittestLinter,
    registry_fixtures_checker: RegistryFixturesChecker,
    helper: str,
    alias: str,
) -> None:
    """Aliased registry import called inside a test function is flagged."""
    root_node = astroid.parse(
        f"""
from homeassistant.helpers import {helper} as {alias}


async def test_something(hass) -> None:
    registry = {alias}.async_get(hass)
""",
        "tests.components.test_integration.test_init",
    )
    call_node = _find_async_get_call(root_node)

    with assert_adds_messages(linter, _expect_registry_fixture(call_node, helper)):
        walk_checker(linter, registry_fixtures_checker, root_node)


@pytest.mark.parametrize(
    "helper",
    [
        "area_registry",
        "category_registry",
        "device_registry",
        "entity_registry",
        "floor_registry",
        "issue_registry",
        "label_registry",
    ],
)
def test_non_aliased_import_in_test_function_flagged(
    linter: UnittestLinter,
    registry_fixtures_checker: RegistryFixturesChecker,
    helper: str,
) -> None:
    """Non-aliased registry import called inside a test is flagged."""
    root_node = astroid.parse(
        f"""
from homeassistant.helpers import {helper}


async def test_something(hass) -> None:
    registry = {helper}.async_get(hass)
""",
        "tests.components.test_integration.test_init",
    )
    call_node = _find_async_get_call(root_node)

    with assert_adds_messages(linter, _expect_registry_fixture(call_node, helper)):
        walk_checker(linter, registry_fixtures_checker, root_node)


@pytest.mark.parametrize(
    "fixture_decorator",
    [
        "@pytest.fixture",
        "@pytest.fixture()",
        '@pytest.fixture(name="my_fixture")',
    ],
    ids=["bare", "call", "named"],
)
def test_pytest_fixture_flagged(
    linter: UnittestLinter,
    registry_fixtures_checker: RegistryFixturesChecker,
    fixture_decorator: str,
) -> None:
    """Calls inside a @pytest.fixture function are flagged."""
    root_node = astroid.parse(
        f"""
import pytest
from homeassistant.helpers import device_registry as dr


{fixture_decorator}
def my_helper(hass):
    return dr.async_get(hass)
""",
        "tests.components.test_integration.test_init",
    )
    call_node = _find_async_get_call(root_node)

    with assert_adds_messages(
        linter, _expect_registry_fixture(call_node, "device_registry")
    ):
        walk_checker(linter, registry_fixtures_checker, root_node)


@pytest.mark.parametrize(
    ("code", "module_name"),
    [
        pytest.param(
            """
from homeassistant.helpers import entity_registry as er


def helper(hass):
    return er.async_get(hass)
""",
            "tests.components.test_integration.test_init",
            id="non_test_non_fixture_helper",
        ),
        pytest.param(
            """
from homeassistant.helpers import entity_registry as er

registry = er.async_get(None)
""",
            "tests.components.test_integration.test_init",
            id="module_top_level",
        ),
        pytest.param(
            """
from homeassistant.helpers import entity_registry as er


async def test_something(hass) -> None:
    registry = er.async_get(hass)
""",
            "homeassistant.components.test_integration",
            id="not_a_test_module",
        ),
        pytest.param(
            """
from homeassistant.helpers import entity_registry as er


async def test_something(hass) -> None:
    registry = er.async_get(hass)
""",
            "tests.helpers.test_entity_registry",
            id="tests_helpers_excluded",
        ),
        pytest.param(
            """
from homeassistant.helpers import entity_registry as er


async def test_something(hass) -> None:
    something = other.async_get(hass)
""",
            "tests.components.test_integration.test_init",
            id="unrelated_attribute_target",
        ),
        pytest.param(
            """
from homeassistant.helpers import entity_registry as er


async def test_something(hass) -> None:
    entry = er.async_get_or_create(hass)
""",
            "tests.components.test_integration.test_init",
            id="different_method_name",
        ),
        pytest.param(
            """
async def test_something(hass) -> None:
    # No import of any registry helper at module scope.
    from homeassistant.helpers import entity_registry as er

    registry = er.async_get(hass)
""",
            "tests.components.test_integration.test_init",
            id="local_import_not_tracked",
        ),
    ],
)
def test_no_warning(
    linter: UnittestLinter,
    registry_fixtures_checker: RegistryFixturesChecker,
    code: str,
    module_name: str,
) -> None:
    """Cases that should not produce a warning."""
    root_node = astroid.parse(code, module_name)

    with assert_no_messages(linter):
        walk_checker(linter, registry_fixtures_checker, root_node)


def test_conftest_file_exempt(
    linter: UnittestLinter,
    registry_fixtures_checker: RegistryFixturesChecker,
    tmp_path: Path,
) -> None:
    """Calls inside ``conftest.py`` files are not flagged."""
    conftest_path = tmp_path / "conftest.py"
    conftest_path.write_text("")

    root_node = astroid.parse(
        """
import pytest
from homeassistant.helpers import entity_registry as er


@pytest.fixture
def entity_registry(hass):
    return er.async_get(hass)
""",
        "tests.components.test_integration.conftest",
    )
    root_node.file = str(conftest_path)

    with assert_no_messages(linter):
        walk_checker(linter, registry_fixtures_checker, root_node)

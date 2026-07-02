"""Tests for the registry fixtures checker."""

from pathlib import Path

import astroid
from pylint.testutils import UnittestLinter
from pylint.utils.ast_walker import ASTWalker
from pylint_home_assistant.checkers.tests.registry_fixtures import (
    RegistryFixturesChecker,
)
import pytest

from tests.pylint import assert_no_messages


@pytest.mark.parametrize(
    ("helper", "alias", "fixture_name"),
    [
        ("area_registry", "ar", "area_registry"),
        ("category_registry", "cr", "category_registry"),
        ("device_registry", "dr", "device_registry"),
        ("entity_registry", "er", "entity_registry"),
        ("floor_registry", "fr", "floor_registry"),
        ("issue_registry", "ir", "issue_registry"),
        ("label_registry", "lr", "label_registry"),
    ],
)
def test_aliased_import_in_test_function_flagged(
    linter: UnittestLinter,
    registry_fixtures_checker: RegistryFixturesChecker,
    helper: str,
    alias: str,
    fixture_name: str,
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
    walker = ASTWalker(linter)
    walker.add_checker(registry_fixtures_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "home-assistant-tests-registry-fixtures"
    assert messages[0].args == (fixture_name, helper)


def test_non_aliased_import_in_test_function_flagged(
    linter: UnittestLinter,
    registry_fixtures_checker: RegistryFixturesChecker,
) -> None:
    """Non-aliased registry import called inside a test is flagged."""
    root_node = astroid.parse(
        """
from homeassistant.helpers import entity_registry


async def test_something(hass) -> None:
    registry = entity_registry.async_get(hass)
""",
        "tests.components.test_integration.test_init",
    )
    walker = ASTWalker(linter)
    walker.add_checker(registry_fixtures_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].args == ("entity_registry", "entity_registry")


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
    walker = ASTWalker(linter)
    walker.add_checker(registry_fixtures_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].args == ("device_registry", "device_registry")


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
    walker = ASTWalker(linter)
    walker.add_checker(registry_fixtures_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


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

    walker = ASTWalker(linter)
    walker.add_checker(registry_fixtures_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)

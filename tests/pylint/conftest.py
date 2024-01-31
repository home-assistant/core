"""Configuration for pylint tests."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
from types import ModuleType

from pylint.checkers import BaseChecker
from pylint.testutils.unittest_linter import UnittestLinter
import pytest

BASE_PATH = Path(__file__).parents[2]


def _load_plugin_from_file(module_name: str, file: str) -> ModuleType:
    """Load plugin from file path."""
    spec = spec_from_file_location(
        module_name,
        str(BASE_PATH.joinpath(file)),
    )
    assert spec and spec.loader

    module = module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(name="hass_enforce_type_hints", scope="session")
def hass_enforce_type_hints_fixture() -> ModuleType:
    """Fixture to provide a requests mocker."""
    return _load_plugin_from_file(
        "hass_enforce_type_hints",
        "pylint/plugins/hass_enforce_type_hints.py",
    )


@pytest.fixture(name="linter")
def linter_fixture() -> UnittestLinter:
    """Fixture to provide a requests mocker."""
    return UnittestLinter()


@pytest.fixture(name="type_hint_checker")
def type_hint_checker_fixture(hass_enforce_type_hints, linter) -> BaseChecker:
    """Fixture to provide a requests mocker."""
    type_hint_checker = hass_enforce_type_hints.HassTypeHintChecker(linter)
    type_hint_checker.module = "homeassistant.components.pylint_test"
    return type_hint_checker


@pytest.fixture(name="hass_imports", scope="session")
def hass_imports_fixture() -> ModuleType:
    """Fixture to provide a requests mocker."""
    return _load_plugin_from_file(
        "hass_imports",
        "pylint/plugins/hass_imports.py",
    )


@pytest.fixture(name="imports_checker")
def imports_checker_fixture(hass_imports, linter) -> BaseChecker:
    """Fixture to provide a requests mocker."""
    type_hint_checker = hass_imports.HassImportsFormatChecker(linter)
    type_hint_checker.module = "homeassistant.components.pylint_test"
    return type_hint_checker


@pytest.fixture(name="hass_enforce_super_call", scope="session")
def hass_enforce_super_call_fixture() -> ModuleType:
    """Fixture to provide a requests mocker."""
    return _load_plugin_from_file(
        "hass_enforce_super_call",
        "pylint/plugins/hass_enforce_super_call.py",
    )


@pytest.fixture(name="super_call_checker")
def super_call_checker_fixture(hass_enforce_super_call, linter) -> BaseChecker:
    """Fixture to provide a requests mocker."""
    super_call_checker = hass_enforce_super_call.HassEnforceSuperCallChecker(linter)
    super_call_checker.module = "homeassistant.components.pylint_test"
    return super_call_checker


@pytest.fixture(name="hass_enforce_sorted_platforms", scope="session")
def hass_enforce_sorted_platforms_fixture() -> ModuleType:
    """Fixture to the content for the hass_enforce_sorted_platforms check."""
    return _load_plugin_from_file(
        "hass_enforce_sorted_platforms",
        "pylint/plugins/hass_enforce_sorted_platforms.py",
    )


@pytest.fixture(name="enforce_sorted_platforms_checker")
def enforce_sorted_platforms_checker_fixture(
    hass_enforce_sorted_platforms, linter
) -> BaseChecker:
    """Fixture to provide a hass_enforce_sorted_platforms checker."""
    enforce_sorted_platforms_checker = (
        hass_enforce_sorted_platforms.HassEnforceSortedPlatformsChecker(linter)
    )
    enforce_sorted_platforms_checker.module = "homeassistant.components.pylint_test"
    return enforce_sorted_platforms_checker


@pytest.fixture(name="hass_enforce_coordinator_module", scope="session")
def hass_enforce_coordinator_module_fixture() -> ModuleType:
    """Fixture to the content for the hass_enforce_coordinator_module check."""
    return _load_plugin_from_file(
        "hass_enforce_coordinator_module",
        "pylint/plugins/hass_enforce_coordinator_module.py",
    )


@pytest.fixture(name="enforce_coordinator_module_checker")
def enforce_coordinator_module_fixture(
    hass_enforce_coordinator_module, linter
) -> BaseChecker:
    """Fixture to provide a hass_enforce_coordinator_module checker."""
    enforce_coordinator_module_checker = (
        hass_enforce_coordinator_module.HassEnforceCoordinatorModule(linter)
    )
    enforce_coordinator_module_checker.module = "homeassistant.components.pylint_test"
    return enforce_coordinator_module_checker

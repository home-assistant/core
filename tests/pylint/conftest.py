"""Configuration for pylint tests."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
from types import ModuleType

from pylint.checkers import BaseChecker
from pylint.testutils.unittest_linter import UnittestLinter
import pytest

BASE_PATH = Path(__file__).parents[2]


@pytest.fixture(name="hass_enforce_type_hints", scope="session")
def hass_enforce_type_hints_fixture() -> ModuleType:
    """Fixture to provide a requests mocker."""
    module_name = "hass_enforce_type_hints"
    spec = spec_from_file_location(
        module_name,
        str(BASE_PATH.joinpath("pylint/plugins/hass_enforce_type_hints.py")),
    )
    assert spec and spec.loader

    module = module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


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
    module_name = "hass_imports"
    spec = spec_from_file_location(
        module_name, str(BASE_PATH.joinpath("pylint/plugins/hass_imports.py"))
    )
    assert spec and spec.loader

    module = module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(name="imports_checker")
def imports_checker_fixture(hass_imports, linter) -> BaseChecker:
    """Fixture to provide a requests mocker."""
    type_hint_checker = hass_imports.HassImportsFormatChecker(linter)
    type_hint_checker.module = "homeassistant.components.pylint_test"
    return type_hint_checker

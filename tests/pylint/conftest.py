"""Configuration for pylint tests."""
from importlib.machinery import SourceFileLoader
from pathlib import Path
from types import ModuleType

from pylint.checkers import BaseChecker
from pylint.testutils.unittest_linter import UnittestLinter
import pytest

BASE_PATH = Path(__file__).parents[2]


@pytest.fixture(name="hass_enforce_type_hints", scope="session")
def hass_enforce_type_hints_fixture() -> ModuleType:
    """Fixture to provide a requests mocker."""
    loader = SourceFileLoader(
        "hass_enforce_type_hints",
        str(BASE_PATH.joinpath("pylint/plugins/hass_enforce_type_hints.py")),
    )
    return loader.load_module(None)


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
    loader = SourceFileLoader(
        "hass_imports",
        str(BASE_PATH.joinpath("pylint/plugins/hass_imports.py")),
    )
    return loader.load_module(None)


@pytest.fixture(name="imports_checker")
def imports_checker_fixture(hass_imports, linter) -> BaseChecker:
    """Fixture to provide a requests mocker."""
    type_hint_checker = hass_imports.HassImportsFormatChecker(linter)
    type_hint_checker.module = "homeassistant.components.pylint_test"
    return type_hint_checker

"""Configuration for pylint tests."""
from importlib.machinery import SourceFileLoader
from types import ModuleType

from pylint.checkers import BaseChecker
from pylint.testutils.unittest_linter import UnittestLinter
import pytest


@pytest.fixture(name="hass_enforce_type_hints")
def hass_enforce_type_hints_fixture() -> ModuleType:
    """Fixture to provide a requests mocker."""
    loader = SourceFileLoader(
        "hass_enforce_type_hints", "pylint/plugins/hass_enforce_type_hints.py"
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

"""Configuration for pylint tests."""

from pylint.checkers import BaseChecker
from pylint.testutils.unittest_linter import UnittestLinter
from pylint_home_assistant.checkers.class_module import HassEnforceClassModule
from pylint_home_assistant.checkers.config_flow.no_name import (
    HassEnforceConfigFlowNoNameChecker,
)
from pylint_home_assistant.checkers.config_flow.no_polling import (
    HassEnforceConfigFlowNoPollingChecker,
)
from pylint_home_assistant.checkers.config_flow.unique_id_no_ip import (
    HassEnforceConfigEntryUniqueIdNoIpChecker,
)
from pylint_home_assistant.checkers.decorator import HassDecoratorChecker
from pylint_home_assistant.checkers.greek_micro_char import (
    HassEnforceGreekMicroCharChecker,
)
from pylint_home_assistant.checkers.imports import HassImportsFormatChecker
from pylint_home_assistant.checkers.runtime_data import HassEnforceRuntimeDataChecker
from pylint_home_assistant.checkers.sorted_platforms import (
    HassEnforceSortedPlatformsChecker,
)
from pylint_home_assistant.checkers.super_call import HassEnforceSuperCallChecker
from pylint_home_assistant.checkers.type_hints import HassTypeHintChecker
from pylint_home_assistant.checkers.utcnow import HassEnforceUtcnowChecker
from pylint_home_assistant.helpers.integration import clear_caches
import pytest


@pytest.fixture(name="linter")
def linter_fixture() -> UnittestLinter:
    """Fixture to provide a UnittestLinter."""
    return UnittestLinter()


@pytest.fixture(name="type_hint_checker")
def type_hint_checker_fixture(linter: UnittestLinter) -> BaseChecker:
    """Fixture to provide a type hint checker."""
    type_hint_checker = HassTypeHintChecker(linter)
    type_hint_checker.module = "homeassistant.components.pylint_test"
    return type_hint_checker


@pytest.fixture(name="imports_checker")
def imports_checker_fixture(linter: UnittestLinter) -> BaseChecker:
    """Fixture to provide an imports checker."""
    type_hint_checker = HassImportsFormatChecker(linter)
    type_hint_checker.module = "homeassistant.components.pylint_test"
    return type_hint_checker


@pytest.fixture(name="super_call_checker")
def super_call_checker_fixture(linter: UnittestLinter) -> BaseChecker:
    """Fixture to provide a super call checker."""
    super_call_checker = HassEnforceSuperCallChecker(linter)
    super_call_checker.module = "homeassistant.components.pylint_test"
    return super_call_checker


@pytest.fixture(name="enforce_sorted_platforms_checker")
def enforce_sorted_platforms_checker_fixture(linter: UnittestLinter) -> BaseChecker:
    """Fixture to provide a sorted platforms checker."""
    enforce_sorted_platforms_checker = HassEnforceSortedPlatformsChecker(linter)
    enforce_sorted_platforms_checker.module = "homeassistant.components.pylint_test"
    return enforce_sorted_platforms_checker


@pytest.fixture(name="enforce_class_module_checker")
def enforce_class_module_fixture(linter: UnittestLinter) -> BaseChecker:
    """Fixture to provide a class module checker."""
    enforce_class_module_checker = HassEnforceClassModule(linter)
    enforce_class_module_checker.module = "homeassistant.components.pylint_test"
    return enforce_class_module_checker


@pytest.fixture(name="decorator_checker")
def decorator_checker_fixture(linter: UnittestLinter) -> BaseChecker:
    """Fixture to provide a decorator checker."""
    type_hint_checker = HassDecoratorChecker(linter)
    type_hint_checker.module = "homeassistant.components.pylint_test"
    return type_hint_checker


@pytest.fixture(name="enforce_config_entry_unique_id_no_ip_checker")
def enforce_config_entry_unique_id_no_ip_checker_fixture(
    linter: UnittestLinter,
) -> BaseChecker:
    """Fixture to provide a unique_id_no_ip checker."""
    clear_caches()
    checker = HassEnforceConfigEntryUniqueIdNoIpChecker(linter)
    checker.module = "homeassistant.components.pylint_test"
    return checker


@pytest.fixture(name="enforce_config_flow_no_name_checker")
def enforce_config_flow_no_name_checker_fixture(
    linter: UnittestLinter,
) -> BaseChecker:
    """Fixture to provide a config_flow_no_name checker."""
    clear_caches()
    checker = HassEnforceConfigFlowNoNameChecker(linter)
    checker.module = "homeassistant.components.pylint_test"
    return checker


@pytest.fixture(name="enforce_config_flow_no_polling_checker")
def enforce_config_flow_no_polling_checker_fixture(
    linter: UnittestLinter,
) -> BaseChecker:
    """Fixture to provide a config_flow_no_polling checker."""
    checker = HassEnforceConfigFlowNoPollingChecker(linter)
    checker.module = "homeassistant.components.pylint_test"
    return checker


@pytest.fixture(name="enforce_runtime_data_checker")
def enforce_runtime_data_checker_fixture(linter: UnittestLinter) -> BaseChecker:
    """Fixture to provide a runtime_data checker."""
    clear_caches()
    enforce_runtime_data_checker = HassEnforceRuntimeDataChecker(linter)
    enforce_runtime_data_checker.module = "homeassistant.components.pylint_test"
    return enforce_runtime_data_checker


@pytest.fixture(name="enforce_greek_micro_char_checker")
def enforce_greek_micro_char_checker_fixture(linter: UnittestLinter) -> BaseChecker:
    """Fixture to provide a greek micro char checker."""
    enforce_greek_micro_char_checker = HassEnforceGreekMicroCharChecker(linter)
    enforce_greek_micro_char_checker.module = "homeassistant.components.pylint_test"
    return enforce_greek_micro_char_checker


@pytest.fixture(name="enforce_utcnow_checker")
def enforce_utcnow_checker_fixture(linter: UnittestLinter) -> BaseChecker:
    """Fixture to provide a utcnow checker."""
    enforce_utcnow_checker = HassEnforceUtcnowChecker(linter)
    enforce_utcnow_checker.module = "homeassistant.components.pylint_test"
    return enforce_utcnow_checker

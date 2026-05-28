"""Configuration for pylint tests checker tests."""

from pylint.testutils.unittest_linter import UnittestLinter
from pylint_home_assistant.checkers.tests.redundant_usefixtures import (
    RedundantUsefixtures,
)
from pylint_home_assistant.checkers.tests.registry_fixtures import (
    RegistryFixturesChecker,
)
import pytest


@pytest.fixture(name="usefixtures_checker")
def usefixtures_checker_fixture(linter: UnittestLinter) -> RedundantUsefixtures:
    """Fixture to provide a redundant usefixtures checker."""
    return RedundantUsefixtures(linter)


@pytest.fixture(name="registry_fixtures_checker")
def registry_fixtures_checker_fixture(
    linter: UnittestLinter,
) -> RegistryFixturesChecker:
    """Fixture to provide a registry fixtures checker."""
    return RegistryFixturesChecker(linter)

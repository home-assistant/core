"""Configuration for pylint tests checker tests."""

from pylint.testutils.unittest_linter import UnittestLinter
from pylint_home_assistant.checkers.tests.redundant_usefixtures import (
    RedundantUsefixtures,
)
import pytest


@pytest.fixture(name="usefixtures_checker")
def usefixtures_checker_fixture(linter: UnittestLinter) -> RedundantUsefixtures:
    """Fixture to provide a redundant usefixtures checker."""
    return RedundantUsefixtures(linter)

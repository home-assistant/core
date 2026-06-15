"""Tests for the duplicate const checker."""

import astroid
from pylint.testutils import UnittestLinter
from pylint.utils.ast_walker import ASTWalker
from pylint_home_assistant.checkers.duplicate_const import DuplicateConstChecker
import pytest

from . import assert_no_messages

# Pre-load homeassistant.const so astroid can resolve it.
astroid.MANAGER.ast_from_module_name("homeassistant.const")


@pytest.fixture(name="duplicate_const_checker")
def duplicate_const_checker_fixture(
    linter: UnittestLinter,
) -> DuplicateConstChecker:
    """Fixture to provide a duplicate const checker."""
    return DuplicateConstChecker(linter)


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
DOMAIN = "my_integration"
""",
            id="domain_same_value_different_semantics",
        ),
        pytest.param(
            """
MY_CUSTOM_CONST = "host"
""",
            id="different_name_same_value",
        ),
        pytest.param(
            """
CONF_HOST = "my_custom_host"
""",
            id="same_name_different_value",
        ),
        pytest.param(
            """
CONF_SPECIAL_SETTING = "special"
""",
            id="name_not_in_ha_const",
        ),
        pytest.param(
            """
from typing import Final

CONF_HOST: Final = "my_custom_host"
""",
            id="annotated_different_value",
        ),
    ],
)
def test_no_warning(
    linter: UnittestLinter,
    duplicate_const_checker: DuplicateConstChecker,
    code: str,
) -> None:
    """Test cases that should not trigger a warning."""
    root_node = astroid.parse(code, "homeassistant.components.test_integration.const")
    walker = ASTWalker(linter)
    walker.add_checker(duplicate_const_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


@pytest.mark.parametrize(
    ("name", "code"),
    [
        pytest.param(
            "CONF_HOST",
            """
CONF_HOST = "host"
""",
            id="conf_host",
        ),
        pytest.param(
            "CONF_PASSWORD",
            """
CONF_PASSWORD = "password"
""",
            id="conf_password",
        ),
        pytest.param(
            "ATTR_TEMPERATURE",
            """
ATTR_TEMPERATURE = "temperature"
""",
            id="attr_temperature",
        ),
        pytest.param(
            "CONF_HOST",
            """
from typing import Final

CONF_HOST: Final = "host"
""",
            id="annotated_final",
        ),
        pytest.param(
            "CONF_API_KEY",
            """
CONF_API_KEY: str = "api_key"
""",
            id="annotated_str",
        ),
    ],
)
def test_duplicate_const_flagged(
    linter: UnittestLinter,
    duplicate_const_checker: DuplicateConstChecker,
    name: str,
    code: str,
) -> None:
    """Test that duplicate constants are flagged."""
    root_node = astroid.parse(code, "homeassistant.components.test_integration.const")
    walker = ASTWalker(linter)
    walker.add_checker(duplicate_const_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "home-assistant-duplicate-const"
    assert messages[0].args == (name,)


def test_not_integration_ignored(
    linter: UnittestLinter,
    duplicate_const_checker: DuplicateConstChecker,
) -> None:
    """Test that non-integration modules are ignored."""
    root_node = astroid.parse(
        """
CONF_HOST = "host"
""",
        "tests.components.test_integration.test_const",
    )
    walker = ASTWalker(linter)
    walker.add_checker(duplicate_const_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)

"""Tests for the entity description defaults checker."""

import astroid
from pylint.testutils import UnittestLinter
from pylint.utils.ast_walker import ASTWalker
from pylint_home_assistant.checkers.entity_description_defaults import (
    EntityDescriptionDefaultsChecker,
)
import pytest

from . import assert_no_messages

# Pre-load EntityDescription so astroid can resolve it in parsed snippets.
# This avoids depending on component-level imports which may not be
# available in all CI test buckets.
_ENTITY_DESCRIPTION_MODULE = astroid.MANAGER.ast_from_module_name(
    "homeassistant.helpers.entity"
)

_IMPORT = "from homeassistant.helpers.entity import EntityDescription"


@pytest.fixture(name="defaults_checker")
def defaults_checker_fixture(
    linter: UnittestLinter,
) -> EntityDescriptionDefaultsChecker:
    """Fixture to provide an entity description defaults checker."""
    return EntityDescriptionDefaultsChecker(linter)


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            f"""
{_IMPORT}

EntityDescription(
    key="temperature",
)
""",
            id="no_defaults_set",
        ),
        pytest.param(
            f"""
{_IMPORT}

EntityDescription(
    key="signal",
    entity_registry_enabled_default=False,
)
""",
            id="non_default_value",
        ),
        pytest.param(
            f"""
{_IMPORT}

class MySensorDescription(EntityDescription):
    entity_category: str | None = "diagnostic"

MySensorDescription(
    key="departure",
    entity_category=None,
)
""",
            id="subclass_overrides_parent_default",
        ),
    ],
)
def test_no_warning(
    linter: UnittestLinter,
    defaults_checker: EntityDescriptionDefaultsChecker,
    code: str,
) -> None:
    """Test cases that should not trigger a warning."""
    root_node = astroid.parse(code, "homeassistant.components.test_integration.sensor")
    walker = ASTWalker(linter)
    walker.add_checker(defaults_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        pytest.param(
            "entity_registry_enabled_default",
            "True",
            f"""
{_IMPORT}

EntityDescription(
    key="temperature",
    entity_registry_enabled_default=True,
)
""",
            id="enabled_default_true",
        ),
        pytest.param(
            "device_class",
            "None",
            f"""
{_IMPORT}

EntityDescription(
    key="temperature",
    device_class=None,
)
""",
            id="device_class_none",
        ),
        pytest.param(
            "icon",
            "None",
            f"""
{_IMPORT}

EntityDescription(
    key="temperature",
    icon=None,
)
""",
            id="icon_none",
        ),
        pytest.param(
            "force_update",
            "False",
            f"""
{_IMPORT}

EntityDescription(
    key="temperature",
    force_update=False,
)
""",
            id="force_update_false",
        ),
        pytest.param(
            "translation_key",
            "None",
            f"""
{_IMPORT}

EntityDescription(
    key="temperature",
    translation_key=None,
)
""",
            id="translation_key_none",
        ),
    ],
)
def test_redundant_default_flagged(
    linter: UnittestLinter,
    defaults_checker: EntityDescriptionDefaultsChecker,
    field: str,
    value: str,
    code: str,
) -> None:
    """Test that redundant defaults are flagged."""
    root_node = astroid.parse(code, "homeassistant.components.test_integration.sensor")
    walker = ASTWalker(linter)
    walker.add_checker(defaults_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "home-assistant-entity-description-redundant-default"
    assert messages[0].args == (field, value)


def test_non_entity_description_ignored(
    linter: UnittestLinter,
    defaults_checker: EntityDescriptionDefaultsChecker,
) -> None:
    """Test that classes not inheriting EntityDescription are ignored."""
    root_node = astroid.parse(
        """
class JobDescription:
    icon: str | None = None

JobDescription(icon=None)
""",
        "homeassistant.components.test_integration.sensor",
    )
    walker = ASTWalker(linter)
    walker.add_checker(defaults_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


def test_local_entity_description_name_ignored(
    linter: UnittestLinter,
    defaults_checker: EntityDescriptionDefaultsChecker,
) -> None:
    """Test local EntityDescription class is not confused."""
    root_node = astroid.parse(
        """
class EntityDescription:
    entity_registry_enabled_default: bool = True

class MyDescription(EntityDescription):
    pass

MyDescription(entity_registry_enabled_default=True)
""",
        "homeassistant.components.test_integration.sensor",
    )
    walker = ASTWalker(linter)
    walker.add_checker(defaults_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


def test_aliased_description_flagged(
    linter: UnittestLinter,
    defaults_checker: EntityDescriptionDefaultsChecker,
) -> None:
    """Test that aliased EntityDescription constructors are still flagged."""
    root_node = astroid.parse(
        f"""
{_IMPORT}

Alias = EntityDescription
Alias(key="temperature", icon=None)
""",
        "homeassistant.components.test_integration.sensor",
    )
    walker = ASTWalker(linter)
    walker.add_checker(defaults_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "home-assistant-entity-description-redundant-default"
    assert messages[0].args == ("icon", "None")


def test_not_integration_ignored(
    linter: UnittestLinter,
    defaults_checker: EntityDescriptionDefaultsChecker,
) -> None:
    """Test that non-integration modules are ignored."""
    root_node = astroid.parse(
        f"""
{_IMPORT}

EntityDescription(
    key="temperature",
    entity_registry_enabled_default=True,
)
""",
        "tests.components.test_integration.test_sensor",
    )
    walker = ASTWalker(linter)
    walker.add_checker(defaults_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)

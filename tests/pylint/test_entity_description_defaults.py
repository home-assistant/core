"""Tests for the entity description defaults checker."""

import astroid
from pylint.testutils import UnittestLinter
from pylint.utils.ast_walker import ASTWalker
from pylint_home_assistant.checkers.entity_description_defaults import (
    EntityDescriptionDefaultsChecker,
)
import pytest

from . import assert_no_messages


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
            """
from homeassistant.components.sensor import SensorEntityDescription

SensorEntityDescription(
    key="temperature",
    device_class=SensorDeviceClass.TEMPERATURE,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
)
""",
            id="no_defaults_set",
        ),
        pytest.param(
            """
from homeassistant.components.sensor import SensorEntityDescription

SensorEntityDescription(
    key="signal",
    entity_registry_enabled_default=False,
)
""",
            id="non_default_value",
        ),
        pytest.param(
            """
from homeassistant.components.sensor import SensorEntityDescription

SensorEntityDescription(
    key="signal",
    entity_category=EntityCategory.DIAGNOSTIC,
)
""",
            id="non_default_category",
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
            """
from homeassistant.components.sensor import SensorEntityDescription

SensorEntityDescription(
    key="temperature",
    entity_registry_enabled_default=True,
)
""",
            id="enabled_default_true",
        ),
        pytest.param(
            "device_class",
            "None",
            """
from homeassistant.components.sensor import SensorEntityDescription

SensorEntityDescription(
    key="temperature",
    device_class=None,
)
""",
            id="device_class_none",
        ),
        pytest.param(
            "icon",
            "None",
            """
from homeassistant.components.sensor import SensorEntityDescription

SensorEntityDescription(
    key="temperature",
    icon=None,
)
""",
            id="icon_none",
        ),
        pytest.param(
            "force_update",
            "False",
            """
from homeassistant.components.sensor import SensorEntityDescription

SensorEntityDescription(
    key="temperature",
    force_update=False,
)
""",
            id="force_update_false",
        ),
        pytest.param(
            "state_class",
            "None",
            """
from homeassistant.components.sensor import SensorEntityDescription

SensorEntityDescription(
    key="temperature",
    state_class=None,
)
""",
            id="state_class_none",
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
    """Test that a local class named EntityDescription is not confused with the real one."""
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
        """
from homeassistant.components.sensor import SensorEntityDescription

Alias = SensorEntityDescription
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


def test_module_qualified_description_flagged(
    linter: UnittestLinter,
    defaults_checker: EntityDescriptionDefaultsChecker,
) -> None:
    """Test that module-qualified EntityDescription constructors are flagged."""
    root_node = astroid.parse(
        """
from homeassistant.components import sensor

sensor.SensorEntityDescription(
    key="temperature",
    icon=None,
)
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
        """
from homeassistant.components.sensor import SensorEntityDescription

SensorEntityDescription(
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

"""Tests for the has_entity_name quality scale checker."""

from pathlib import Path

import astroid
from astroid import nodes
from pylint.testutils import MessageTest, UnittestLinter
from pylint.utils.ast_walker import ASTWalker
from pylint_home_assistant.checkers.quality_scale.has_entity_name import (
    HasEntityNameChecker,
)
from pylint_home_assistant.helpers.quality_scale import clear_quality_scale_cache
import pytest
import yaml

from tests.pylint import assert_adds_messages, assert_no_messages


@pytest.fixture(name="has_entity_name_checker")
def has_entity_name_checker_fixture(
    linter: UnittestLinter,
) -> HasEntityNameChecker:
    """Fixture to provide a has-entity-name checker."""
    clear_quality_scale_cache()
    return HasEntityNameChecker(linter)


def _create_quality_scale(integration_dir: Path, rules: dict | None = None) -> None:
    """Create a quality_scale.yaml in the integration directory."""
    if rules is not None:
        (integration_dir / "quality_scale.yaml").write_text(yaml.dump({"rules": rules}))


def _make_integration(tmp_path: Path) -> Path:
    """Create a fake integration directory under components/."""
    integration_dir = tmp_path / "homeassistant" / "components" / "test_integration"
    integration_dir.mkdir(parents=True)
    return integration_dir


def _parse(
    code: str,
    integration_dir: Path,
    module_name: str = "homeassistant.components.test_integration.sensor",
    file_name: str = "sensor.py",
) -> nodes.Module:
    """Parse code as a module of the integration with .file set."""
    root_node = astroid.parse(code, module_name)
    root_node.file = str(integration_dir / file_name)
    return root_node


def _expect_missing(class_node: nodes.ClassDef) -> MessageTest:
    """Build the expected MessageTest for a flagged class.

    Pylint uses astroid's ``ClassDef.position`` (the class-name range, not
    the full body) for the end_line/end_col_offset of messages attached
    to a class node.
    """
    pos = class_node.position
    return MessageTest(
        msg_id="home-assistant-missing-has-entity-name",
        node=class_node,
        line=pos.lineno,
        col_offset=pos.col_offset,
        end_line=pos.end_lineno,
        end_col_offset=pos.end_col_offset,
        args=(class_node.name,),
    )


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MyEntity(Entity):
    _attr_has_entity_name = True
""",
            id="class_level_assign_true",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MyEntity(Entity):
    _attr_has_entity_name: bool = True
""",
            id="class_level_annassign_true",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MyEntity(Entity):
    def __init__(self):
        self._attr_has_entity_name = True
""",
            id="self_assign_true_in_init",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MyEntity(Entity):
    def __init__(self):
        self._attr_has_entity_name: bool = True
""",
            id="self_annassign_true_in_init",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MyEntity(Entity):
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_has_entity_name = True
""",
            id="self_assign_true_after_super_call",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MyEntity(Entity):
    def __init__(self, name):
        self._attr_name = name
        self._attr_has_entity_name = True
""",
            id="self_assign_true_after_other_assign",
        ),
    ],
)
def test_handled(
    linter: UnittestLinter,
    has_entity_name_checker: HasEntityNameChecker,
    tmp_path: Path,
    code: str,
) -> None:
    """No warning when the class handles _attr_has_entity_name."""
    integration_dir = _make_integration(tmp_path)
    _create_quality_scale(integration_dir, {"has-entity-name": "done"})

    root_node = _parse(code, integration_dir)
    walker = ASTWalker(linter)
    walker.add_checker(has_entity_name_checker)
    with assert_no_messages(linter):
        walker.walk(root_node)


def test_ancestor_class_level(
    linter: UnittestLinter,
    has_entity_name_checker: HasEntityNameChecker,
    tmp_path: Path,
) -> None:
    """Subclass passes when an ancestor sets it at class level."""
    integration_dir = _make_integration(tmp_path)
    _create_quality_scale(integration_dir, {"has-entity-name": "done"})

    astroid.parse(
        """
from homeassistant.helpers.entity import Entity

class TestIntegrationBaseEntity(Entity):
    _attr_has_entity_name = True
""",
        "homeassistant.components.test_integration.entity",
    )

    root_node = _parse(
        """
from homeassistant.components.test_integration.entity import TestIntegrationBaseEntity

class MySensor(TestIntegrationBaseEntity):
    pass
""",
        integration_dir,
    )

    walker = ASTWalker(linter)
    walker.add_checker(has_entity_name_checker)
    with assert_no_messages(linter):
        walker.walk(root_node)


def test_ancestor_self_assign(
    linter: UnittestLinter,
    has_entity_name_checker: HasEntityNameChecker,
    tmp_path: Path,
) -> None:
    """Subclass passes when an ancestor sets it via self in __init__."""
    integration_dir = _make_integration(tmp_path)
    _create_quality_scale(integration_dir, {"has-entity-name": "done"})

    astroid.parse(
        """
from homeassistant.helpers.entity import Entity

class TestIntegrationBaseEntity(Entity):
    def __init__(self):
        self._attr_has_entity_name = True
""",
        "homeassistant.components.test_integration.entity",
    )

    root_node = _parse(
        """
from homeassistant.components.test_integration.entity import TestIntegrationBaseEntity

class MySensor(TestIntegrationBaseEntity):
    pass
""",
        integration_dir,
    )

    walker = ASTWalker(linter)
    walker.add_checker(has_entity_name_checker)
    with assert_no_messages(linter):
        walker.walk(root_node)


def test_missing_fires(
    linter: UnittestLinter,
    has_entity_name_checker: HasEntityNameChecker,
    tmp_path: Path,
) -> None:
    """Warning when no _attr_has_entity_name is set anywhere."""
    integration_dir = _make_integration(tmp_path)
    _create_quality_scale(integration_dir, {"has-entity-name": "done"})

    root_node = _parse(
        """
from homeassistant.helpers.entity import Entity

class MySensor(Entity):
    pass
""",
        integration_dir,
    )

    class_node = next(root_node.nodes_of_class(nodes.ClassDef))
    walker = ASTWalker(linter)
    walker.add_checker(has_entity_name_checker)
    with assert_adds_messages(linter, _expect_missing(class_node)):
        walker.walk(root_node)


@pytest.mark.parametrize(
    ("code", "class_name"),
    [
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MyEntity(Entity):
    def __init__(self, has_name):
        self._attr_has_entity_name = has_name
""",
            "MyEntity",
            id="self_assign_non_constant",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MyEntity(Entity):
    def __init__(self, condition):
        if condition:
            self._attr_has_entity_name = True
""",
            "MyEntity",
            id="self_assign_true_inside_if",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MyEntity(Entity):
    def __init__(self):
        try:
            self._attr_has_entity_name = True
        except Exception:
            pass
""",
            "MyEntity",
            id="self_assign_true_inside_try",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MyEntity(Entity):
    def __init__(self, valid):
        if not valid:
            raise ValueError
        self._attr_has_entity_name = True
""",
            "MyEntity",
            id="self_assign_true_after_guard_raise",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MyEntity(Entity):
    def __init__(self, skip):
        if skip:
            return
        self._attr_has_entity_name = True
""",
            "MyEntity",
            id="self_assign_true_after_guard_return",
        ),
    ],
)
def test_conditional_self_assignment_fires(
    linter: UnittestLinter,
    has_entity_name_checker: HasEntityNameChecker,
    tmp_path: Path,
    code: str,
    class_name: str,
) -> None:
    """Non-literal or nested self assignments don't guarantee True."""
    integration_dir = _make_integration(tmp_path)
    _create_quality_scale(integration_dir, {"has-entity-name": "done"})

    root_node = _parse(code, integration_dir)
    class_node = next(
        cls
        for cls in root_node.nodes_of_class(nodes.ClassDef)
        if cls.name == class_name
    )
    walker = ASTWalker(linter)
    walker.add_checker(has_entity_name_checker)
    with assert_adds_messages(linter, _expect_missing(class_node)):
        walker.walk(root_node)


def test_explicit_false_fires(
    linter: UnittestLinter,
    has_entity_name_checker: HasEntityNameChecker,
    tmp_path: Path,
) -> None:
    """Warning when _attr_has_entity_name = False with no override."""
    integration_dir = _make_integration(tmp_path)
    _create_quality_scale(integration_dir, {"has-entity-name": "done"})

    root_node = _parse(
        """
from homeassistant.helpers.entity import Entity

class MySensor(Entity):
    _attr_has_entity_name = False
""",
        integration_dir,
    )

    class_node = next(root_node.nodes_of_class(nodes.ClassDef))
    walker = ASTWalker(linter)
    walker.add_checker(has_entity_name_checker)
    with assert_adds_messages(linter, _expect_missing(class_node)):
        walker.walk(root_node)


def test_generic_subscript_base_sets_flag(
    linter: UnittestLinter,
    has_entity_name_checker: HasEntityNameChecker,
    tmp_path: Path,
) -> None:
    """PEP-695-style generic base ``Base[T]`` is recognised as an ancestor."""
    integration_dir = _make_integration(tmp_path)
    _create_quality_scale(integration_dir, {"has-entity-name": "done"})

    astroid.parse(
        """
from homeassistant.helpers.entity import Entity

class TestIntegrationGenericBase[T](Entity):
    _attr_has_entity_name = True
""",
        "homeassistant.components.test_integration.entity",
    )

    root_node = _parse(
        """
from homeassistant.components.test_integration.entity import TestIntegrationGenericBase

class MySensor(TestIntegrationGenericBase[int]):
    pass
""",
        integration_dir,
    )

    walker = ASTWalker(linter)
    walker.add_checker(has_entity_name_checker)
    with assert_no_messages(linter):
        walker.walk(root_node)


def test_two_level_subscript_chain(
    linter: UnittestLinter,
    has_entity_name_checker: HasEntityNameChecker,
    tmp_path: Path,
) -> None:
    """Subscript-base resolution walks transitively through ancestors.

    Mirrors the vesync pattern: a non-subscript ancestor itself uses a
    subscript base for the class that sets the flag.
    """
    integration_dir = _make_integration(tmp_path)
    _create_quality_scale(integration_dir, {"has-entity-name": "done"})

    astroid.parse(
        """
from homeassistant.helpers.entity import Entity

class TestIntegrationBase[T](Entity):
    _attr_has_entity_name = True

class TestIntegrationLightBase(TestIntegrationBase[int]):
    _attr_name = None
""",
        "homeassistant.components.test_integration.entity",
    )

    root_node = _parse(
        """
from homeassistant.components.test_integration.entity import TestIntegrationLightBase

class MyLight(TestIntegrationLightBase):
    pass
""",
        integration_dir,
        module_name="homeassistant.components.test_integration.light",
        file_name="light.py",
    )

    walker = ASTWalker(linter)
    walker.add_checker(has_entity_name_checker)
    with assert_no_messages(linter):
        walker.walk(root_node)


def test_entity_description_fallback(
    linter: UnittestLinter,
    has_entity_name_checker: HasEntityNameChecker,
    tmp_path: Path,
) -> None:
    """Entity passes via EntityDescription.has_entity_name = True fallback."""
    integration_dir = _make_integration(tmp_path)
    _create_quality_scale(integration_dir, {"has-entity-name": "done"})

    root_node = _parse(
        """
from dataclasses import dataclass

from homeassistant.helpers.entity import Entity, EntityDescription


@dataclass(frozen=True, kw_only=True)
class TestIntegrationDescription(EntityDescription):
    has_entity_name = True


class MyEntity(Entity):
    entity_description: TestIntegrationDescription
""",
        integration_dir,
    )

    walker = ASTWalker(linter)
    walker.add_checker(has_entity_name_checker)
    with assert_no_messages(linter):
        walker.walk(root_node)


def test_entity_description_subscripted_annotation(
    linter: UnittestLinter,
    has_entity_name_checker: HasEntityNameChecker,
    tmp_path: Path,
) -> None:
    """``entity_description: Desc[T]`` annotation still resolves."""
    integration_dir = _make_integration(tmp_path)
    _create_quality_scale(integration_dir, {"has-entity-name": "done"})

    root_node = _parse(
        """
from dataclasses import dataclass

from homeassistant.helpers.entity import Entity, EntityDescription


@dataclass(frozen=True, kw_only=True)
class TestIntegrationDescription[T](EntityDescription):
    has_entity_name = True


class MyEntity[T](Entity):
    entity_description: TestIntegrationDescription[T]
""",
        integration_dir,
    )

    walker = ASTWalker(linter)
    walker.add_checker(has_entity_name_checker)
    with assert_no_messages(linter):
        walker.walk(root_node)


def test_entity_description_without_flag_still_fires(
    linter: UnittestLinter,
    has_entity_name_checker: HasEntityNameChecker,
    tmp_path: Path,
) -> None:
    """Description annotation that doesn't set has_entity_name doesn't satisfy."""
    integration_dir = _make_integration(tmp_path)
    _create_quality_scale(integration_dir, {"has-entity-name": "done"})

    root_node = _parse(
        """
from dataclasses import dataclass

from homeassistant.helpers.entity import Entity, EntityDescription


@dataclass(frozen=True, kw_only=True)
class TestIntegrationDescription(EntityDescription):
    pass


class MyEntity(Entity):
    entity_description: TestIntegrationDescription
""",
        integration_dir,
    )

    class_node = next(
        cls
        for cls in root_node.nodes_of_class(nodes.ClassDef)
        if cls.name == "MyEntity"
    )
    walker = ASTWalker(linter)
    walker.add_checker(has_entity_name_checker)
    with assert_adds_messages(linter, _expect_missing(class_node)):
        walker.walk(root_node)


def test_entity_description_set_in_ancestor(
    linter: UnittestLinter,
    has_entity_name_checker: HasEntityNameChecker,
    tmp_path: Path,
) -> None:
    """Annotation on an ancestor counts for subclass."""
    integration_dir = _make_integration(tmp_path)
    _create_quality_scale(integration_dir, {"has-entity-name": "done"})

    astroid.parse(
        """
from dataclasses import dataclass

from homeassistant.helpers.entity import Entity, EntityDescription


@dataclass(frozen=True, kw_only=True)
class TestIntegrationDescription(EntityDescription):
    has_entity_name = True


class TestIntegrationBaseEntity(Entity):
    entity_description: TestIntegrationDescription
""",
        "homeassistant.components.test_integration.entity",
    )

    root_node = _parse(
        """
from homeassistant.components.test_integration.entity import TestIntegrationBaseEntity

class MySensor(TestIntegrationBaseEntity):
    pass
""",
        integration_dir,
    )

    walker = ASTWalker(linter)
    walker.add_checker(has_entity_name_checker)
    with assert_no_messages(linter):
        walker.walk(root_node)


def test_mixin_subclassed_in_same_module_ignored(
    linter: UnittestLinter,
    has_entity_name_checker: HasEntityNameChecker,
    tmp_path: Path,
) -> None:
    """Mixin base class is skipped if another class in the same module extends it."""
    integration_dir = _make_integration(tmp_path)
    _create_quality_scale(integration_dir, {"has-entity-name": "done"})

    root_node = _parse(
        """
from homeassistant.helpers.entity import Entity

class MyClimateMixin(Entity):
    _attr_temperature_unit = "C"

class ActualEntity(MyClimateMixin):
    _attr_has_entity_name = True
""",
        integration_dir,
    )

    walker = ASTWalker(linter)
    walker.add_checker(has_entity_name_checker)
    with assert_no_messages(linter):
        walker.walk(root_node)


def test_subclassed_via_subscript_ignored(
    linter: UnittestLinter,
    has_entity_name_checker: HasEntityNameChecker,
    tmp_path: Path,
) -> None:
    """Generic base referenced as ``Base[T]`` in subclass declaration is recognised."""
    integration_dir = _make_integration(tmp_path)
    _create_quality_scale(integration_dir, {"has-entity-name": "done"})

    root_node = _parse(
        """
from homeassistant.helpers.entity import Entity

class GenericBase[T](Entity):
    pass

class ConcreteEntity(GenericBase[int]):
    _attr_has_entity_name = True
""",
        integration_dir,
    )

    walker = ASTWalker(linter)
    walker.add_checker(has_entity_name_checker)
    with assert_no_messages(linter):
        walker.walk(root_node)


def test_leaf_class_still_fires(
    linter: UnittestLinter,
    has_entity_name_checker: HasEntityNameChecker,
    tmp_path: Path,
) -> None:
    """A class that other module classes don't extend is still flagged."""
    integration_dir = _make_integration(tmp_path)
    _create_quality_scale(integration_dir, {"has-entity-name": "done"})

    root_node = _parse(
        """
from homeassistant.helpers.entity import Entity

class LonelySensor(Entity):
    pass

class SomethingUnrelated:
    pass
""",
        integration_dir,
    )

    class_node = next(
        cls
        for cls in root_node.nodes_of_class(nodes.ClassDef)
        if cls.name == "LonelySensor"
    )
    walker = ASTWalker(linter)
    walker.add_checker(has_entity_name_checker)
    with assert_adds_messages(linter, _expect_missing(class_node)):
        walker.walk(root_node)


def test_non_entity_class_ignored(
    linter: UnittestLinter,
    has_entity_name_checker: HasEntityNameChecker,
    tmp_path: Path,
) -> None:
    """Class that does not inherit from Entity is ignored."""
    integration_dir = _make_integration(tmp_path)
    _create_quality_scale(integration_dir, {"has-entity-name": "done"})

    root_node = _parse(
        """
class NotAnEntity:
    pass
""",
        integration_dir,
    )

    walker = ASTWalker(linter)
    walker.add_checker(has_entity_name_checker)
    with assert_no_messages(linter):
        walker.walk(root_node)


def test_dict_status_done_fires(
    linter: UnittestLinter,
    has_entity_name_checker: HasEntityNameChecker,
    tmp_path: Path,
) -> None:
    """Dict-form {status: done} also gates."""
    integration_dir = _make_integration(tmp_path)
    _create_quality_scale(
        integration_dir,
        {"has-entity-name": {"status": "done", "comment": "ok"}},
    )

    root_node = _parse(
        """
from homeassistant.helpers.entity import Entity

class MySensor(Entity):
    pass
""",
        integration_dir,
    )

    class_node = next(root_node.nodes_of_class(nodes.ClassDef))
    walker = ASTWalker(linter)
    walker.add_checker(has_entity_name_checker)
    with assert_adds_messages(linter, _expect_missing(class_node)):
        walker.walk(root_node)


@pytest.mark.parametrize(
    ("module_name", "file_name", "rules"),
    [
        pytest.param(
            "homeassistant.components.test_integration.sensor",
            "sensor.py",
            None,
            id="no_quality_scale_file",
        ),
        pytest.param(
            "homeassistant.components.test_integration.sensor",
            "sensor.py",
            {"has-entity-name": "todo"},
            id="rule_todo",
        ),
        pytest.param(
            "homeassistant.components.test_integration.sensor",
            "sensor.py",
            {"has-entity-name": {"status": "exempt", "comment": "reason"}},
            id="rule_exempt",
        ),
        pytest.param(
            "homeassistant.components.test_integration.sensor",
            "sensor.py",
            {"some-other-rule": "done"},
            id="rule_absent",
        ),
        pytest.param(
            "homeassistant.components.test_integration.entity",
            "entity.py",
            {"has-entity-name": "done"},
            id="non_platform_module",
        ),
        pytest.param(
            "homeassistant.components.test_integration",
            "__init__.py",
            {"has-entity-name": "done"},
            id="init_module",
        ),
        pytest.param(
            "not_homeassistant.something.sensor",
            "sensor.py",
            {"has-entity-name": "done"},
            id="not_an_integration",
        ),
    ],
)
def test_not_fired(
    linter: UnittestLinter,
    has_entity_name_checker: HasEntityNameChecker,
    tmp_path: Path,
    module_name: str,
    file_name: str,
    rules: dict | None,
) -> None:
    """No warning when rule is not done, module is not a platform, etc."""
    integration_dir = _make_integration(tmp_path)
    _create_quality_scale(integration_dir, rules)

    code = """
from homeassistant.helpers.entity import Entity

class MySensor(Entity):
    pass
"""
    root_node = _parse(code, integration_dir, module_name, file_name)

    walker = ASTWalker(linter)
    walker.add_checker(has_entity_name_checker)
    with assert_no_messages(linter):
        walker.walk(root_node)

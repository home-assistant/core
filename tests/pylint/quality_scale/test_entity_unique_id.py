"""Tests for the entity_unique_id quality scale checker."""

import json
from pathlib import Path

import astroid
from astroid import nodes
from pylint.testutils import MessageTest, UnittestLinter
from pylint.utils.ast_walker import ASTWalker
from pylint_home_assistant.checkers.quality_scale.entity_unique_id import (
    EntityUniqueIdChecker,
)
from pylint_home_assistant.helpers.integration import clear_caches
from pylint_home_assistant.helpers.quality_scale import clear_quality_scale_cache
import pytest
import yaml

from tests.pylint import assert_adds_messages, assert_no_messages


@pytest.fixture(name="entity_unique_id_checker")
def entity_unique_id_checker_fixture(
    linter: UnittestLinter,
) -> EntityUniqueIdChecker:
    """Fixture to provide an entity-unique-id checker."""
    clear_quality_scale_cache()
    clear_caches()
    return EntityUniqueIdChecker(linter)


def _create_quality_scale(integration_dir: Path, rules: dict | None = None) -> None:
    """Create a quality_scale.yaml in the integration directory."""
    if rules is not None:
        (integration_dir / "quality_scale.yaml").write_text(yaml.dump({"rules": rules}))


def _create_manifest(integration_dir: Path, *, single_config_entry: bool) -> None:
    """Create a minimal manifest.json in the integration directory."""
    (integration_dir / "manifest.json").write_text(
        json.dumps(
            {"domain": "test_integration", "single_config_entry": single_config_entry}
        )
    )


def _make_integration(tmp_path: Path, *, single_config_entry: bool = True) -> Path:
    """Create a fake integration directory under components/.

    Writes a manifest with ``single_config_entry`` defaulting to ``True``
    so tests that use class-body string-literal unique_ids don't trip
    ``home-assistant-entity-unique-id-static`` by accident. Tests that
    exercise W7424 pass ``single_config_entry=False`` explicitly.
    """
    integration_dir = tmp_path / "homeassistant" / "components" / "test_integration"
    integration_dir.mkdir(parents=True)
    _create_manifest(integration_dir, single_config_entry=single_config_entry)
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
    """Build the expected MessageTest for a flagged class."""
    pos = class_node.position
    return MessageTest(
        msg_id="home-assistant-missing-entity-unique-id",
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
    _attr_unique_id = "fixed_id"
""",
            id="class_level_assign_string",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MyEntity(Entity):
    _attr_unique_id: str = "fixed_id"
""",
            id="class_level_annassign_string",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MyEntity(Entity):
    def __init__(self, key):
        self._attr_unique_id = key
""",
            id="self_assign_name_in_init",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MyEntity(Entity):
    def __init__(self, key):
        self._attr_unique_id = f"prefix_{key}"
""",
            id="self_assign_fstring_in_init",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MyEntity(Entity):
    def __init__(self, key):
        self._attr_unique_id: str = key
""",
            id="self_annassign_in_init",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MyEntity(Entity):
    def __init__(self, coordinator, key):
        super().__init__(coordinator)
        self._attr_unique_id = key
""",
            id="self_assign_after_super_call",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MyEntity(Entity):
    def __init__(self, name, key):
        self._attr_name = name
        self._attr_unique_id = key
""",
            id="self_assign_after_other_assign",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MyEntity(Entity):
    def __init__(self, segment, key):
        if segment == 0:
            self._attr_name = None
        else:
            self._attr_translation_placeholders = {"s": str(segment)}
        self._attr_unique_id = key
""",
            id="self_assign_after_non_terminating_if_else",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MyEntity(Entity):
    def __init__(self, channel, key):
        if channel.is_sub_device():
            self._attr_device_info["via_device"] = ("dom", channel.id)
        self._attr_unique_id = key
""",
            id="self_assign_after_non_terminating_if_no_else",
        ),
        pytest.param(
            """
from typing import TYPE_CHECKING
from homeassistant.helpers.entity import Entity

class MyEntity(Entity):
    def __init__(self, entry, description):
        if TYPE_CHECKING:
            assert entry.unique_id
        self._attr_unique_id = f"{entry.unique_id}_{description.key}"
""",
            id="self_assign_after_type_checking_guard",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MyEntity(Entity):
    def __init__(self, description):
        if description is None:
            self._attr_unique_id = self.device.mac
            self._attr_name = None
        else:
            self.entity_description = description
            self._attr_unique_id = f"{self.device.mac}_{description.key}"
""",
            id="self_assign_in_both_branches_of_if_else",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MyEntity(Entity):
    @property
    def unique_id(self) -> str:
        return "x"
""",
            id="unique_id_property_override",
        ),
        pytest.param(
            """
from functools import cached_property
from homeassistant.helpers.entity import Entity

class MyEntity(Entity):
    @cached_property
    def unique_id(self) -> str:
        return "x"
""",
            id="unique_id_cached_property_override",
        ),
    ],
)
def test_handled(
    linter: UnittestLinter,
    entity_unique_id_checker: EntityUniqueIdChecker,
    tmp_path: Path,
    code: str,
) -> None:
    """No warning when the class handles _attr_unique_id / unique_id."""
    integration_dir = _make_integration(tmp_path)
    _create_quality_scale(integration_dir, {"entity-unique-id": "done"})

    root_node = _parse(code, integration_dir)
    walker = ASTWalker(linter)
    walker.add_checker(entity_unique_id_checker)
    with assert_no_messages(linter):
        walker.walk(root_node)


def test_ancestor_class_level(
    linter: UnittestLinter,
    entity_unique_id_checker: EntityUniqueIdChecker,
    tmp_path: Path,
) -> None:
    """Subclass passes when an ancestor sets _attr_unique_id at class level."""
    integration_dir = _make_integration(tmp_path)
    _create_quality_scale(integration_dir, {"entity-unique-id": "done"})

    astroid.parse(
        """
from homeassistant.helpers.entity import Entity

class TestIntegrationBaseEntity(Entity):
    _attr_unique_id = "fixed_id"
""",
        "homeassistant.components.test_integration.eui_entity",
    )

    root_node = _parse(
        """
from homeassistant.components.test_integration.eui_entity import TestIntegrationBaseEntity

class MySensor(TestIntegrationBaseEntity):
    pass
""",
        integration_dir,
    )

    walker = ASTWalker(linter)
    walker.add_checker(entity_unique_id_checker)
    with assert_no_messages(linter):
        walker.walk(root_node)


def test_ancestor_self_assign(
    linter: UnittestLinter,
    entity_unique_id_checker: EntityUniqueIdChecker,
    tmp_path: Path,
) -> None:
    """Subclass passes when an ancestor sets _attr_unique_id via self in __init__."""
    integration_dir = _make_integration(tmp_path)
    _create_quality_scale(integration_dir, {"entity-unique-id": "done"})

    astroid.parse(
        """
from homeassistant.helpers.entity import Entity

class TestIntegrationBaseEntity(Entity):
    def __init__(self, key):
        self._attr_unique_id = key
""",
        "homeassistant.components.test_integration.eui_entity",
    )

    root_node = _parse(
        """
from homeassistant.components.test_integration.eui_entity import TestIntegrationBaseEntity

class MySensor(TestIntegrationBaseEntity):
    pass
""",
        integration_dir,
    )

    walker = ASTWalker(linter)
    walker.add_checker(entity_unique_id_checker)
    with assert_no_messages(linter):
        walker.walk(root_node)


def test_ancestor_property(
    linter: UnittestLinter,
    entity_unique_id_checker: EntityUniqueIdChecker,
    tmp_path: Path,
) -> None:
    """Subclass passes when an ancestor defines a unique_id property override."""
    integration_dir = _make_integration(tmp_path)
    _create_quality_scale(integration_dir, {"entity-unique-id": "done"})

    astroid.parse(
        """
from homeassistant.helpers.entity import Entity

class TestIntegrationBaseEntity(Entity):
    @property
    def unique_id(self) -> str:
        return self._device.id
""",
        "homeassistant.components.test_integration.eui_entity",
    )

    root_node = _parse(
        """
from homeassistant.components.test_integration.eui_entity import TestIntegrationBaseEntity

class MySensor(TestIntegrationBaseEntity):
    pass
""",
        integration_dir,
    )

    walker = ASTWalker(linter)
    walker.add_checker(entity_unique_id_checker)
    with assert_no_messages(linter):
        walker.walk(root_node)


def test_missing_fires(
    linter: UnittestLinter,
    entity_unique_id_checker: EntityUniqueIdChecker,
    tmp_path: Path,
) -> None:
    """Warning when no unique_id is set anywhere."""
    integration_dir = _make_integration(tmp_path)
    _create_quality_scale(integration_dir, {"entity-unique-id": "done"})

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
    walker.add_checker(entity_unique_id_checker)
    with assert_adds_messages(linter, _expect_missing(class_node)):
        walker.walk(root_node)


@pytest.mark.parametrize(
    ("code", "class_name"),
    [
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MyEntity(Entity):
    def __init__(self, condition, key):
        if condition:
            self._attr_unique_id = key
""",
            "MyEntity",
            id="self_assign_inside_if",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MyEntity(Entity):
    def __init__(self, key):
        try:
            self._attr_unique_id = key
        except Exception:
            pass
""",
            "MyEntity",
            id="self_assign_inside_try",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MyEntity(Entity):
    def __init__(self, valid, key):
        if not valid:
            raise ValueError
        self._attr_unique_id = key
""",
            "MyEntity",
            id="self_assign_after_guard_raise",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MyEntity(Entity):
    def __init__(self, skip, key):
        if skip:
            return
        self._attr_unique_id = key
""",
            "MyEntity",
            id="self_assign_after_guard_return",
        ),
    ],
)
def test_conditional_self_assignment_fires(
    linter: UnittestLinter,
    entity_unique_id_checker: EntityUniqueIdChecker,
    tmp_path: Path,
    code: str,
    class_name: str,
) -> None:
    """Nested self assignments don't guarantee a non-None id."""
    integration_dir = _make_integration(tmp_path)
    _create_quality_scale(integration_dir, {"entity-unique-id": "done"})

    root_node = _parse(code, integration_dir)
    class_node = next(
        cls
        for cls in root_node.nodes_of_class(nodes.ClassDef)
        if cls.name == class_name
    )
    walker = ASTWalker(linter)
    walker.add_checker(entity_unique_id_checker)
    with assert_adds_messages(linter, _expect_missing(class_node)):
        walker.walk(root_node)


def test_explicit_none_class_body_fires(
    linter: UnittestLinter,
    entity_unique_id_checker: EntityUniqueIdChecker,
    tmp_path: Path,
) -> None:
    """Warning when _attr_unique_id = None at class level."""
    integration_dir = _make_integration(tmp_path)
    _create_quality_scale(integration_dir, {"entity-unique-id": "done"})

    root_node = _parse(
        """
from homeassistant.helpers.entity import Entity

class MySensor(Entity):
    _attr_unique_id = None
""",
        integration_dir,
    )

    class_node = next(root_node.nodes_of_class(nodes.ClassDef))
    walker = ASTWalker(linter)
    walker.add_checker(entity_unique_id_checker)
    with assert_adds_messages(linter, _expect_missing(class_node)):
        walker.walk(root_node)


def test_explicit_none_self_assign_fires(
    linter: UnittestLinter,
    entity_unique_id_checker: EntityUniqueIdChecker,
    tmp_path: Path,
) -> None:
    """Warning when self._attr_unique_id = None in __init__."""
    integration_dir = _make_integration(tmp_path)
    _create_quality_scale(integration_dir, {"entity-unique-id": "done"})

    root_node = _parse(
        """
from homeassistant.helpers.entity import Entity

class MySensor(Entity):
    def __init__(self):
        self._attr_unique_id = None
""",
        integration_dir,
    )

    class_node = next(root_node.nodes_of_class(nodes.ClassDef))
    walker = ASTWalker(linter)
    walker.add_checker(entity_unique_id_checker)
    with assert_adds_messages(linter, _expect_missing(class_node)):
        walker.walk(root_node)


def test_bare_annotation_only_fires(
    linter: UnittestLinter,
    entity_unique_id_checker: EntityUniqueIdChecker,
    tmp_path: Path,
) -> None:
    """``_attr_unique_id: str`` without a value doesn't satisfy the rule."""
    integration_dir = _make_integration(tmp_path)
    _create_quality_scale(integration_dir, {"entity-unique-id": "done"})

    root_node = _parse(
        """
from homeassistant.helpers.entity import Entity

class MySensor(Entity):
    _attr_unique_id: str
""",
        integration_dir,
    )

    class_node = next(root_node.nodes_of_class(nodes.ClassDef))
    walker = ASTWalker(linter)
    walker.add_checker(entity_unique_id_checker)
    with assert_adds_messages(linter, _expect_missing(class_node)):
        walker.walk(root_node)


def test_entity_default_does_not_satisfy(
    linter: UnittestLinter,
    entity_unique_id_checker: EntityUniqueIdChecker,
    tmp_path: Path,
) -> None:
    """Test Entity's defaults don't satisfy the rule.

    Inheriting Entity's ``_attr_unique_id = None`` / ``unique_id``
    property must not be treated as satisfying the rule. A bare
    subclass passes neither the ``_attr_unique_id`` non-None check
    (Entity sets it to None) nor the ``unique_id`` property override
    check (Entity itself is explicitly excluded).
    """
    integration_dir = _make_integration(tmp_path)
    _create_quality_scale(integration_dir, {"entity-unique-id": "done"})

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
    walker.add_checker(entity_unique_id_checker)
    with assert_adds_messages(linter, _expect_missing(class_node)):
        walker.walk(root_node)


def test_generic_subscript_base_sets_attr(
    linter: UnittestLinter,
    entity_unique_id_checker: EntityUniqueIdChecker,
    tmp_path: Path,
) -> None:
    """PEP-695-style generic base ``Base[T]`` is recognised as an ancestor."""
    integration_dir = _make_integration(tmp_path)
    _create_quality_scale(integration_dir, {"entity-unique-id": "done"})

    astroid.parse(
        """
from homeassistant.helpers.entity import Entity

class TestIntegrationGenericBase[T](Entity):
    _attr_unique_id = "x"
""",
        "homeassistant.components.test_integration.eui_entity",
    )

    root_node = _parse(
        """
from homeassistant.components.test_integration.eui_entity import TestIntegrationGenericBase

class MySensor(TestIntegrationGenericBase[int]):
    pass
""",
        integration_dir,
    )

    walker = ASTWalker(linter)
    walker.add_checker(entity_unique_id_checker)
    with assert_no_messages(linter):
        walker.walk(root_node)


def test_mixin_subclassed_in_same_module_ignored(
    linter: UnittestLinter,
    entity_unique_id_checker: EntityUniqueIdChecker,
    tmp_path: Path,
) -> None:
    """Mixin base class is skipped if another class in the same module extends it."""
    integration_dir = _make_integration(tmp_path)
    _create_quality_scale(integration_dir, {"entity-unique-id": "done"})

    root_node = _parse(
        """
from homeassistant.helpers.entity import Entity

class MyClimateMixin(Entity):
    _attr_temperature_unit = "C"

class ActualEntity(MyClimateMixin):
    _attr_unique_id = "x"
""",
        integration_dir,
    )

    walker = ASTWalker(linter)
    walker.add_checker(entity_unique_id_checker)
    with assert_no_messages(linter):
        walker.walk(root_node)


def test_leaf_class_still_fires(
    linter: UnittestLinter,
    entity_unique_id_checker: EntityUniqueIdChecker,
    tmp_path: Path,
) -> None:
    """A class that other module classes don't extend is still flagged."""
    integration_dir = _make_integration(tmp_path)
    _create_quality_scale(integration_dir, {"entity-unique-id": "done"})

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
    walker.add_checker(entity_unique_id_checker)
    with assert_adds_messages(linter, _expect_missing(class_node)):
        walker.walk(root_node)


def test_non_entity_class_ignored(
    linter: UnittestLinter,
    entity_unique_id_checker: EntityUniqueIdChecker,
    tmp_path: Path,
) -> None:
    """Class that does not inherit from Entity is ignored."""
    integration_dir = _make_integration(tmp_path)
    _create_quality_scale(integration_dir, {"entity-unique-id": "done"})

    root_node = _parse(
        """
class NotAnEntity:
    pass
""",
        integration_dir,
    )

    walker = ASTWalker(linter)
    walker.add_checker(entity_unique_id_checker)
    with assert_no_messages(linter):
        walker.walk(root_node)


def test_dict_status_done_fires(
    linter: UnittestLinter,
    entity_unique_id_checker: EntityUniqueIdChecker,
    tmp_path: Path,
) -> None:
    """Dict-form {status: done} also gates."""
    integration_dir = _make_integration(tmp_path)
    _create_quality_scale(
        integration_dir,
        {"entity-unique-id": {"status": "done", "comment": "ok"}},
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
    walker.add_checker(entity_unique_id_checker)
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
            {"entity-unique-id": "todo"},
            id="rule_todo",
        ),
        pytest.param(
            "homeassistant.components.test_integration.sensor",
            "sensor.py",
            {"entity-unique-id": {"status": "exempt", "comment": "reason"}},
            id="rule_exempt",
        ),
        pytest.param(
            "homeassistant.components.test_integration.sensor",
            "sensor.py",
            {"some-other-rule": "done"},
            id="rule_absent",
        ),
        pytest.param(
            "homeassistant.components.test_integration.eui_entity",
            "entity.py",
            {"entity-unique-id": "done"},
            id="non_platform_module",
        ),
        pytest.param(
            "homeassistant.components.test_integration",
            "__init__.py",
            {"entity-unique-id": "done"},
            id="init_module",
        ),
        pytest.param(
            "not_homeassistant.something.sensor",
            "sensor.py",
            {"entity-unique-id": "done"},
            id="not_an_integration",
        ),
    ],
)
def test_not_fired(
    linter: UnittestLinter,
    entity_unique_id_checker: EntityUniqueIdChecker,
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
    walker.add_checker(entity_unique_id_checker)
    with assert_no_messages(linter):
        walker.walk(root_node)


def _find_attr_value_node(
    root_node: nodes.Module, attr_name: str = "_attr_unique_id"
) -> nodes.NodeNG:
    """Find the value AST node of the first class-body ``attr_name = ...`` assign."""
    for class_node in root_node.nodes_of_class(nodes.ClassDef):
        for item in class_node.body:
            if (
                isinstance(item, nodes.Assign)
                and any(
                    isinstance(t, nodes.AssignName) and t.name == attr_name
                    for t in item.targets
                )
            ) or (
                isinstance(item, nodes.AnnAssign)
                and isinstance(item.target, nodes.AssignName)
                and item.target.name == attr_name
            ):
                return item.value
    raise AssertionError(f"no class-body assignment to {attr_name} found")


def _expect_static(value_node: nodes.NodeNG, class_name: str) -> MessageTest:
    """Build the expected MessageTest for a static-class-body violation."""
    return MessageTest(
        msg_id="home-assistant-entity-unique-id-static",
        node=value_node,
        line=value_node.lineno,
        col_offset=value_node.col_offset,
        end_line=value_node.end_lineno,
        end_col_offset=value_node.end_col_offset,
        args=(class_name,),
    )


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MySensor(Entity):
    _attr_unique_id = "fixed_id"
""",
            id="assign_string_literal",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MySensor(Entity):
    _attr_unique_id: str = "fixed_id"
""",
            id="annassign_string_literal",
        ),
    ],
)
def test_static_class_body_string_in_multi_entry_fires(
    linter: UnittestLinter,
    entity_unique_id_checker: EntityUniqueIdChecker,
    tmp_path: Path,
    code: str,
) -> None:
    """Multi-entry integration: class-body string-literal unique_id is flagged."""
    integration_dir = _make_integration(tmp_path, single_config_entry=False)
    _create_quality_scale(integration_dir, {"entity-unique-id": "done"})

    root_node = _parse(code, integration_dir)
    value_node = _find_attr_value_node(root_node)
    walker = ASTWalker(linter)
    walker.add_checker(entity_unique_id_checker)
    with assert_adds_messages(linter, _expect_static(value_node, "MySensor")):
        walker.walk(root_node)


def test_static_class_body_string_in_single_entry_passes(
    linter: UnittestLinter,
    entity_unique_id_checker: EntityUniqueIdChecker,
    tmp_path: Path,
) -> None:
    """Single-config-entry integration: class-body string literal is fine."""
    integration_dir = _make_integration(tmp_path, single_config_entry=True)
    _create_quality_scale(integration_dir, {"entity-unique-id": "done"})

    root_node = _parse(
        """
from homeassistant.helpers.entity import Entity

class MySensor(Entity):
    _attr_unique_id = "fixed_id"
""",
        integration_dir,
    )

    walker = ASTWalker(linter)
    walker.add_checker(entity_unique_id_checker)
    with assert_no_messages(linter):
        walker.walk(root_node)


def test_static_class_body_string_no_manifest_fires(
    linter: UnittestLinter,
    entity_unique_id_checker: EntityUniqueIdChecker,
    tmp_path: Path,
) -> None:
    """Absent manifest is treated as non-singleton: the rule fires."""
    integration_dir = tmp_path / "homeassistant" / "components" / "test_integration"
    integration_dir.mkdir(parents=True)
    _create_quality_scale(integration_dir, {"entity-unique-id": "done"})

    root_node = _parse(
        """
from homeassistant.helpers.entity import Entity

class MySensor(Entity):
    _attr_unique_id = "fixed_id"
""",
        integration_dir,
    )

    value_node = _find_attr_value_node(root_node)
    walker = ASTWalker(linter)
    walker.add_checker(entity_unique_id_checker)
    with assert_adds_messages(linter, _expect_static(value_node, "MySensor")):
        walker.walk(root_node)


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

MY_CONST = "fixed"

class MySensor(Entity):
    _attr_unique_id = MY_CONST
""",
            id="name_reference_not_flagged",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MySensor(Entity):
    def __init__(self, key):
        self._attr_unique_id = key
""",
            id="self_assign_string_not_flagged",
        ),
    ],
)
def test_static_rule_only_targets_class_body_string_literals(
    linter: UnittestLinter,
    entity_unique_id_checker: EntityUniqueIdChecker,
    tmp_path: Path,
    code: str,
) -> None:
    """W7424 only fires for literal strings at class body; references / self-assigns pass."""
    integration_dir = _make_integration(tmp_path, single_config_entry=False)
    _create_quality_scale(integration_dir, {"entity-unique-id": "done"})

    root_node = _parse(code, integration_dir)
    walker = ASTWalker(linter)
    walker.add_checker(entity_unique_id_checker)
    with assert_no_messages(linter):
        walker.walk(root_node)


def test_static_rule_gated_off_when_rule_not_done(
    linter: UnittestLinter,
    entity_unique_id_checker: EntityUniqueIdChecker,
    tmp_path: Path,
) -> None:
    """When entity-unique-id is not 'done', W7424 doesn't fire either."""
    integration_dir = _make_integration(tmp_path, single_config_entry=False)
    _create_quality_scale(integration_dir, {"entity-unique-id": "todo"})

    root_node = _parse(
        """
from homeassistant.helpers.entity import Entity

class MySensor(Entity):
    _attr_unique_id = "fixed_id"
""",
        integration_dir,
    )

    walker = ASTWalker(linter)
    walker.add_checker(entity_unique_id_checker)
    with assert_no_messages(linter):
        walker.walk(root_node)

"""Tests for the entity_unique_id_format pylint checker."""

import json
from pathlib import Path

import astroid
from astroid import nodes
from pylint.testutils import MessageTest, UnittestLinter
from pylint_home_assistant.checkers.entity_unique_id_format import (
    EntityUniqueIdFormatChecker,
)
from pylint_home_assistant.helpers.integration import clear_caches
import pytest

from . import assert_adds_messages, assert_no_messages, walk_checker


@pytest.fixture(name="checker")
def checker_fixture(
    linter: UnittestLinter,
) -> EntityUniqueIdFormatChecker:
    """Fixture to provide the W7425 checker."""
    clear_caches()
    return EntityUniqueIdFormatChecker(linter)


def _make_integration(tmp_path: Path, *, domain: str = "test_integration") -> Path:
    """Create a fake integration directory under components/."""
    integration_dir = tmp_path / "homeassistant" / "components" / "test_integration"
    integration_dir.mkdir(parents=True)
    (integration_dir / "manifest.json").write_text(
        json.dumps({"domain": domain, "single_config_entry": False})
    )
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


def _find_attr_value_node(
    root_node: nodes.Module, attr_name: str = "_attr_unique_id"
) -> nodes.NodeNG:
    """Find the value AST node of the first assignment to *attr_name*.

    Matches both class-body ``attr_name = ...`` assignments and
    ``self.attr_name = ...`` assignments at any depth.
    """
    for assign in root_node.nodes_of_class((nodes.Assign, nodes.AnnAssign)):
        targets = (
            list(assign.targets)
            if isinstance(assign, nodes.Assign)
            else [assign.target]
        )
        for target in targets:
            if isinstance(target, nodes.AssignName) and target.name == attr_name:
                return assign.value
            if (
                isinstance(target, nodes.AssignAttr)
                and target.attrname == attr_name
                and isinstance(target.expr, nodes.Name)
                and target.expr.name == "self"
            ):
                return assign.value
    raise AssertionError(f"no assignment to {attr_name} found")


def _expect_redundant_domain(value_node: nodes.NodeNG, class_name: str) -> MessageTest:
    """Build the expected MessageTest for a DOMAIN-in-unique_id violation."""
    return MessageTest(
        msg_id="home-assistant-entity-unique-id-redundant-domain",
        node=value_node,
        line=value_node.lineno,
        col_offset=value_node.col_offset,
        end_line=value_node.end_lineno,
        end_col_offset=value_node.end_col_offset,
        args=(class_name,),
    )


def _expect_redundant_platform(
    value_node: nodes.NodeNG, class_name: str, platform: str
) -> MessageTest:
    """Build the expected MessageTest for a platform-in-unique_id violation."""
    return MessageTest(
        msg_id="home-assistant-entity-unique-id-redundant-platform",
        node=value_node,
        line=value_node.lineno,
        col_offset=value_node.col_offset,
        end_line=value_node.end_lineno,
        end_col_offset=value_node.end_col_offset,
        args=(class_name, platform),
    )


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
from .const import DOMAIN
from homeassistant.helpers.entity import Entity

class MySensor(Entity):
    _attr_unique_id = DOMAIN
""",
            id="class_body_name_only",
        ),
        pytest.param(
            """
from .const import DOMAIN
from homeassistant.helpers.entity import Entity

class MySensor(Entity):
    def __init__(self, entry, key):
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_{key}"
""",
            id="self_assign_fstring_leading_domain",
        ),
        pytest.param(
            """
from .const import DOMAIN
from homeassistant.helpers.entity import Entity

class MySensor(Entity):
    def __init__(self, entry, key):
        self._attr_unique_id = f"{key}_{DOMAIN}_{entry.entry_id}"
""",
            id="self_assign_fstring_embedded_domain",
        ),
        pytest.param(
            """
from .const import DOMAIN
from homeassistant.helpers.entity import Entity

class MySensor(Entity):
    def __init__(self, entry, key):
        if key:
            self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_{key}"
        else:
            self._attr_unique_id = entry.entry_id
""",
            id="self_assign_inside_if_branch",
        ),
        pytest.param(
            """
from .const import DOMAIN
from homeassistant.helpers.entity import Entity

class MySensor(Entity):
    _attr_unique_id: str = DOMAIN
""",
            id="class_body_annassign_name",
        ),
        pytest.param(
            """
from .const import DOMAIN
from homeassistant.helpers.entity import Entity

class MySensor(Entity):
    def __init__(self, host, port, key):
        self._attr_unique_id = "_".join([DOMAIN, host, str(port), key])
""",
            id="self_assign_name_buried_in_call_args",
        ),
        pytest.param(
            """
from .const import DOMAIN
from homeassistant.helpers.entity import Entity

class MySensor(Entity):
    async def async_added_to_hass(self):
        self._attr_unique_id = f"{DOMAIN}_{self._key}"
""",
            id="async_method_self_assign",
        ),
    ],
)
def test_redundant_domain_fires(
    linter: UnittestLinter,
    checker: EntityUniqueIdFormatChecker,
    tmp_path: Path,
    code: str,
) -> None:
    """W7425 fires when _attr_unique_id references DOMAIN."""
    integration_dir = _make_integration(tmp_path)

    root_node = _parse(code, integration_dir)
    value_node = _find_attr_value_node(root_node)
    with assert_adds_messages(linter, _expect_redundant_domain(value_node, "MySensor")):
        walk_checker(linter, checker, root_node)


def test_redundant_domain_fires_in_both_branches(
    linter: UnittestLinter,
    checker: EntityUniqueIdFormatChecker,
    tmp_path: Path,
) -> None:
    """One message per offending assignment when DOMAIN appears in both branches."""
    integration_dir = _make_integration(tmp_path)

    root_node = _parse(
        """
from .const import DOMAIN
from homeassistant.helpers.entity import Entity

class MySensor(Entity):
    def __init__(self, entry, key):
        if key:
            self._attr_unique_id = f"{DOMAIN}_a_{entry.entry_id}"
        else:
            self._attr_unique_id = f"{DOMAIN}_b_{entry.entry_id}"
""",
        integration_dir,
    )
    value_nodes = [
        assign.value
        for assign in root_node.nodes_of_class((nodes.Assign, nodes.AnnAssign))
        if any(
            isinstance(t, nodes.AssignAttr)
            and t.attrname == "_attr_unique_id"
            and isinstance(t.expr, nodes.Name)
            and t.expr.name == "self"
            for t in (
                assign.targets if isinstance(assign, nodes.Assign) else [assign.target]
            )
        )
    ]
    assert len(value_nodes) == 2
    with assert_adds_messages(
        linter,
        _expect_redundant_domain(value_nodes[0], "MySensor"),
        _expect_redundant_domain(value_nodes[1], "MySensor"),
    ):
        walk_checker(linter, checker, root_node)


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MySensor(Entity):
    def __init__(self, entry, key):
        self._attr_unique_id = f"{entry.entry_id}_{key}"
""",
            id="no_domain_reference",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MySensor(Entity):
    def __init__(self, entry, key):
        domain_prefix = "myprefix"
        self._attr_unique_id = f"{domain_prefix}_{key}"
""",
            id="local_name_not_DOMAIN",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MySensor(Entity):
    @property
    def unique_id(self) -> str:
        return self._key
""",
            id="plain_unique_id_property",
        ),
    ],
)
def test_redundant_domain_does_not_fire(
    linter: UnittestLinter,
    checker: EntityUniqueIdFormatChecker,
    tmp_path: Path,
    code: str,
) -> None:
    """W7425 does not fire when the unique_id value doesn't embed the domain."""
    integration_dir = _make_integration(tmp_path)

    root_node = _parse(code, integration_dir)
    with assert_no_messages(linter):
        walk_checker(linter, checker, root_node)


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MySensor(Entity):
    def __init__(self, server_id):
        self._attr_unique_id = f"myhub-scan_clients-{server_id}"
""",
            id="domain_prefix_with_dash",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MySensor(Entity):
    def __init__(self, key):
        self._attr_unique_id = f"myhub_{key}"
""",
            id="domain_prefix_with_underscore",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MySensor(Entity):
    def __init__(self, key, host):
        self._attr_unique_id = f"{host}_myhub_{key}"
""",
            id="domain_embedded_segment",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MySensor(Entity):
    _attr_unique_id = "myhub-static"
""",
            id="domain_in_class_body_literal",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MySensor(Entity):
    def __init__(self, key):
        self._attr_unique_id = f"myhub.{key}"
""",
            id="domain_prefix_with_dot",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MySensor(Entity):
    def __init__(self, key):
        self._attr_unique_id = f"{key}:myhub:value"
""",
            id="domain_embedded_with_colons",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MySensor(Entity):
    def __init__(self, key):
        self._attr_unique_id = f"{key} myhub other"
""",
            id="domain_delimited_by_spaces",
        ),
    ],
)
def test_redundant_domain_literal_fires(
    linter: UnittestLinter,
    checker: EntityUniqueIdFormatChecker,
    tmp_path: Path,
    code: str,
) -> None:
    """W7425 fires when the integration's domain appears as a delimited literal."""
    integration_dir = _make_integration(tmp_path, domain="myhub")

    root_node = _parse(code, integration_dir)
    walk_checker(linter, checker, root_node)
    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "home-assistant-entity-unique-id-redundant-domain"


@pytest.mark.parametrize(
    ("literal", "fires"),
    [
        pytest.param("my_hub", True, id="exact_match"),
        pytest.param("my_hub_key", True, id="trailing_underscore"),
        pytest.param("prefix_my_hub_key", True, id="underscore_on_both_sides"),
        pytest.param("my_hub-key", True, id="trailing_dash"),
        pytest.param("my_hub.key", True, id="trailing_dot"),
        pytest.param("my_hubs_key", False, id="extended_into_longer_word"),
        pytest.param("Amy_hubB", False, id="alpha_on_both_sides"),
        pytest.param("my_hubX", False, id="trailing_letter"),
    ],
)
def test_redundant_domain_with_underscored_domain(
    linter: UnittestLinter,
    checker: EntityUniqueIdFormatChecker,
    tmp_path: Path,
    literal: str,
    fires: bool,
) -> None:
    """Domain containing ``_`` is matched literally; boundaries apply outside it."""
    integration_dir = _make_integration(tmp_path, domain="my_hub")

    root_node = _parse(
        f"""
from homeassistant.helpers.entity import Entity

class MySensor(Entity):
    _attr_unique_id = "{literal}"
""",
        integration_dir,
    )
    walk_checker(linter, checker, root_node)
    messages = linter.release_messages()
    assert len(messages) == (1 if fires else 0)


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MySensor(Entity):
    def __init__(self, key):
        self._attr_unique_id = f"myhubitat_{key}"
""",
            id="non_delimited_substring_in_word",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MySensor(Entity):
    def __init__(self, key):
        self._attr_unique_id = f"submyhub-{key}"
""",
            id="domain_appears_inside_other_word",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MySensor(Entity):
    def __init__(self, key):
        self._attr_unique_id = f"Amyhub-{key}"
""",
            id="domain_preceded_by_letter",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MySensor(Entity):
    def __init__(self, key):
        self._attr_unique_id = f"-myhubX-{key}"
""",
            id="domain_followed_by_letter",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MySensor(Entity):
    def __init__(self, key):
        self._attr_unique_id = f"1myhub2"
""",
            id="domain_between_digits",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MySensor(Entity):
    def __init__(self, key):
        self._attr_unique_id = f"-myhub2{key}"
""",
            id="domain_followed_by_digit",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MySensor(Entity):
    def __init__(self, prefix, key):
        self._attr_unique_id = f"{prefix}myhub-{key}"
""",
            id="domain_at_const_start_after_fstring_expr",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MySensor(Entity):
    def __init__(self, suffix, key):
        self._attr_unique_id = f"-myhub{suffix}-{key}"
""",
            id="domain_at_const_end_before_fstring_expr",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MySensor(Entity):
    def __init__(self, key):
        self._attr_unique_id = f"myhub{key}"
""",
            id="domain_at_fstring_start_then_expr",
        ),
    ],
)
def test_redundant_domain_literal_does_not_fire_on_word_substrings(
    linter: UnittestLinter,
    checker: EntityUniqueIdFormatChecker,
    tmp_path: Path,
    code: str,
) -> None:
    """Domain appearing as a non-delimited substring of a larger word doesn't fire."""
    integration_dir = _make_integration(tmp_path, domain="myhub")

    root_node = _parse(code, integration_dir)
    with assert_no_messages(linter):
        walk_checker(linter, checker, root_node)


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
from .const import DOMAIN
from homeassistant.helpers.entity import Entity

class MySensor(Entity):
    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_{self._key}"
""",
            id="property",
        ),
        pytest.param(
            """
from functools import cached_property
from .const import DOMAIN
from homeassistant.helpers.entity import Entity

class MySensor(Entity):
    @cached_property
    def unique_id(self) -> str:
        return f"{DOMAIN}_{self._key}"
""",
            id="cached_property",
        ),
    ],
)
def test_redundant_domain_fires_in_unique_id_property(
    linter: UnittestLinter,
    checker: EntityUniqueIdFormatChecker,
    tmp_path: Path,
    code: str,
) -> None:
    """W7425 fires when DOMAIN is referenced in a ``unique_id`` property body."""
    integration_dir = _make_integration(tmp_path)

    root_node = _parse(code, integration_dir)
    return_node = next(root_node.nodes_of_class(nodes.Return))
    with assert_adds_messages(
        linter, _expect_redundant_domain(return_node.value, "MySensor")
    ):
        walk_checker(linter, checker, root_node)


@pytest.mark.parametrize(
    ("code", "module_name", "file_name"),
    [
        pytest.param(
            """
from .const import DOMAIN

class NotAnEntity:
    def __init__(self, key):
        self._attr_unique_id = f"{DOMAIN}_{key}"
""",
            "homeassistant.components.test_integration.sensor",
            "sensor.py",
            id="non_entity_class",
        ),
        pytest.param(
            """
from .const import DOMAIN
from homeassistant.helpers.entity import Entity

class MyEntity(Entity):
    def __init__(self, key):
        self._attr_unique_id = f"{DOMAIN}_{key}"
""",
            "not_homeassistant.something.sensor",
            "sensor.py",
            id="module_outside_integration",
        ),
    ],
)
def test_out_of_scope_ignored(
    linter: UnittestLinter,
    checker: EntityUniqueIdFormatChecker,
    tmp_path: Path,
    code: str,
    module_name: str,
    file_name: str,
) -> None:
    """W7425 doesn't fire for classes/modules outside the rule's scope."""
    integration_dir = _make_integration(tmp_path)

    root_node = _parse(
        code, integration_dir, module_name=module_name, file_name=file_name
    )
    with assert_no_messages(linter):
        walk_checker(linter, checker, root_node)


@pytest.mark.parametrize(
    ("module_name", "file_name"),
    [
        pytest.param(
            "homeassistant.components.test_integration.entity",
            "entity.py",
            id="entity_module",
        ),
        pytest.param(
            "homeassistant.components.test_integration",
            "__init__.py",
            id="init_module",
        ),
    ],
)
def test_non_platform_module_fires(
    linter: UnittestLinter,
    checker: EntityUniqueIdFormatChecker,
    tmp_path: Path,
    module_name: str,
    file_name: str,
) -> None:
    """W7425 fires in non-platform modules (entity.py, __init__.py) too.

    Shared base entities are commonly defined outside platform modules,
    and antipatterns there propagate to every subclass.
    """
    integration_dir = _make_integration(tmp_path)

    root_node = _parse(
        """
from .const import DOMAIN
from homeassistant.helpers.entity import Entity

class MyEntity(Entity):
    def __init__(self, key):
        self._attr_unique_id = f"{DOMAIN}_{key}"
""",
        integration_dir,
        module_name=module_name,
        file_name=file_name,
    )
    value_node = _find_attr_value_node(root_node)
    with assert_adds_messages(linter, _expect_redundant_domain(value_node, "MyEntity")):
        walk_checker(linter, checker, root_node)


def test_same_module_mixin_base_fires(
    linter: UnittestLinter,
    checker: EntityUniqueIdFormatChecker,
    tmp_path: Path,
) -> None:
    """W7425 fires on a same-module base class that has the antipattern.

    Unlike the gated rules (which exempt mixins/abstract bases), W7425
    targets antipatterns in code that propagate to every subclass via
    inheritance.
    """
    integration_dir = _make_integration(tmp_path)

    root_node = _parse(
        """
from .const import DOMAIN
from homeassistant.helpers.entity import Entity

class MyBaseSensor(Entity):
    def __init__(self, coordinator, key):
        self._attr_unique_id = f"{DOMAIN}_{coordinator.id}_{key}"

class MyConcreteSensor(MyBaseSensor):
    pass
""",
        integration_dir,
    )
    value_node = _find_attr_value_node(root_node)
    with assert_adds_messages(
        linter, _expect_redundant_domain(value_node, "MyBaseSensor")
    ):
        walk_checker(linter, checker, root_node)


@pytest.mark.parametrize(
    ("code", "platform", "module_name", "file_name"),
    [
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MySensor(Entity):
    def __init__(self, key):
        self._attr_unique_id = f"sensor_{key}"
""",
            "sensor",
            "homeassistant.components.test_integration.sensor",
            "sensor.py",
            id="sensor_prefix_underscore",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MyLight(Entity):
    def __init__(self, key):
        self._attr_unique_id = f"{key}-light"
""",
            "light",
            "homeassistant.components.test_integration.light",
            "light.py",
            id="light_suffix_dash",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MyBinarySensor(Entity):
    def __init__(self, key):
        self._attr_unique_id = f"{key}_binary_sensor_{key}"
""",
            "binary_sensor",
            "homeassistant.components.test_integration.binary_sensor",
            "binary_sensor.py",
            id="binary_sensor_embedded_segment",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MySwitch(Entity):
    _attr_unique_id = "switch-static"
""",
            "switch",
            "homeassistant.components.test_integration.switch",
            "switch.py",
            id="switch_class_body_literal",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MySensor(Entity):
    def __init__(self, key):
        self._attr_unique_id = f"sensor_{key}"
""",
            "sensor",
            "homeassistant.components.test_integration.sensor.helpers",
            "sensor/helpers.py",
            id="platform_package_submodule",
        ),
    ],
)
def test_redundant_platform_fires(
    linter: UnittestLinter,
    checker: EntityUniqueIdFormatChecker,
    tmp_path: Path,
    code: str,
    platform: str,
    module_name: str,
    file_name: str,
) -> None:
    """W7427 fires when _attr_unique_id embeds the platform name as a delimited segment."""
    integration_dir = _make_integration(tmp_path)

    root_node = _parse(
        code, integration_dir, module_name=module_name, file_name=file_name
    )
    value_node = _find_attr_value_node(root_node)
    class_node = next(root_node.nodes_of_class(nodes.ClassDef))
    with assert_adds_messages(
        linter, _expect_redundant_platform(value_node, class_node.name, platform)
    ):
        walk_checker(linter, checker, root_node)


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MyLight(Entity):
    def __init__(self, key):
        self._attr_unique_id = f"lighter_{key}"
""",
            id="non_delimited_substring_in_word",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MyLight(Entity):
    def __init__(self, key):
        self._attr_unique_id = f"highlight-{key}"
""",
            id="platform_appears_inside_other_word",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MyLight(Entity):
    def __init__(self, key):
        self._attr_unique_id = f"{key}_brightness"
""",
            id="no_platform_reference",
        ),
    ],
)
def test_redundant_platform_does_not_fire(
    linter: UnittestLinter,
    checker: EntityUniqueIdFormatChecker,
    tmp_path: Path,
    code: str,
) -> None:
    """W7427 does not fire when the platform name is absent or not delimited."""
    integration_dir = _make_integration(tmp_path)

    root_node = _parse(
        code,
        integration_dir,
        module_name="homeassistant.components.test_integration.light",
        file_name="light.py",
    )
    with assert_no_messages(linter):
        walk_checker(linter, checker, root_node)


@pytest.mark.parametrize(
    ("module_name", "file_name"),
    [
        pytest.param(
            "homeassistant.components.test_integration.entity",
            "entity.py",
            id="entity_module",
        ),
        pytest.param(
            "homeassistant.components.test_integration",
            "__init__.py",
            id="init_module",
        ),
        pytest.param(
            "homeassistant.components.test_integration.coordinator",
            "coordinator.py",
            id="non_platform_submodule",
        ),
    ],
)
def test_redundant_platform_does_not_fire_outside_platform_module(
    linter: UnittestLinter,
    checker: EntityUniqueIdFormatChecker,
    tmp_path: Path,
    module_name: str,
    file_name: str,
) -> None:
    """W7427 only fires in platform modules; entity.py / __init__.py / other are out of scope."""
    integration_dir = _make_integration(tmp_path)

    root_node = _parse(
        """
from homeassistant.helpers.entity import Entity

class MyEntity(Entity):
    def __init__(self, key):
        self._attr_unique_id = f"sensor_{key}"
""",
        integration_dir,
        module_name=module_name,
        file_name=file_name,
    )
    with assert_no_messages(linter):
        walk_checker(linter, checker, root_node)


def test_redundant_platform_fires_in_unique_id_property(
    linter: UnittestLinter,
    checker: EntityUniqueIdFormatChecker,
    tmp_path: Path,
) -> None:
    """W7427 fires when a ``unique_id`` property returns a value embedding the platform."""
    integration_dir = _make_integration(tmp_path)

    root_node = _parse(
        """
from homeassistant.helpers.entity import Entity

class MySensor(Entity):
    @property
    def unique_id(self) -> str:
        return f"sensor_{self._key}"
""",
        integration_dir,
        module_name="homeassistant.components.test_integration.sensor",
        file_name="sensor.py",
    )
    return_node = next(root_node.nodes_of_class(nodes.Return))
    with assert_adds_messages(
        linter, _expect_redundant_platform(return_node.value, "MySensor", "sensor")
    ):
        walk_checker(linter, checker, root_node)


def test_redundant_domain_and_platform_both_fire(
    linter: UnittestLinter,
    checker: EntityUniqueIdFormatChecker,
    tmp_path: Path,
) -> None:
    """W7425 and W7427 both fire when the value embeds DOMAIN and the platform name."""
    integration_dir = _make_integration(tmp_path)

    root_node = _parse(
        """
from .const import DOMAIN
from homeassistant.helpers.entity import Entity

class MySensor(Entity):
    def __init__(self, key):
        self._attr_unique_id = f"{DOMAIN}_sensor_{key}"
""",
        integration_dir,
        module_name="homeassistant.components.test_integration.sensor",
        file_name="sensor.py",
    )
    value_node = _find_attr_value_node(root_node)
    with assert_adds_messages(
        linter,
        _expect_redundant_domain(value_node, "MySensor"),
        _expect_redundant_platform(value_node, "MySensor", "sensor"),
    ):
        walk_checker(linter, checker, root_node)

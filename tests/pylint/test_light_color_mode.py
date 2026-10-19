"""Tests for the light_color_mode pylint checker."""

import json
from pathlib import Path

import astroid
from astroid import nodes
from pylint.testutils import MessageTest, UnittestLinter
from pylint_home_assistant.checkers.light_color_mode import HassLightColorModeChecker
import pytest

from . import assert_adds_messages, assert_no_messages, walk_checker

_MISSING_COLOR_MODE = "home-assistant-light-missing-color-mode"
_MISSING_SUPPORTED = "home-assistant-light-missing-supported-color-modes"


@pytest.fixture(name="checker")
def checker_fixture(linter: UnittestLinter) -> HassLightColorModeChecker:
    """Fixture to provide the W7436 + W7437 checker."""
    return HassLightColorModeChecker(linter)


def _make_integration(tmp_path: Path, *, domain: str = "test_integration") -> Path:
    """Create a fake integration directory under components/."""
    integration_dir = tmp_path / "homeassistant" / "components" / "test_integration"
    integration_dir.mkdir(parents=True)
    (integration_dir / "manifest.json").write_text(json.dumps({"domain": domain}))
    return integration_dir


def _parse(
    code: str,
    integration_dir: Path,
    module_name: str = "homeassistant.components.test_integration.light",
    file_name: str = "light.py",
) -> nodes.Module:
    """Parse code as a module of the integration with .file set."""
    root_node = astroid.parse(code, module_name)
    root_node.file = str(integration_dir / file_name)
    return root_node


def _find_class(root_node: nodes.Module, name: str) -> nodes.ClassDef:
    """Return the ClassDef named *name*."""
    for class_node in root_node.nodes_of_class(nodes.ClassDef):
        if class_node.name == name:
            return class_node
    raise AssertionError(f"no class named {name} found")


def _expect(class_node: nodes.ClassDef, msg_id: str) -> MessageTest:
    """Build the expected MessageTest for a flagged class."""
    pos = class_node.position
    return MessageTest(
        msg_id=msg_id,
        node=class_node,
        line=pos.lineno,
        col_offset=pos.col_offset,
        end_line=pos.end_lineno,
        end_col_offset=pos.end_col_offset,
        args=(class_node.name,),
    )


@pytest.mark.parametrize(
    ("code", "class_name"),
    [
        pytest.param(
            """
from homeassistant.components.light import ColorMode, LightEntity

class MyLight(LightEntity):
    _attr_supported_color_modes = {ColorMode.ONOFF}
""",
            "MyLight",
            id="class_body_supported_no_color_mode",
        ),
        pytest.param(
            """
from homeassistant.components.light import ColorMode, LightEntity

class MyLight(LightEntity):
    def __init__(self, status) -> None:
        modes = {ColorMode.HS}
        self._attr_supported_color_modes = modes
""",
            "MyLight",
            id="self_assign_supported_no_color_mode",
        ),
        pytest.param(
            """
from homeassistant.components.light import ColorMode, LightEntity

class MyLight(LightEntity):
    @property
    def supported_color_modes(self):
        return {ColorMode.HS}
""",
            "MyLight",
            id="supported_property_override_no_color_mode",
        ),
        pytest.param(
            """
from homeassistant.components.light import ColorMode, LightEntity

class MyLight(LightEntity):
    _attr_supported_color_modes = {ColorMode.HS}
    _attr_color_mode = None
""",
            "MyLight",
            id="color_mode_explicitly_none",
        ),
        pytest.param(
            """
from homeassistant.components.light import ColorMode, LightEntity

class MyLight(LightEntity):
    _attr_supported_color_modes = {ColorMode.HS}
    _attr_color_mode = ColorMode.HS
    _attr_color_mode = None
""",
            "MyLight",
            id="color_mode_reassigned_none_wins",
        ),
        pytest.param(
            """
from homeassistant.components.light import ColorMode, LightEntity

class MyLight(LightEntity):
    _attr_supported_color_modes = {ColorMode.HS}

    def _factory(self):
        class _Inner:
            def run(self):
                self._attr_color_mode = ColorMode.HS
        return _Inner
""",
            "MyLight",
            id="color_mode_only_in_nested_class_scope",
        ),
        pytest.param(
            """
from homeassistant.components.light import ColorMode, LightEntity

class MyBaseLight(LightEntity):
    _attr_supported_color_modes = {ColorMode.HS}

class MyLight(MyBaseLight):
    pass
""",
            "MyLight",
            id="supported_inherited_color_mode_missing",
        ),
        pytest.param(
            """
from homeassistant.components.light import ColorMode, LightEntity

class MyBaseLight(LightEntity):
    _attr_supported_color_modes = {ColorMode.HS}
    _attr_color_mode = ColorMode.HS

class MyLight(MyBaseLight):
    _attr_color_mode = None
""",
            "MyLight",
            id="subclass_nullifies_inherited_color_mode",
        ),
        pytest.param(
            """
from homeassistant.components.light import ColorMode, LightEntity

class MyBaseLight(LightEntity):
    pass

class MyColorLight(MyBaseLight):
    def __init__(self, status) -> None:
        self._attr_supported_color_modes = {ColorMode.HS}

    @property
    def color_mode(self):
        return ColorMode.HS

class MySwitchLight(MyBaseLight):
    def __init__(self, status) -> None:
        self._attr_supported_color_modes = {ColorMode.ONOFF}
""",
            "MySwitchLight",
            id="two_subclasses_only_offender",
        ),
    ],
)
def test_fires_w7436(
    linter: UnittestLinter,
    checker: HassLightColorModeChecker,
    tmp_path: Path,
    code: str,
    class_name: str,
) -> None:
    """W7436 fires when supported color modes are set but no color mode is reported."""
    integration_dir = _make_integration(tmp_path)

    root_node = _parse(code, integration_dir)
    class_node = _find_class(root_node, class_name)
    with assert_adds_messages(linter, _expect(class_node, _MISSING_COLOR_MODE)):
        walk_checker(linter, checker, root_node)


@pytest.mark.parametrize(
    ("code", "class_name"),
    [
        pytest.param(
            """
from homeassistant.components.light import ColorMode, LightEntity

class MyLight(LightEntity):
    _attr_color_mode = ColorMode.ONOFF
""",
            "MyLight",
            id="class_body_color_mode_no_supported",
        ),
        pytest.param(
            """
from homeassistant.components.light import ColorMode, LightEntity

class MyLight(LightEntity):
    def __init__(self, status) -> None:
        self._attr_color_mode = ColorMode.HS
""",
            "MyLight",
            id="self_assign_color_mode_no_supported",
        ),
        pytest.param(
            """
from homeassistant.components.light import ColorMode, LightEntity

class MyLight(LightEntity):
    @property
    def color_mode(self):
        return ColorMode.HS
""",
            "MyLight",
            id="color_mode_property_override_no_supported",
        ),
        pytest.param(
            """
from homeassistant.components.light import ColorMode, LightEntity

class MyBaseLight(LightEntity):
    _attr_color_mode = ColorMode.HS

class MyLight(MyBaseLight):
    pass
""",
            "MyLight",
            id="color_mode_inherited_supported_missing",
        ),
        pytest.param(
            """
from homeassistant.components.light import ColorMode, LightEntity

class MyBaseLight(LightEntity):
    _attr_supported_color_modes = {ColorMode.HS}
    _attr_color_mode = ColorMode.HS

class MyLight(MyBaseLight):
    _attr_supported_color_modes = None
""",
            "MyLight",
            id="subclass_nullifies_inherited_supported",
        ),
    ],
)
def test_fires_w7437(
    linter: UnittestLinter,
    checker: HassLightColorModeChecker,
    tmp_path: Path,
    code: str,
    class_name: str,
) -> None:
    """W7437 fires when a color mode is reported but no supported modes are set."""
    integration_dir = _make_integration(tmp_path)

    root_node = _parse(code, integration_dir)
    class_node = _find_class(root_node, class_name)
    with assert_adds_messages(linter, _expect(class_node, _MISSING_SUPPORTED)):
        walk_checker(linter, checker, root_node)


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
from homeassistant.components.light import ColorMode, LightEntity

class MyLight(LightEntity):
    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_color_mode = ColorMode.ONOFF
""",
            id="both_class_attrs",
        ),
        pytest.param(
            """
from homeassistant.components.light import ColorMode, LightEntity

class MyLight(LightEntity):
    _attr_supported_color_modes = {ColorMode.HS}

    @property
    def color_mode(self):
        return ColorMode.HS
""",
            id="supported_attr_and_color_mode_property",
        ),
        pytest.param(
            """
from homeassistant.components.light import ColorMode, LightEntity

class MyLight(LightEntity):
    def __init__(self, status) -> None:
        self._attr_supported_color_modes = {ColorMode.HS}
        self._attr_color_mode = ColorMode.HS
""",
            id="both_self_assigned",
        ),
        pytest.param(
            """
from homeassistant.components.light import LightEntity

class MyLight(LightEntity):
    @property
    def is_on(self) -> bool:
        return True
""",
            id="neither_set",
        ),
        pytest.param(
            """
from homeassistant.components.light import ColorMode, LightEntity

class MyLight(LightEntity):
    _attr_supported_color_modes: set[ColorMode] | None = None
""",
            id="supported_explicitly_none",
        ),
        pytest.param(
            """
from homeassistant.components.light import ColorMode, LightEntity

class MyBaseLight(LightEntity):
    _attr_color_mode = ColorMode.HS

class MyLight(MyBaseLight):
    _attr_supported_color_modes = {ColorMode.HS}
""",
            id="color_mode_from_base_supported_from_subclass",
        ),
        pytest.param(
            """
from homeassistant.components.light import ColorMode, LightEntity

class MyBaseLight(LightEntity):
    _attr_supported_color_modes = {ColorMode.HS}

class MyLight(MyBaseLight):
    _attr_color_mode = ColorMode.HS
""",
            id="supported_from_base_color_mode_from_subclass",
        ),
        pytest.param(
            """
from homeassistant.components.light import ColorMode, LightEntity

class MyBaseLight(LightEntity):
    _attr_supported_color_modes = {ColorMode.HS}
    _attr_color_mode = ColorMode.HS

class MyLight(MyBaseLight):
    _attr_color_mode = None

    def __init__(self) -> None:
        self._attr_color_mode = ColorMode.HS
""",
            id="subclass_reassigns_inherited_color_mode_via_init",
        ),
    ],
)
def test_good(
    linter: UnittestLinter,
    checker: HassLightColorModeChecker,
    tmp_path: Path,
    code: str,
) -> None:
    """No message when a light reports both halves, or neither.

    Covers the both-reported cases (directly or via inheritance, including a
    runtime ``self._attr_...`` assignment that wins over a class-body
    ``None``) and the both-missing case (legacy/abstract, deliberately not
    flagged).
    """
    integration_dir = _make_integration(tmp_path)

    root_node = _parse(code, integration_dir)
    with assert_no_messages(linter):
        walk_checker(linter, checker, root_node)


@pytest.mark.parametrize(
    ("code", "module_name", "file_name"),
    [
        pytest.param(
            """
from homeassistant.components.light import ColorMode

class NotALight:
    _attr_supported_color_modes = {ColorMode.HS}
""",
            "homeassistant.components.test_integration.light",
            "light.py",
            id="non_light_entity_class",
        ),
        pytest.param(
            """
from homeassistant.components.light import ColorMode, LightEntity

class MyLight(LightEntity):
    _attr_supported_color_modes = {ColorMode.HS}
""",
            "not_homeassistant.something.light",
            "light.py",
            id="module_outside_integration",
        ),
    ],
)
def test_out_of_scope_ignored(
    linter: UnittestLinter,
    checker: HassLightColorModeChecker,
    tmp_path: Path,
    code: str,
    module_name: str,
    file_name: str,
) -> None:
    """W7436 doesn't fire for classes/modules outside the rule's scope."""
    integration_dir = _make_integration(tmp_path)

    root_node = _parse(
        code, integration_dir, module_name=module_name, file_name=file_name
    )
    with assert_no_messages(linter):
        walk_checker(linter, checker, root_node)

"""Tests for the light_color_mode pylint checker."""

import json
from pathlib import Path

import astroid
from astroid import nodes
from pylint.testutils import MessageTest, UnittestLinter
from pylint_home_assistant.checkers.light_color_mode import HassLightColorModeChecker
import pytest

from . import assert_adds_messages, assert_no_messages, walk_checker


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


def _expect(
    class_node: nodes.ClassDef,
    msg_id: str = "home-assistant-light-missing-color-mode",
) -> MessageTest:
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


_MISSING_SUPPORTED = "home-assistant-light-missing-supported-color-modes"


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
from homeassistant.components.light import ColorMode, LightEntity

class MyLight(LightEntity):
    _attr_supported_color_modes = {ColorMode.ONOFF}
""",
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
            id="supported_property_override_no_color_mode",
        ),
        pytest.param(
            """
from homeassistant.components.light import ColorMode, LightEntity

class MyLight(LightEntity):
    _attr_supported_color_modes = {ColorMode.HS}
    _attr_color_mode = None
""",
            id="color_mode_explicitly_none_still_fires",
        ),
    ],
)
def test_fires(
    linter: UnittestLinter,
    checker: HassLightColorModeChecker,
    tmp_path: Path,
    code: str,
) -> None:
    """W7436 fires when supported color modes are set but no color mode is reported."""
    integration_dir = _make_integration(tmp_path)

    root_node = _parse(code, integration_dir)
    class_node = _find_class(root_node, "MyLight")
    with assert_adds_messages(linter, _expect(class_node)):
        walk_checker(linter, checker, root_node)


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
from homeassistant.components.light import ColorMode, LightEntity

class MyLight(LightEntity):
    _attr_color_mode = ColorMode.ONOFF
""",
            id="class_body_color_mode_no_supported",
        ),
        pytest.param(
            """
from homeassistant.components.light import ColorMode, LightEntity

class MyLight(LightEntity):
    def __init__(self, status) -> None:
        self._attr_color_mode = ColorMode.HS
""",
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
            id="color_mode_property_override_no_supported",
        ),
    ],
)
def test_missing_supported_fires(
    linter: UnittestLinter,
    checker: HassLightColorModeChecker,
    tmp_path: Path,
    code: str,
) -> None:
    """W7437 fires when a color mode is reported but no supported modes are set."""
    integration_dir = _make_integration(tmp_path)

    root_node = _parse(code, integration_dir)
    class_node = _find_class(root_node, "MyLight")
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
            id="color_mode_property_override",
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
from homeassistant.components.light import ColorMode, LightEntity

class MyLight(LightEntity):
    @property
    def is_on(self) -> bool:
        return True
""",
            id="no_supported_color_modes_set",
        ),
        pytest.param(
            """
from homeassistant.components.light import ColorMode, LightEntity

class MyLight(LightEntity):
    _attr_supported_color_modes: set[ColorMode] | None = None
""",
            id="supported_explicitly_none",
        ),
    ],
)
def test_does_not_fire(
    linter: UnittestLinter,
    checker: HassLightColorModeChecker,
    tmp_path: Path,
    code: str,
) -> None:
    """W7436 does not fire when color mode is reported or supported modes are unset."""
    integration_dir = _make_integration(tmp_path)

    root_node = _parse(code, integration_dir)
    with assert_no_messages(linter):
        walk_checker(linter, checker, root_node)


def test_color_mode_from_base_class(
    linter: UnittestLinter,
    checker: HassLightColorModeChecker,
    tmp_path: Path,
) -> None:
    """No fire when a base supplies color_mode and the subclass supplies supported."""
    integration_dir = _make_integration(tmp_path)

    root_node = _parse(
        """
from homeassistant.components.light import ColorMode, LightEntity

class MyBaseLight(LightEntity):
    _attr_color_mode = ColorMode.HS

class MyLight(MyBaseLight):
    _attr_supported_color_modes = {ColorMode.HS}
""",
        integration_dir,
    )
    with assert_no_messages(linter):
        walk_checker(linter, checker, root_node)


def test_supported_from_base_subclass_supplies_color_mode(
    linter: UnittestLinter,
    checker: HassLightColorModeChecker,
    tmp_path: Path,
) -> None:
    """No fire when a base supplies supported and the subclass supplies color_mode.

    The base is exempt as a same-module ancestor; the concrete subclass
    resolves color_mode from its own body.
    """
    integration_dir = _make_integration(tmp_path)

    root_node = _parse(
        """
from homeassistant.components.light import ColorMode, LightEntity

class MyBaseLight(LightEntity):
    _attr_supported_color_modes = {ColorMode.HS}

class MyLight(MyBaseLight):
    _attr_color_mode = ColorMode.HS
""",
        integration_dir,
    )
    with assert_no_messages(linter):
        walk_checker(linter, checker, root_node)


def test_supported_from_base_subclass_missing_color_mode(
    linter: UnittestLinter,
    checker: HassLightColorModeChecker,
    tmp_path: Path,
) -> None:
    """Fire on the concrete subclass when supported is inherited but color_mode is absent.

    The abstract base that sets supported is exempt as a same-module
    ancestor; the concrete subclass is flagged.
    """
    integration_dir = _make_integration(tmp_path)

    root_node = _parse(
        """
from homeassistant.components.light import ColorMode, LightEntity

class MyBaseLight(LightEntity):
    _attr_supported_color_modes = {ColorMode.HS}

class MyLight(MyBaseLight):
    pass
""",
        integration_dir,
    )
    class_node = _find_class(root_node, "MyLight")
    with assert_adds_messages(linter, _expect(class_node)):
        walk_checker(linter, checker, root_node)


def test_color_mode_from_base_subclass_missing_supported(
    linter: UnittestLinter,
    checker: HassLightColorModeChecker,
    tmp_path: Path,
) -> None:
    """Fire W7437 on the concrete subclass when color_mode is inherited but supported is absent.

    The abstract base that sets color_mode is exempt as a same-module
    ancestor; the concrete subclass is flagged for the missing supported
    color modes.
    """
    integration_dir = _make_integration(tmp_path)

    root_node = _parse(
        """
from homeassistant.components.light import ColorMode, LightEntity

class MyBaseLight(LightEntity):
    _attr_color_mode = ColorMode.HS

class MyLight(MyBaseLight):
    pass
""",
        integration_dir,
    )
    class_node = _find_class(root_node, "MyLight")
    with assert_adds_messages(linter, _expect(class_node, _MISSING_SUPPORTED)):
        walk_checker(linter, checker, root_node)


def test_subclass_nullifies_inherited_color_mode(
    linter: UnittestLinter,
    checker: HassLightColorModeChecker,
    tmp_path: Path,
) -> None:
    """Fire W7436 when a subclass shadows an inherited color_mode with None.

    The base reports both, but the subclass resets `_attr_color_mode` to
    None, so at runtime the subclass reports no color mode.
    """
    integration_dir = _make_integration(tmp_path)

    root_node = _parse(
        """
from homeassistant.components.light import ColorMode, LightEntity

class MyBaseLight(LightEntity):
    _attr_supported_color_modes = {ColorMode.HS}
    _attr_color_mode = ColorMode.HS

class MyLight(MyBaseLight):
    _attr_color_mode = None
""",
        integration_dir,
    )
    class_node = _find_class(root_node, "MyLight")
    with assert_adds_messages(linter, _expect(class_node)):
        walk_checker(linter, checker, root_node)


def test_subclass_nullifies_inherited_supported(
    linter: UnittestLinter,
    checker: HassLightColorModeChecker,
    tmp_path: Path,
) -> None:
    """Fire W7437 when a subclass shadows inherited supported modes with None.

    The base reports both, but the subclass resets
    `_attr_supported_color_modes` to None, so at runtime the subclass sets
    no supported color modes.
    """
    integration_dir = _make_integration(tmp_path)

    root_node = _parse(
        """
from homeassistant.components.light import ColorMode, LightEntity

class MyBaseLight(LightEntity):
    _attr_supported_color_modes = {ColorMode.HS}
    _attr_color_mode = ColorMode.HS

class MyLight(MyBaseLight):
    _attr_supported_color_modes = None
""",
        integration_dir,
    )
    class_node = _find_class(root_node, "MyLight")
    with assert_adds_messages(linter, _expect(class_node, _MISSING_SUPPORTED)):
        walk_checker(linter, checker, root_node)


def test_subclass_reassigns_inherited_color_mode_via_init(
    linter: UnittestLinter,
    checker: HassLightColorModeChecker,
    tmp_path: Path,
) -> None:
    """No fire when a subclass nullifies the class attr but sets it in __init__.

    A runtime `self._attr_color_mode = ...` assignment wins over the
    class-body None, so the pair is still reported.
    """
    integration_dir = _make_integration(tmp_path)

    root_node = _parse(
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
        integration_dir,
    )
    with assert_no_messages(linter):
        walk_checker(linter, checker, root_node)


def test_two_subclasses_only_offender_fires(
    linter: UnittestLinter,
    checker: HassLightColorModeChecker,
    tmp_path: Path,
) -> None:
    """Mirror the xthings_cloud shape: only the class without color_mode fires."""
    integration_dir = _make_integration(tmp_path)

    root_node = _parse(
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
        integration_dir,
    )
    class_node = _find_class(root_node, "MySwitchLight")
    with assert_adds_messages(linter, _expect(class_node)):
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

"""Tests for the device info dict checker."""

import astroid
from pylint.testutils import UnittestLinter
from pylint_home_assistant.checkers.device_info_dict import DeviceInfoDictChecker
import pytest

from . import assert_no_messages, walk_checker

# Pre-load Entity so astroid can resolve it in parsed snippets.
astroid.MANAGER.ast_from_module_name("homeassistant.helpers.entity")

_ENTITY_IMPORT = "from homeassistant.helpers.entity import Entity"


@pytest.fixture(name="device_info_checker")
def device_info_checker_fixture(linter: UnittestLinter) -> DeviceInfoDictChecker:
    """Fixture to provide a device info dict checker."""
    return DeviceInfoDictChecker(linter)


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
class Entity:
    def __init__(self):
        self._attr_device_info = DeviceInfo(identifiers={("test", "1")})
""",
            id="device_info_in_init",
        ),
        pytest.param(
            """
class Entity:
    _attr_device_info = DeviceInfo(identifiers={("test", "1")})
""",
            id="device_info_class_level",
        ),
        pytest.param(
            """
class Entity:
    def __init__(self):
        self._attr_device_info = None
""",
            id="none",
        ),
        pytest.param(
            """
class Entity:
    def __init__(self):
        self._attr_other = {"identifiers": {("test", "1")}}
""",
            id="other_attribute_dict",
        ),
        pytest.param(
            """
class Entity:
    def __init__(self):
        self._attr_device_info["connections"] = {("mac", "1")}
""",
            id="subscript_assignment",
        ),
        pytest.param(
            f"""
{_ENTITY_IMPORT}
class MyEntity(Entity):
    @property
    def device_info(self):
        return DeviceInfo(identifiers={{("test", "1")}})
""",
            id="property_device_info",
        ),
        pytest.param(
            f"""
{_ENTITY_IMPORT}
class MyEntity(Entity):
    @property
    def device_info(self):
        return None
""",
            id="property_none",
        ),
        pytest.param(
            f"""
{_ENTITY_IMPORT}
class MyEntity(Entity):
    @property
    def device_info(self):
        def helper():
            return {{"a": 1}}
        return DeviceInfo(identifiers=helper())
""",
            id="property_nested_function_dict",
        ),
        pytest.param(
            """
class NotAnEntity:
    @property
    def device_info(self):
        return {"a": 1}
""",
            id="property_not_entity",
        ),
        pytest.param(
            f"""
{_ENTITY_IMPORT}
class MyEntity(Entity):
    def other(self):
        return {{"a": 1}}
""",
            id="other_method_dict",
        ),
    ],
)
def test_no_warning(
    linter: UnittestLinter,
    device_info_checker: DeviceInfoDictChecker,
    code: str,
) -> None:
    """Test cases that should not trigger a warning."""
    root_node = astroid.parse(code, "homeassistant.components.test_integration.sensor")

    with assert_no_messages(linter):
        walk_checker(linter, device_info_checker, root_node)


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
class Entity:
    def __init__(self):
        self._attr_device_info = {"identifiers": {("test", "1")}}
""",
            id="dict_literal_in_init",
        ),
        pytest.param(
            """
class Entity:
    _attr_device_info = {"identifiers": {("test", "1")}}
""",
            id="dict_literal_class_level",
        ),
        pytest.param(
            """
class Entity:
    _attr_device_info: dict = {"identifiers": {("test", "1")}}
""",
            id="annotated_dict_literal",
        ),
        pytest.param(
            """
class Entity:
    def __init__(self):
        self._attr_device_info = dict(identifiers={("test", "1")})
""",
            id="dict_call",
        ),
        pytest.param(
            """
class Entity:
    def __init__(self):
        self._attr_device_info = {}
""",
            id="empty_dict",
        ),
        pytest.param(
            f"""
{_ENTITY_IMPORT}
class MyEntity(Entity):
    @property
    def device_info(self):
        return {{"identifiers": {{("test", "1")}}}}
""",
            id="property_dict_literal",
        ),
        pytest.param(
            f"""
{_ENTITY_IMPORT}
class MyEntity(Entity):
    @property
    def device_info(self):
        return dict(identifiers={{("test", "1")}})
""",
            id="property_dict_call",
        ),
    ],
)
def test_dict_flagged(
    linter: UnittestLinter,
    device_info_checker: DeviceInfoDictChecker,
    code: str,
) -> None:
    """Warning when _attr_device_info is set to a dict."""
    root_node = astroid.parse(code, "homeassistant.components.test_integration.sensor")

    walk_checker(linter, device_info_checker, root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "home-assistant-device-info-dict"


def test_property_multiple_returns_flagged(
    linter: UnittestLinter,
    device_info_checker: DeviceInfoDictChecker,
) -> None:
    """Each dict return in the property is flagged."""
    code = f"""
{_ENTITY_IMPORT}
class MyEntity(Entity):
    @property
    def device_info(self):
        if self.x:
            return {{"a": 1}}
        return {{"b": 2}}
"""
    root_node = astroid.parse(code, "homeassistant.components.test_integration.sensor")

    walk_checker(linter, device_info_checker, root_node)

    assert len(linter.release_messages()) == 2


def test_non_integration_module_ignored(
    linter: UnittestLinter,
    device_info_checker: DeviceInfoDictChecker,
) -> None:
    """No warning for code outside integration modules."""
    code = """
class Entity:
    def __init__(self):
        self._attr_device_info = {"identifiers": {("test", "1")}}
"""
    root_node = astroid.parse(code, "some_other.module")

    with assert_no_messages(linter):
        walk_checker(linter, device_info_checker, root_node)

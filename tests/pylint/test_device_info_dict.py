"""Tests for the device info dict checker."""

import astroid
from pylint.testutils import UnittestLinter
from pylint_home_assistant.checkers.device_info_dict import DeviceInfoDictChecker
import pytest

from . import assert_no_messages, walk_checker


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

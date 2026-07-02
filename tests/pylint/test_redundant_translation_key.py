"""Tests for the redundant translation_key checker."""

import json
from pathlib import Path

import astroid
from pylint.testutils import UnittestLinter
from pylint.utils.ast_walker import ASTWalker
from pylint_home_assistant.checkers.redundant_translation_key import (
    RedundantTranslationKeyChecker,
    clear_device_class_cache,
)
from pylint_home_assistant.helpers.translations import clear_translations_cache
import pytest

from . import assert_no_messages

_SENSOR_MODULE = astroid.MANAGER.ast_from_module_name("homeassistant.components.sensor")


@pytest.fixture(name="redundant_tk_checker")
def redundant_tk_checker_fixture(
    linter: UnittestLinter,
) -> RedundantTranslationKeyChecker:
    """Fixture to provide a redundant translation_key checker."""
    clear_translations_cache()
    clear_device_class_cache()
    return RedundantTranslationKeyChecker(linter)


def _make_integration(
    tmp_path: Path,
    strings: dict | None = None,
    platform_strings: dict[str, dict] | None = None,
) -> Path:
    """Create a fake integration with strings.json and platform translations."""
    components_dir = tmp_path / "homeassistant" / "components"
    integration_dir = components_dir / "test_int"
    integration_dir.mkdir(parents=True)
    if strings is not None:
        (integration_dir / "strings.json").write_text(json.dumps(strings))

    if platform_strings is not None:
        for platform, data in platform_strings.items():
            platform_dir = components_dir / platform
            platform_dir.mkdir(parents=True, exist_ok=True)
            (platform_dir / "strings.json").write_text(json.dumps(data))

    return integration_dir


_PLATFORM_SENSOR_STRINGS = {
    "entity_component": {
        "power": {"name": "Power"},
        "temperature": {"name": "Temperature"},
        "battery": {"name": "Battery"},
    }
}


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
from homeassistant.components.sensor import SensorEntityDescription, SensorDeviceClass

SensorEntityDescription(
    key="power",
    device_class=SensorDeviceClass.POWER,
)
""",
            id="no_translation_key",
        ),
        pytest.param(
            """
from homeassistant.components.sensor import SensorEntityDescription, SensorDeviceClass

SensorEntityDescription(
    key="device_temp",
    translation_key="device_temperature",
    device_class=SensorDeviceClass.TEMPERATURE,
)
""",
            id="different_translation",
        ),
        pytest.param(
            """
from homeassistant.components.sensor import SensorEntityDescription, SensorDeviceClass

SensorEntityDescription(
    key="watt_hours",
    translation_key="energy_consumption",
    device_class=SensorDeviceClass.POWER,
)
""",
            id="translation_key_not_in_strings",
        ),
        pytest.param(
            """
from homeassistant.components.sensor import SensorEntityDescription

SensorEntityDescription(
    key="custom",
    translation_key="power",
)
""",
            id="no_device_class",
        ),
    ],
)
def test_no_warning(
    linter: UnittestLinter,
    redundant_tk_checker: RedundantTranslationKeyChecker,
    tmp_path: Path,
    code: str,
) -> None:
    """Test cases that should not trigger a warning."""
    integration_dir = _make_integration(
        tmp_path,
        strings={
            "entity": {
                "sensor": {
                    "device_temperature": {"name": "Device temperature"},
                }
            }
        },
        platform_strings={"sensor": _PLATFORM_SENSOR_STRINGS},
    )

    root_node = astroid.parse(code, "homeassistant.components.test_int.sensor")
    root_node.file = str(integration_dir / "sensor.py")

    walker = ASTWalker(linter)
    walker.add_checker(redundant_tk_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


def test_redundant_translation_key_flagged(
    linter: UnittestLinter,
    redundant_tk_checker: RedundantTranslationKeyChecker,
    tmp_path: Path,
) -> None:
    """Warning when translation_key provides the same name as device_class."""
    integration_dir = _make_integration(
        tmp_path,
        strings={
            "entity": {
                "sensor": {
                    "power": {"name": "Power"},
                }
            }
        },
        platform_strings={"sensor": _PLATFORM_SENSOR_STRINGS},
    )

    code = """
from homeassistant.components.sensor import SensorEntityDescription, SensorDeviceClass

SensorEntityDescription(
    key="power",
    translation_key="power",
    device_class=SensorDeviceClass.POWER,
)
"""
    root_node = astroid.parse(code, "homeassistant.components.test_int.sensor")
    root_node.file = str(integration_dir / "sensor.py")

    walker = ASTWalker(linter)
    walker.add_checker(redundant_tk_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "home-assistant-redundant-translation-key"
    assert messages[0].args == ("power", "power", "Power")


def test_redundant_different_key_same_translation(
    linter: UnittestLinter,
    redundant_tk_checker: RedundantTranslationKeyChecker,
    tmp_path: Path,
) -> None:
    """Warning when translation_key differs from device_class but resolves to same name."""
    integration_dir = _make_integration(
        tmp_path,
        strings={
            "entity": {
                "sensor": {
                    "cell_temp": {"name": "Temperature"},
                }
            }
        },
        platform_strings={"sensor": _PLATFORM_SENSOR_STRINGS},
    )

    code = """
from homeassistant.components.sensor import SensorEntityDescription, SensorDeviceClass

SensorEntityDescription(
    key="cell_temp",
    translation_key="cell_temp",
    device_class=SensorDeviceClass.TEMPERATURE,
)
"""
    root_node = astroid.parse(code, "homeassistant.components.test_int.sensor")
    root_node.file = str(integration_dir / "sensor.py")

    walker = ASTWalker(linter)
    walker.add_checker(redundant_tk_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].args == ("cell_temp", "temperature", "Temperature")


def test_non_integration_module_ignored(
    linter: UnittestLinter,
    redundant_tk_checker: RedundantTranslationKeyChecker,
) -> None:
    """No warning for code outside integration modules."""
    code = """
from homeassistant.components.sensor import SensorEntityDescription, SensorDeviceClass

SensorEntityDescription(
    key="power",
    translation_key="power",
    device_class=SensorDeviceClass.POWER,
)
"""
    root_node = astroid.parse(code, "some_other.module")

    walker = ASTWalker(linter)
    walker.add_checker(redundant_tk_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


def test_non_platform_module_ignored(
    linter: UnittestLinter,
    redundant_tk_checker: RedundantTranslationKeyChecker,
    tmp_path: Path,
) -> None:
    """No warning for non-platform modules like __init__.py."""
    integration_dir = _make_integration(
        tmp_path,
        strings={
            "entity": {
                "sensor": {
                    "power": {"name": "Power"},
                }
            }
        },
        platform_strings={"sensor": _PLATFORM_SENSOR_STRINGS},
    )

    code = """
from homeassistant.components.sensor import SensorEntityDescription, SensorDeviceClass

SensorEntityDescription(
    key="power",
    translation_key="power",
    device_class=SensorDeviceClass.POWER,
)
"""
    root_node = astroid.parse(code, "homeassistant.components.test_int")
    root_node.file = str(integration_dir / "__init__.py")

    walker = ASTWalker(linter)
    walker.add_checker(redundant_tk_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


def test_multiple_descriptions_mixed(
    linter: UnittestLinter,
    redundant_tk_checker: RedundantTranslationKeyChecker,
    tmp_path: Path,
) -> None:
    """Only flag redundant ones in a list of descriptions."""
    integration_dir = _make_integration(
        tmp_path,
        strings={
            "entity": {
                "sensor": {
                    "power": {"name": "Power"},
                    "device_temp": {"name": "Device temperature"},
                    "battery": {"name": "Battery"},
                }
            }
        },
        platform_strings={"sensor": _PLATFORM_SENSOR_STRINGS},
    )

    code = """
from homeassistant.components.sensor import SensorEntityDescription, SensorDeviceClass

SENSORS = [
    SensorEntityDescription(
        key="power",
        translation_key="power",
        device_class=SensorDeviceClass.POWER,
    ),
    SensorEntityDescription(
        key="device_temp",
        translation_key="device_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="bat",
        translation_key="battery",
        device_class=SensorDeviceClass.BATTERY,
    ),
]
"""
    root_node = astroid.parse(code, "homeassistant.components.test_int.sensor")
    root_node.file = str(integration_dir / "sensor.py")

    walker = ASTWalker(linter)
    walker.add_checker(redundant_tk_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 2
    flagged_keys = {msg.args[0] for msg in messages}
    assert flagged_keys == {"power", "battery"}

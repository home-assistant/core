"""Tests for the redundant translation_key checker."""

import json
from pathlib import Path
from typing import Any

import astroid
from pylint.testutils import UnittestLinter
from pylint.utils.ast_walker import ASTWalker
from pylint_home_assistant.checkers.redundant_translation_key import (
    RedundantTranslationKeyChecker,
)
from pylint_home_assistant.helpers.icons import clear_icons_cache
from pylint_home_assistant.helpers.translations import clear_translations_cache
import pytest

from . import assert_no_messages

# Pre-load so astroid can resolve the sensor classes in parsed snippets
astroid.MANAGER.ast_from_module_name("homeassistant.components.sensor")

_SENSOR_STRINGS = {
    "entity_component": {
        "_": {"name": "Sensor"},
        "battery": {"name": "Battery"},
        "enum": {"name": "Enum"},
        "power": {"name": "Power"},
        "temperature": {"name": "Temperature"},
    }
}

_REMOVE_KEY = "remove the translation_key and its strings.json entry"
_REMOVE_NAME = (
    "remove only its name from strings.json, the key is also used for states, "
    "state attributes, icons or in code"
)


@pytest.fixture(name="checker")
def checker_fixture(linter: UnittestLinter) -> RedundantTranslationKeyChecker:
    """Fixture to provide a redundant translation_key checker."""
    clear_translations_cache()
    clear_icons_cache()
    return RedundantTranslationKeyChecker(linter)


def _walk(
    linter: UnittestLinter,
    checker: RedundantTranslationKeyChecker,
    tmp_path: Path,
    code: str,
    *,
    entity_strings: dict[str, Any],
    icons: dict[str, Any] | None = None,
    module: str = "sensor",
    code_reading_key: str | None = None,
) -> None:
    """Create a fake integration and walk *code* as one of its modules."""
    components_dir = tmp_path / "homeassistant" / "components"
    integration_dir = components_dir / "test_int"
    integration_dir.mkdir(parents=True)
    (integration_dir / "strings.json").write_text(
        json.dumps({"entity": entity_strings})
    )
    if code_reading_key is not None:
        (integration_dir / "entity.py").write_text(code_reading_key)
    if icons is not None:
        (integration_dir / "icons.json").write_text(json.dumps({"entity": icons}))
    (components_dir / "sensor").mkdir()
    (components_dir / "sensor" / "strings.json").write_text(json.dumps(_SENSOR_STRINGS))

    module_name = (
        "homeassistant.components.test_int"
        if module == "__init__"
        else f"homeassistant.components.test_int.{module}"
    )
    root_node = astroid.parse(code, module_name)
    root_node.file = str(integration_dir / f"{module}.py")

    walker = ASTWalker(linter)
    walker.add_checker(checker)
    walker.walk(root_node)


@pytest.mark.parametrize(
    ("code", "entity_strings", "module"),
    [
        pytest.param(
            """
from homeassistant.components.sensor import SensorDeviceClass, SensorEntityDescription

SensorEntityDescription(key="power", device_class=SensorDeviceClass.POWER)
""",
            {"sensor": {"power": {"name": "Power"}}},
            "sensor",
            id="no_translation_key",
        ),
        pytest.param(
            """
from homeassistant.components.sensor import SensorEntityDescription

SensorEntityDescription(key="power", translation_key="power")
""",
            {"sensor": {"power": {"name": "Power"}}},
            "sensor",
            id="no_device_class",
        ),
        pytest.param(
            """
from homeassistant.components.sensor import SensorDeviceClass, SensorEntityDescription

SensorEntityDescription(
    key="device_temperature",
    translation_key="device_temperature",
    device_class=SensorDeviceClass.TEMPERATURE,
)
""",
            {"sensor": {"device_temperature": {"name": "Device temperature"}}},
            "sensor",
            id="different_name",
        ),
        pytest.param(
            """
from homeassistant.components.sensor import SensorDeviceClass, SensorEntityDescription

SensorEntityDescription(
    key="power",
    translation_key="power",
    device_class=SensorDeviceClass.POWER,
)
""",
            {"sensor": {}},
            "sensor",
            id="translation_key_not_in_strings",
        ),
        pytest.param(
            """
from homeassistant.components.sensor import SensorDeviceClass, SensorEntityDescription

SensorEntityDescription(
    key="mode",
    translation_key="enum",
    device_class=SensorDeviceClass.ENUM,
)
""",
            {"sensor": {"enum": {"name": "Enum"}}},
            "sensor",
            id="enum_sensor",
        ),
        pytest.param(
            """
from homeassistant.components.sensor import SensorDeviceClass, SensorEntityDescription

SensorEntityDescription(
    key="power",
    translation_key="power",
    device_class=SensorDeviceClass.POWER,
)
""",
            {"switch": {"power": {"name": "Power"}}},
            "switch",
            id="platform_without_device_class_name",
        ),
        pytest.param(
            """
from homeassistant.components.sensor import SensorDeviceClass, SensorEntityDescription

SensorEntityDescription(
    key="power",
    translation_key="power",
    device_class=SensorDeviceClass.POWER,
)
""",
            {"sensor": {"power": {"name": "Power"}}},
            "__init__",
            id="not_a_platform_module",
        ),
        pytest.param(
            """
def build(**kwargs):
    return kwargs

build(translation_key="power", device_class="power")
""",
            {"sensor": {"power": {"name": "Power"}}},
            "sensor",
            id="not_an_entity_description",
        ),
    ],
)
def test_no_warning(
    linter: UnittestLinter,
    checker: RedundantTranslationKeyChecker,
    tmp_path: Path,
    code: str,
    entity_strings: dict[str, Any],
    module: str,
) -> None:
    """Test cases that should not trigger a warning."""
    with assert_no_messages(linter):
        _walk(
            linter,
            checker,
            tmp_path,
            code,
            entity_strings=entity_strings,
            module=module,
        )


@pytest.mark.parametrize(
    ("code", "entity_strings", "icons", "expected_args"),
    [
        pytest.param(
            """
from homeassistant.components.sensor import SensorDeviceClass, SensorEntityDescription

SensorEntityDescription(
    key="power",
    translation_key="power",
    device_class=SensorDeviceClass.POWER,
)
""",
            {"sensor": {"power": {"name": "Power"}}},
            None,
            ("power", "power", "Power", _REMOVE_KEY),
            id="same_key",
        ),
        pytest.param(
            """
from homeassistant.components.sensor import SensorDeviceClass, SensorEntityDescription

SensorEntityDescription(
    key="cell_temp",
    translation_key="cell_temp",
    device_class=SensorDeviceClass.TEMPERATURE,
)
""",
            {"sensor": {"cell_temp": {"name": "Temperature"}}},
            None,
            ("cell_temp", "temperature", "Temperature", _REMOVE_KEY),
            id="different_key_same_name",
        ),
        pytest.param(
            """
from homeassistant.components.sensor import SensorEntityDescription

SensorEntityDescription(key="power", translation_key="power", device_class="power")
""",
            {"sensor": {"power": {"name": "Power"}}},
            None,
            ("power", "power", "Power", _REMOVE_KEY),
            id="string_device_class",
        ),
        pytest.param(
            """
from homeassistant.components.sensor import SensorDeviceClass, SensorEntityDescription

SensorEntityDescription(
    key="power",
    translation_key="power",
    device_class=SensorDeviceClass.POWER,
)
""",
            {
                "sensor": {
                    "power": {
                        "name": "[%key:component::sensor::entity_component::power::name%]"
                    }
                }
            },
            None,
            ("power", "power", "Power", _REMOVE_KEY),
            id="key_reference",
        ),
        pytest.param(
            """
from homeassistant.components.sensor import SensorDeviceClass, SensorEntityDescription

SensorEntityDescription(
    key="battery",
    translation_key="battery",
    device_class=SensorDeviceClass.BATTERY,
)
""",
            {
                "sensor": {
                    "battery": {
                        "name": "Battery",
                        "state_attributes": {"cells": {"name": "Cells"}},
                    }
                }
            },
            None,
            ("battery", "battery", "Battery", _REMOVE_NAME),
            id="key_with_state_attributes",
        ),
        pytest.param(
            """
from homeassistant.components.sensor import SensorDeviceClass, SensorEntityDescription

SensorEntityDescription(
    key="battery",
    translation_key="battery",
    device_class=SensorDeviceClass.BATTERY,
)
""",
            {"sensor": {"battery": {"name": "Battery"}}},
            {"sensor": {"battery": {"default": "mdi:battery-heart"}}},
            ("battery", "battery", "Battery", _REMOVE_NAME),
            id="key_with_icon",
        ),
    ],
)
def test_warning(
    linter: UnittestLinter,
    checker: RedundantTranslationKeyChecker,
    tmp_path: Path,
    code: str,
    entity_strings: dict[str, Any],
    icons: dict[str, Any] | None,
    expected_args: tuple[str, str, str, str],
) -> None:
    """Test cases that should trigger a warning."""
    _walk(linter, checker, tmp_path, code, entity_strings=entity_strings, icons=icons)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "home-assistant-redundant-translation-key"
    assert messages[0].args == expected_args


def test_code_reads_translation_key(
    linter: UnittestLinter,
    checker: RedundantTranslationKeyChecker,
    tmp_path: Path,
) -> None:
    """Test only the name should go when the integration reads the key."""
    code = """
from homeassistant.components.sensor import SensorDeviceClass, SensorEntityDescription

SensorEntityDescription(
    key="power",
    translation_key="power",
    device_class=SensorDeviceClass.POWER,
)
"""
    _walk(
        linter,
        checker,
        tmp_path,
        code,
        entity_strings={"sensor": {"power": {"name": "Power"}}},
        code_reading_key=(
            "def numbered(description):\n"
            '    return f"{description.translation_key}_n"\n'
        ),
    )

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].args == ("power", "power", "Power", _REMOVE_NAME)


def test_only_redundant_descriptions_flagged(
    linter: UnittestLinter,
    checker: RedundantTranslationKeyChecker,
    tmp_path: Path,
) -> None:
    """Test only the redundant descriptions in a list are flagged."""
    code = """
from homeassistant.components.sensor import SensorDeviceClass, SensorEntityDescription

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
    _walk(
        linter,
        checker,
        tmp_path,
        code,
        entity_strings={
            "sensor": {
                "power": {"name": "Power"},
                "device_temp": {"name": "Device temperature"},
                "battery": {"name": "Battery"},
            }
        },
    )

    messages = linter.release_messages()
    assert {message.args[0] for message in messages} == {"power", "battery"}

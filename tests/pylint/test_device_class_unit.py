"""Tests for the device class unit checker."""

import astroid
from pylint.testutils import UnittestLinter
from pylint_home_assistant.checkers.device_class_unit import DeviceClassUnitChecker
import pytest

from . import assert_no_messages, walk_checker

# Pre-load so astroid can resolve the platform classes in parsed snippets
astroid.MANAGER.ast_from_module_name("homeassistant.components.number")
astroid.MANAGER.ast_from_module_name("homeassistant.components.sensor")

_IMPORTS = """
from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import UnitOfTemperature
"""

_INTEGRATION_MODULE = "homeassistant.components.test_integration.sensor"

RAW_STRING = "home-assistant-unit-raw-string"
INVALID_UNIT = "home-assistant-unit-invalid-for-device-class"


@pytest.fixture(name="checker")
def checker_fixture(linter: UnittestLinter) -> DeviceClassUnitChecker:
    """Fixture to provide a device class unit checker."""
    return DeviceClassUnitChecker(linter)


@pytest.mark.parametrize(
    ("code", "module"),
    [
        pytest.param(
            """
SensorEntityDescription(
    key="temperature",
    device_class=SensorDeviceClass.TEMPERATURE,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
)
""",
            _INTEGRATION_MODULE,
            id="unit_constant",
        ),
        pytest.param(
            """
SensorEntityDescription(
    key="lateral_acceleration",
    native_unit_of_measurement="g",
)
""",
            _INTEGRATION_MODULE,
            id="no_device_class",
        ),
        pytest.param(
            """
SensorEntityDescription(
    key="cost",
    device_class=SensorDeviceClass.MONETARY,
    native_unit_of_measurement="EUR",
)
""",
            _INTEGRATION_MODULE,
            id="device_class_accepts_any_unit",
        ),
        pytest.param(
            """
DEVICE_CLASS = SensorDeviceClass.TEMPERATURE
UNIT = "°C"

SensorEntityDescription(
    key="temperature",
    device_class=DEVICE_CLASS,
    native_unit_of_measurement=UNIT,
)
""",
            _INTEGRATION_MODULE,
            id="not_literals",
        ),
        pytest.param(
            """
dict(
    device_class=SensorDeviceClass.TEMPERATURE,
    native_unit_of_measurement="°C",
)
""",
            _INTEGRATION_MODULE,
            id="not_entity_description",
        ),
        pytest.param(
            """
class Settings:
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = "°C"
""",
            _INTEGRATION_MODULE,
            id="not_entity_class",
        ),
        pytest.param(
            """
SensorEntityDescription(
    key="temperature",
    device_class=SensorDeviceClass.TEMPERATURE,
    native_unit_of_measurement="°C",
)
""",
            "tests.components.test_integration.test_sensor",
            id="not_integration_module",
        ),
    ],
)
def test_no_warning(
    linter: UnittestLinter,
    checker: DeviceClassUnitChecker,
    code: str,
    module: str,
) -> None:
    """Test cases that should not trigger a warning."""
    root_node = astroid.parse(_IMPORTS + code, module)

    with assert_no_messages(linter):
        walk_checker(linter, checker, root_node)


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        pytest.param(
            """
SensorEntityDescription(
    key="temperature",
    device_class=SensorDeviceClass.TEMPERATURE,
    native_unit_of_measurement="°C",
)
""",
            [
                (
                    RAW_STRING,
                    (
                        "UnitOfTemperature.CELSIUS",
                        "°C",
                        "native_unit_of_measurement",
                    ),
                )
            ],
            id="enum_member",
        ),
        pytest.param(
            """
SensorEntityDescription(
    key="battery",
    device_class=SensorDeviceClass.BATTERY,
    native_unit_of_measurement="%",
)
""",
            [
                (
                    RAW_STRING,
                    ("UnitOfRatio.PERCENTAGE", "%", "native_unit_of_measurement"),
                )
            ],
            id="percentage",
        ),
        pytest.param(
            """
SensorEntityDescription(
    key="wind_direction",
    device_class=SensorDeviceClass.WIND_DIRECTION,
    native_unit_of_measurement="°",
)
""",
            [(RAW_STRING, ("DEGREE", "°", "native_unit_of_measurement"))],
            id="plain_constant",
        ),
        pytest.param(
            """
SensorEntityDescription(
    key="upload",
    device_class=SensorDeviceClass.DATA_SIZE,
    native_unit_of_measurement="B",
    suggested_unit_of_measurement="TiB",
)
""",
            [
                (
                    RAW_STRING,
                    ("UnitOfInformation.BYTES", "B", "native_unit_of_measurement"),
                ),
                (
                    RAW_STRING,
                    (
                        "UnitOfInformation.TEBIBYTES",
                        "TiB",
                        "suggested_unit_of_measurement",
                    ),
                ),
            ],
            id="whole_enum_and_suggested_unit",
        ),
        pytest.param(
            """
NumberEntityDescription(
    key="duration",
    device_class=NumberDeviceClass.DURATION,
    native_unit_of_measurement="min",
)
""",
            [
                (
                    RAW_STRING,
                    ("UnitOfTime.MINUTES", "min", "native_unit_of_measurement"),
                )
            ],
            id="number",
        ),
        pytest.param(
            """
class TemperatureSensor(SensorEntity):
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = "°C"
""",
            [
                (
                    RAW_STRING,
                    (
                        "UnitOfTemperature.CELSIUS",
                        "°C",
                        "native_unit_of_measurement",
                    ),
                )
            ],
            id="entity_class",
        ),
        pytest.param(
            """
SensorEntityDescription(
    key="temperature",
    device_class=SensorDeviceClass.TEMPERATURE,
    native_unit_of_measurement="min",
)
""",
            [(INVALID_UNIT, ("min", "SensorDeviceClass.TEMPERATURE"))],
            id="invalid_unit",
        ),
        pytest.param(
            """
SensorEntityDescription(
    key="aqi",
    device_class=SensorDeviceClass.AQI,
    native_unit_of_measurement="AQI",
)
""",
            [(INVALID_UNIT, ("AQI", "SensorDeviceClass.AQI"))],
            id="device_class_without_unit",
        ),
        pytest.param(
            """
class HumidityNumber(NumberEntity):
    _attr_device_class = NumberDeviceClass.HUMIDITY
    _attr_native_unit_of_measurement = "g"
""",
            [(INVALID_UNIT, ("g", "NumberDeviceClass.HUMIDITY"))],
            id="invalid_unit_entity_class",
        ),
    ],
)
def test_warning(
    linter: UnittestLinter,
    checker: DeviceClassUnitChecker,
    code: str,
    expected: list[tuple[str, tuple[str, ...]]],
) -> None:
    """Test cases that should trigger a warning."""
    root_node = astroid.parse(_IMPORTS + code, _INTEGRATION_MODULE)
    walk_checker(linter, checker, root_node)

    messages = linter.release_messages()
    assert [(message.msg_id, message.args) for message in messages] == expected

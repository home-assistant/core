"""Test const module."""


from enum import Enum

import pytest

from homeassistant import const
from homeassistant.components import sensor

from tests.common import import_and_test_deprecated_constant_enum


def _create_tuples(
    value: Enum | list[Enum], constant_prefix: str
) -> list[tuple[Enum, str]]:
    result = []
    for enum in value:
        result.append((enum, constant_prefix))
    return result


@pytest.mark.parametrize(
    ("enum", "constant_prefix"),
    _create_tuples(const.EntityCategory, "ENTITY_CATEGORY_")
    + _create_tuples(
        [
            sensor.SensorDeviceClass.AQI,
            sensor.SensorDeviceClass.BATTERY,
            sensor.SensorDeviceClass.CO,
            sensor.SensorDeviceClass.CO2,
            sensor.SensorDeviceClass.CURRENT,
            sensor.SensorDeviceClass.DATE,
            sensor.SensorDeviceClass.ENERGY,
            sensor.SensorDeviceClass.FREQUENCY,
            sensor.SensorDeviceClass.GAS,
            sensor.SensorDeviceClass.HUMIDITY,
            sensor.SensorDeviceClass.ILLUMINANCE,
            sensor.SensorDeviceClass.MONETARY,
            sensor.SensorDeviceClass.NITROGEN_DIOXIDE,
            sensor.SensorDeviceClass.NITROGEN_MONOXIDE,
            sensor.SensorDeviceClass.NITROUS_OXIDE,
            sensor.SensorDeviceClass.OZONE,
            sensor.SensorDeviceClass.PM1,
            sensor.SensorDeviceClass.PM10,
            sensor.SensorDeviceClass.PM25,
            sensor.SensorDeviceClass.POWER_FACTOR,
            sensor.SensorDeviceClass.POWER,
            sensor.SensorDeviceClass.PRESSURE,
            sensor.SensorDeviceClass.SIGNAL_STRENGTH,
            sensor.SensorDeviceClass.SULPHUR_DIOXIDE,
            sensor.SensorDeviceClass.TEMPERATURE,
            sensor.SensorDeviceClass.TIMESTAMP,
            sensor.SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
            sensor.SensorDeviceClass.VOLTAGE,
        ],
        "DEVICE_CLASS_",
    ),
)
def test_deprecated_constants(
    caplog: pytest.LogCaptureFixture,
    enum: Enum,
    constant_prefix: str,
) -> None:
    """Test deprecated constants."""
    import_and_test_deprecated_constant_enum(
        caplog, const, enum, constant_prefix, "2025.1"
    )

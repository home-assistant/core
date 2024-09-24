"""Test const module."""

from enum import Enum

import pytest

from homeassistant import const
from homeassistant.components import lock, sensor

from .common import (
    help_test_all,
    import_and_test_deprecated_constant,
    import_and_test_deprecated_constant_enum,
)


def _create_tuples(
    value: type[Enum] | list[Enum], constant_prefix: str
) -> list[tuple[Enum, str]]:
    return [(enum, constant_prefix) for enum in value]


def test_all() -> None:
    """Test module.__all__ is correctly set."""
    help_test_all(const)


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
    )
    + _create_tuples(const.UnitOfApparentPower, "POWER_")
    + _create_tuples(const.UnitOfPower, "POWER_")
    + _create_tuples(
        [
            const.UnitOfEnergy.KILO_WATT_HOUR,
            const.UnitOfEnergy.MEGA_WATT_HOUR,
            const.UnitOfEnergy.WATT_HOUR,
        ],
        "ENERGY_",
    )
    + _create_tuples(const.UnitOfElectricCurrent, "ELECTRIC_CURRENT_")
    + _create_tuples(const.UnitOfElectricPotential, "ELECTRIC_POTENTIAL_")
    + _create_tuples(const.UnitOfTemperature, "TEMP_")
    + _create_tuples(const.UnitOfTime, "TIME_")
    + _create_tuples(
        [
            const.UnitOfLength.MILLIMETERS,
            const.UnitOfLength.CENTIMETERS,
            const.UnitOfLength.METERS,
            const.UnitOfLength.KILOMETERS,
            const.UnitOfLength.INCHES,
            const.UnitOfLength.FEET,
            const.UnitOfLength.MILES,
        ],
        "LENGTH_",
    )
    + _create_tuples(const.UnitOfFrequency, "FREQUENCY_")
    + _create_tuples(const.UnitOfPressure, "PRESSURE_")
    + _create_tuples(
        [
            const.UnitOfVolume.CUBIC_FEET,
            const.UnitOfVolume.CUBIC_METERS,
            const.UnitOfVolume.LITERS,
            const.UnitOfVolume.MILLILITERS,
            const.UnitOfVolume.GALLONS,
        ],
        "VOLUME_",
    )
    + _create_tuples(
        [
            const.UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
            const.UnitOfVolumeFlowRate.CUBIC_FEET_PER_MINUTE,
        ],
        "VOLUME_FLOW_RATE_",
    )
    + _create_tuples(
        [
            const.UnitOfMass.GRAMS,
            const.UnitOfMass.KILOGRAMS,
            const.UnitOfMass.MILLIGRAMS,
            const.UnitOfMass.MICROGRAMS,
            const.UnitOfMass.OUNCES,
            const.UnitOfMass.POUNDS,
        ],
        "MASS_",
    )
    + _create_tuples(const.UnitOfIrradiance, "IRRADIATION_")
    + _create_tuples(
        [
            const.UnitOfPrecipitationDepth.INCHES,
            const.UnitOfPrecipitationDepth.MILLIMETERS,
            const.UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
            const.UnitOfVolumetricFlux.INCHES_PER_HOUR,
        ],
        "PRECIPITATION_",
    )
    + _create_tuples(
        [
            const.UnitOfSpeed.FEET_PER_SECOND,
            const.UnitOfSpeed.METERS_PER_SECOND,
            const.UnitOfSpeed.KILOMETERS_PER_HOUR,
            const.UnitOfSpeed.KNOTS,
            const.UnitOfSpeed.MILES_PER_HOUR,
        ],
        "SPEED_",
    )
    + _create_tuples(
        [
            const.UnitOfVolumetricFlux.MILLIMETERS_PER_DAY,
            const.UnitOfVolumetricFlux.INCHES_PER_DAY,
            const.UnitOfVolumetricFlux.INCHES_PER_HOUR,
        ],
        "SPEED_",
    )
    + _create_tuples(const.UnitOfInformation, "DATA_")
    + _create_tuples(const.UnitOfDataRate, "DATA_RATE_"),
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


@pytest.mark.parametrize(
    ("replacement", "constant_name"),
    [
        (const.UnitOfLength.YARDS, "LENGTH_YARD"),
        (const.UnitOfSoundPressure.DECIBEL, "SOUND_PRESSURE_DB"),
        (const.UnitOfSoundPressure.WEIGHTED_DECIBEL_A, "SOUND_PRESSURE_WEIGHTED_DBA"),
        (const.UnitOfVolume.FLUID_OUNCES, "VOLUME_FLUID_OUNCE"),
    ],
)
def test_deprecated_constant_name_changes(
    caplog: pytest.LogCaptureFixture,
    replacement: Enum,
    constant_name: str,
) -> None:
    """Test deprecated constants, where the name is not the same as the enum value."""
    import_and_test_deprecated_constant(
        caplog,
        const,
        constant_name,
        f"{replacement.__class__.__name__}.{replacement.name}",
        replacement,
        "2025.1",
    )


def _create_tuples_lock_states(
    enum: type[Enum], constant_prefix: str, remove_in_version: str
) -> list[tuple[Enum, str]]:
    return [
        (enum_field, constant_prefix, remove_in_version)
        for enum_field in enum
        if enum_field
        not in [
            lock.LockState.OPEN,
            lock.LockState.OPENING,
        ]
    ]


@pytest.mark.parametrize(
    ("enum", "constant_prefix", "remove_in_version"),
    _create_tuples_lock_states(lock.LockState, "STATE_", "2025.10"),
)
def test_deprecated_constants_lock(
    caplog: pytest.LogCaptureFixture,
    enum: Enum,
    constant_prefix: str,
    remove_in_version: str,
) -> None:
    """Test deprecated constants."""
    import_and_test_deprecated_constant_enum(
        caplog, const, enum, constant_prefix, remove_in_version
    )

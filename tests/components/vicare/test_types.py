"""Test ViCare diagnostics."""

import pytest

from homeassistant.components.climate import PRESET_COMFORT, PRESET_SLEEP
from homeassistant.components.vicare.fan import VentilationMode
from homeassistant.components.vicare.types import HeatingProgram


@pytest.mark.parametrize(
    ("vicare_program", "expected_result"),
    [
        ("", None),
        (None, None),
        ("anything", None),
        (HeatingProgram.COMFORT, PRESET_COMFORT),
        (HeatingProgram.COMFORT_HEATING, PRESET_COMFORT),
    ],
)
async def test_heating_program_to_ha_preset(
    vicare_program: str | None,
    expected_result: str | None,
) -> None:
    """Testing ViCare HeatingProgram to HA Preset."""

    assert HeatingProgram.to_ha_preset(vicare_program) == expected_result


@pytest.mark.parametrize(
    ("ha_preset", "expected_result"),
    [
        ("", None),
        (None, None),
        ("anything", None),
        (PRESET_SLEEP, HeatingProgram.REDUCED),
    ],
)
async def test_ha_preset_to_heating_program(
    ha_preset: str | None,
    expected_result: str | None,
) -> None:
    """Testing HA Preset to ViCare HeatingProgram."""

    supported_programs = [
        HeatingProgram.COMFORT,
        HeatingProgram.ECO,
        HeatingProgram.NORMAL,
        HeatingProgram.REDUCED,
    ]
    assert (
        HeatingProgram.from_ha_preset(ha_preset, supported_programs) == expected_result
    )


async def test_ha_preset_to_heating_program_error() -> None:
    """Testing HA Preset to ViCare HeatingProgram."""

    supported_programs = [
        "test",
    ]
    assert (
        HeatingProgram.from_ha_preset(HeatingProgram.NORMAL, supported_programs) is None
    )


@pytest.mark.parametrize(
    ("vicare_mode", "expected_result"),
    [
        ("", None),
        (None, None),
        ("anything", None),
        ("sensorOverride", VentilationMode.SENSOR_OVERRIDE),
    ],
)
async def test_ventilation_mode_to_ha_mode(
    vicare_mode: str | None,
    expected_result: str | None,
) -> None:
    """Testing ViCare mode to VentilationMode."""

    assert VentilationMode.from_vicare_mode(vicare_mode) == expected_result


@pytest.mark.parametrize(
    ("ha_mode", "expected_result"),
    [
        ("", None),
        (None, None),
        ("anything", None),
        (VentilationMode.SENSOR_OVERRIDE, "sensorOverride"),
    ],
)
async def test_ha_mode_to_ventilation_mode(
    ha_mode: str | None,
    expected_result: str | None,
) -> None:
    """Testing VentilationMode to ViCare mode."""

    assert VentilationMode.to_vicare_mode(ha_mode) == expected_result

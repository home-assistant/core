"""Tests for the Aprilaire climate entity."""

import pytest

from homeassistant.components.climate import ATTR_TARGET_TEMP_STEP
from homeassistant.core import HomeAssistant
from homeassistant.util.unit_system import (
    METRIC_SYSTEM,
    US_CUSTOMARY_SYSTEM,
    UnitSystem,
)

from .test_init import _async_setup_integration


@pytest.mark.parametrize(
    ("unit_system", "expected_step"),
    [(METRIC_SYSTEM, 0.5), (US_CUSTOMARY_SYSTEM, 1.0)],
)
async def test_target_temperature_step(
    hass: HomeAssistant, unit_system: UnitSystem, expected_step: float
) -> None:
    """Test the step shown in the system's unit is 0.5 °C or 1 °F."""
    hass.config.units = unit_system
    await _async_setup_integration(hass)

    states = hass.states.async_all("climate")
    assert len(states) == 1
    assert states[0].attributes[ATTR_TARGET_TEMP_STEP] == expected_step

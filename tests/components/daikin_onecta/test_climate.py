"""Tests for the Daikin Onecta climate platform."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.daikin_onecta.climate import DaikinClimate


@pytest.mark.parametrize(
    ("last_update_success", "device_available", "expected"),
    [(True, True, True), (False, True, False), (True, False, False)],
)
def test_climate_availability(
    last_update_success: bool, device_available: bool, expected: bool
) -> None:
    """Climate entities require a successful update and an available device."""
    entity = object.__new__(DaikinClimate)
    entity.coordinator = MagicMock(last_update_success=last_update_success)
    entity._device = MagicMock(available=device_available)

    assert entity.available is expected

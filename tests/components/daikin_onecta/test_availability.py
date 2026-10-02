"""Test entity availability."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.daikin_onecta.binary_sensor import DaikinBinarySensor
from homeassistant.components.daikin_onecta.climate import DaikinClimate
from homeassistant.components.daikin_onecta.select import DaikinScheduleSelect
from homeassistant.components.daikin_onecta.sensor import (
    DaikinEnergySensor,
    DaikinValueSensor,
)
from homeassistant.components.daikin_onecta.switch import DaikinSwitch
from homeassistant.components.daikin_onecta.water_heater import DaikinWaterTank


@pytest.mark.parametrize(
    "entity_class",
    [
        DaikinBinarySensor,
        DaikinClimate,
        DaikinEnergySensor,
        DaikinScheduleSelect,
        DaikinValueSensor,
        DaikinSwitch,
        DaikinWaterTank,
    ],
)
@pytest.mark.parametrize(
    ("last_update_success", "device_available", "expected"),
    [
        (True, True, True),
        (False, True, False),
        (True, False, False),
    ],
)
def test_availability_requires_successful_update_and_available_device(
    entity_class,
    last_update_success,
    device_available,
    expected,
) -> None:
    """An entity is available only after a successful update from an available device."""
    entity = object.__new__(entity_class)
    entity.coordinator = MagicMock(last_update_success=last_update_success)
    device_attribute = "_device"
    setattr(entity, device_attribute, MagicMock(available=device_available))

    assert entity.available is expected

"""Tests for the Daikin Onecta climate platform."""

from unittest.mock import AsyncMock, MagicMock

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


async def test_set_temperature_updates_cached_setpoint() -> None:
    """Update the cached setpoint after a successful cloud write."""
    entity = object.__new__(DaikinClimate)
    device = MagicMock(id="device", name="Device")
    device.patch = AsyncMock(return_value=True)
    setpoint = MagicMock(value=20)
    object.__setattr__(entity, "_device", device)
    object.__setattr__(entity, "_embedded_id", "zone")
    object.__setattr__(entity, "_setpoint", "roomTemperature")
    object.__setattr__(entity, "_attr_target_temperature", 20)
    entity.operation_mode = MagicMock(return_value=MagicMock(value="heating"))
    entity.setpoint = MagicMock(return_value=setpoint)
    entity.async_write_ha_state = MagicMock()

    await entity.async_set_temperature(temperature=21)

    assert setpoint.value == 21

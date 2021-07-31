"""Tests for Dyson binary_sensor platform."""

from unittest.mock import patch

from libdyson import DEVICE_TYPE_360_EYE, Dyson360Eye
from libdyson.const import MessageType
from libdyson.dyson_vacuum_device import DysonVacuumDevice
import pytest

from homeassistant.components.binary_sensor import DEVICE_CLASS_BATTERY_CHARGING
from homeassistant.const import ATTR_DEVICE_CLASS, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry

from . import MODULE, NAME, SERIAL, get_base_device, setup_entry, update_device


@pytest.fixture
async def device(hass: HomeAssistant) -> DysonVacuumDevice:
    """Return mocked device."""
    device = get_base_device(Dyson360Eye, DEVICE_TYPE_360_EYE)
    device.is_charging = False
    with patch(f"{MODULE}._PLATFORMS", ["binary_sensor"]):
        await setup_entry(hass, device)
    return device


async def test_is_charging_sensor(
    hass: HomeAssistant,
    device: DysonVacuumDevice,
):
    """Test is charging sensor."""
    er = await entity_registry.async_get_registry(hass)
    entity_id = f"binary_sensor.{NAME}_battery_charging"
    state = hass.states.get(entity_id)
    assert state.name == f"{NAME} Battery Charging"
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_DEVICE_CLASS] == DEVICE_CLASS_BATTERY_CHARGING
    assert er.async_get(entity_id).unique_id == f"{SERIAL}-battery_charging"

    device.is_charging = True
    await update_device(hass, device, MessageType.STATE)
    assert hass.states.get(entity_id).state == STATE_ON

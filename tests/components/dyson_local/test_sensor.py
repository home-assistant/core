"""Tests for Dyson sensor platform."""

from unittest.mock import patch

from libdyson import DEVICE_TYPE_360_EYE, Dyson360Eye
from libdyson.const import MessageType
from libdyson.dyson_device import DysonDevice
import pytest

from homeassistant.components.dyson_local.sensor import SENSORS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry

from . import (
    MODULE,
    NAME,
    SERIAL,
    get_base_device,
    name_to_entity,
    setup_entry,
    update_device,
)


@pytest.fixture
async def device(hass: HomeAssistant) -> DysonDevice:
    """Return mocked device."""
    device = get_base_device(Dyson360Eye, DEVICE_TYPE_360_EYE)
    device.battery_level = 80
    with patch(f"{MODULE}._PLATFORMS", ["sensor"]):
        await setup_entry(hass, device)
    return device


async def test_sensors(
    hass: HomeAssistant,
    device: DysonDevice,
):
    """Test sensor attributes."""
    er = await entity_registry.async_get_registry(hass)
    name, attributes = SENSORS["battery_level"]
    entity_id = f"sensor.{NAME}_{name_to_entity(name)}"
    state = hass.states.get(entity_id)
    assert state.name == f"{NAME} {name}"
    for attr, value in attributes.items():
        assert state.attributes[attr] == value
    assert er.async_get(entity_id).unique_id == f"{SERIAL}-battery_level"


async def test_360_eye(hass: HomeAssistant, device: Dyson360Eye):
    """Test 360 Eye sensors."""
    assert hass.states.get(f"sensor.{NAME}_battery_level").state == "80"
    device.battery_level = 40
    await update_device(hass, device, MessageType.STATE)
    assert hass.states.get(f"sensor.{NAME}_battery_level").state == "40"

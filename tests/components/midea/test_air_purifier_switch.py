"""Tests for Midea air purifier power switches."""

from collections.abc import Callable
from unittest.mock import patch

from midealocal.const import DeviceType
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant

from . import setup_integration
from .conftest import DummyDevice, entity_entries
from .const import TEST_DEVICE_ID


@pytest.mark.parametrize("power", [False, True])
async def test_air_purifier_power_switch(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
    power: bool,
) -> None:
    """Test reported power and power services independently of the mode."""
    device = DummyDevice(DeviceType.FC, attributes={"power": power, "mode": "auto"})
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, config_entry, device)

    entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_power"]
    assert entity_entry.entity_category is None
    assert (state := hass.states.get(entity_entry.entity_id)) is not None
    assert state.state == (STATE_ON if power else STATE_OFF)

    device.calls.clear()
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_entry.entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert device.calls == [("set_attribute", "power", True)]
    assert device.attributes["mode"] == "auto"
    assert (state := hass.states.get(entity_entry.entity_id)) is not None
    assert state.state == STATE_ON

    device.calls.clear()
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_entry.entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert device.calls == [("set_attribute", "power", False)]
    assert device.attributes["mode"] == "auto"
    assert (state := hass.states.get(entity_entry.entity_id)) is not None
    assert state.state == STATE_OFF


async def test_air_purifier_power_switch_requires_attribute(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
) -> None:
    """Test a purifier without a power attribute gets no power switch."""
    device = DummyDevice(DeviceType.FC, attributes={"mode": "auto"})
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, config_entry, device)

    assert f"{TEST_DEVICE_ID}_power" not in entity_entries(hass, config_entry)

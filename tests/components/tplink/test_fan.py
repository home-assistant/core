"""Tests for fan platform."""

from __future__ import annotations

from freezegun.api import FrozenDateTimeFactory
from kasa import Device, Module
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.fan import (
    ATTR_PERCENTAGE,
    DOMAIN as FAN_DOMAIN,
    SERVICE_SET_PERCENTAGE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import _mocked_device, setup_platform_for_device, snapshot_platform
from .const import DEVICE_ID

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_states(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test a fan state."""
    child_fan_1 = _mocked_device(
        modules=[Module.Fan], alias="my_fan_0", device_id=f"{DEVICE_ID}00"
    )
    child_fan_2 = _mocked_device(
        modules=[Module.Fan], alias="my_fan_1", device_id=f"{DEVICE_ID}01"
    )
    parent_device = _mocked_device(
        device_id=DEVICE_ID,
        alias="my_device",
        children=[child_fan_1, child_fan_2],
        modules=[Module.Fan],
        device_type=Device.Type.WallSwitch,
    )

    await setup_platform_for_device(
        hass, mock_config_entry, Platform.FAN, parent_device
    )
    await snapshot_platform(
        hass, entity_registry, device_registry, snapshot, mock_config_entry.entry_id
    )


async def test_fan_unique_id(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a fan unique id."""
    fan = _mocked_device(modules=[Module.Fan], alias="my_fan")
    await setup_platform_for_device(hass, mock_config_entry, Platform.FAN, fan)

    device_entries = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert device_entries
    entity_id = "fan.my_fan"

    assert entity_registry.async_get(entity_id).unique_id == DEVICE_ID


async def test_fan(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test fan functionality."""
    device = _mocked_device(modules=[Module.Fan], alias="my_fan")
    fan = device.modules[Module.Fan]
    fan.fan_speed_level = 0
    await setup_platform_for_device(hass, mock_config_entry, Platform.FAN, device)

    entity_id = "fan.my_fan"

    state = hass.states.get(entity_id)
    assert state.state == "off"

    await hass.services.async_call(
        FAN_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    fan.set_fan_speed_level.assert_called_once_with(4)
    fan.set_fan_speed_level.reset_mock()

    fan.fan_speed_level = 4

    freezer.tick(10)
    async_fire_time_changed(hass)

    await hass.async_block_till_done(wait_background_tasks=True)
    state = hass.states.get(entity_id)
    assert state.state == "on"

    await hass.services.async_call(
        FAN_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    fan.set_fan_speed_level.assert_called_once_with(0)
    fan.set_fan_speed_level.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_PERCENTAGE: 50},
        blocking=True,
    )
    fan.set_fan_speed_level.assert_called_once_with(2)
    fan.set_fan_speed_level.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PERCENTAGE: 25},
        blocking=True,
    )
    fan.set_fan_speed_level.assert_called_once_with(1)
    fan.set_fan_speed_level.reset_mock()


async def test_fan_child(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test child fans are added to parent device with the right ids."""
    child_fan_1 = _mocked_device(
        modules=[Module.Fan], alias="my_fan_0", device_id=f"{DEVICE_ID}00"
    )
    child_fan_2 = _mocked_device(
        modules=[Module.Fan], alias="my_fan_1", device_id=f"{DEVICE_ID}01"
    )
    parent_device = _mocked_device(
        device_id=DEVICE_ID,
        alias="my_device",
        children=[child_fan_1, child_fan_2],
        modules=[Module.Fan],
        device_type=Device.Type.WallSwitch,
    )
    await setup_platform_for_device(
        hass, mock_config_entry, Platform.FAN, parent_device
    )

    entity_id = "fan.my_device"
    entity = entity_registry.async_get(entity_id)
    assert entity

    for fan_id in range(2):
        child_entity_id = f"fan.my_device_my_fan_{fan_id}"
        child_entity = entity_registry.async_get(child_entity_id)
        assert child_entity
        assert child_entity.unique_id == f"{DEVICE_ID}0{fan_id}"
        assert child_entity.device_id == entity.device_id

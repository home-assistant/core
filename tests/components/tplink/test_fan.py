"""Tests for fan platform."""

from __future__ import annotations

from datetime import timedelta

from kasa import Module

from homeassistant.components import tplink
from homeassistant.components.fan import (
    ATTR_PERCENTAGE,
    DOMAIN as FAN_DOMAIN,
    SERVICE_SET_PERCENTAGE,
)
from homeassistant.components.tplink.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from . import DEVICE_ID, MAC_ADDRESS, _mocked_device, _patch_connect, _patch_discovery

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_fan_unique_id(hass: HomeAssistant) -> None:
    """Test a fan unique id."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    fan = _mocked_device(modules=[Module.Fan], alias="my_fan")
    with _patch_discovery(device=fan), _patch_connect(device=fan):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "fan.my_fan"
    entity_registry = er.async_get(hass)
    assert entity_registry.async_get(entity_id).unique_id == DEVICE_ID


async def test_fan(hass: HomeAssistant) -> None:
    """Test a color fan and that all transitions are correctly passed."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    device = _mocked_device(modules=[Module.Fan], alias="my_fan")
    fan = device.modules[Module.Fan]
    fan.fan_speed_level = 0
    with _patch_discovery(device=device), _patch_connect(device=device):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done(wait_background_tasks=True)

    entity_id = "fan.my_fan"

    state = hass.states.get(entity_id)
    assert state.state == "off"

    await hass.services.async_call(
        FAN_DOMAIN, "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    fan.set_fan_speed_level.assert_called_once_with(4)
    fan.set_fan_speed_level.reset_mock()

    fan.fan_speed_level = 4
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == "on"

    await hass.services.async_call(
        FAN_DOMAIN, "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    fan.set_fan_speed_level.assert_called_once_with(0)
    fan.set_fan_speed_level.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        "turn_on",
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
    entity_registry: er.EntityRegistry,
) -> None:
    """Test child fans are added to parent device with the right ids."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)

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
    )

    with _patch_discovery(device=parent_device), _patch_connect(device=parent_device):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "fan.my_device"
    entity = entity_registry.async_get(entity_id)
    assert entity

    for fan_id in range(2):
        child_entity_id = f"fan.my_device_my_fan_{fan_id}"
        child_entity = entity_registry.async_get(child_entity_id)
        assert child_entity
        assert child_entity.unique_id == f"{DEVICE_ID}0{fan_id}"
        assert child_entity.device_id == entity.device_id

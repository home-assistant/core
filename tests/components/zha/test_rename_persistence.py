"""Test that renamed ZHA entity IDs persist after a restart."""

import asyncio
from collections.abc import Callable, Coroutine
from unittest.mock import patch

import pytest
from zigpy.device import Device
from zigpy.profiles import zha
from zigpy.zcl.clusters import general

from homeassistant.components.zha import DOMAIN
from homeassistant.components.zha.helpers import get_zha_gateway, get_zha_gateway_proxy
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import SIG_EP_INPUT, SIG_EP_OUTPUT, SIG_EP_PROFILE, SIG_EP_TYPE

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def required_platforms_only():
    """Only set up required platforms and base platforms."""
    with patch(
        "homeassistant.components.zha.PLATFORMS",
        (
            Platform.BINARY_SENSOR,
            Platform.BUTTON,
            Platform.DEVICE_TRACKER,
            Platform.LIGHT,
            Platform.NUMBER,
            Platform.SELECT,
            Platform.SENSOR,
            Platform.SWITCH,
            Platform.SIREN,
        ),
    ):
        yield


async def test_entity_id_rename_persists_after_restart(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., Device],
) -> None:
    """Test that a renamed entity keeps its new ID after config entry reload."""
    await setup_zha()
    gateway = get_zha_gateway(hass)

    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_INPUT: [
                    general.Basic.cluster_id,
                    general.OnOff.cluster_id,
                ],
                SIG_EP_OUTPUT: [],
                SIG_EP_TYPE: zha.DeviceType.ON_OFF_SWITCH,
                SIG_EP_PROFILE: zha.PROFILE_ID,
            }
        }
    )

    gateway.get_or_create_device(zigpy_device)
    await gateway.async_device_initialized(zigpy_device)
    await hass.async_block_till_done(wait_background_tasks=True)

    switch_entities = [
        entry
        for entry in entity_registry.entities.values()
        if entry.domain == "switch" and entry.platform == DOMAIN
    ]
    assert len(switch_entities) == 1, (
        f"Expected 1 switch entity, got {len(switch_entities)}"
    )

    switch_entity = switch_entities[0]
    old_entity_id = switch_entity.entity_id
    unique_id = switch_entity.unique_id

    new_entity_id = "switch.my_custom_renamed_switch"
    entity_registry.async_update_entity(old_entity_id, new_entity_id=new_entity_id)
    await hass.async_block_till_done()

    updated_entity = entity_registry.async_get(new_entity_id)
    assert updated_entity is not None, "Entity not found with new ID"
    assert updated_entity.unique_id == unique_id, "Unique ID changed after rename"

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    await hass.async_block_till_done()

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    entity_id_after_restart = entity_registry.async_get_entity_id(
        "switch", DOMAIN, unique_id
    )

    assert entity_id_after_restart == new_entity_id, (
        f"BUG: Entity ID reverted to '{entity_id_after_restart}' "
        f"instead of remaining '{new_entity_id}'"
    )


async def test_device_removal_cleans_up_entity_registry(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., Device],
) -> None:
    """Test that removing a device cleans up its entity registry entries."""
    await setup_zha()
    gateway_proxy = get_zha_gateway_proxy(hass)
    gateway = gateway_proxy.gateway

    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_INPUT: [
                    general.Basic.cluster_id,
                    general.OnOff.cluster_id,
                ],
                SIG_EP_OUTPUT: [],
                SIG_EP_TYPE: zha.DeviceType.ON_OFF_SWITCH,
                SIG_EP_PROFILE: zha.PROFILE_ID,
            }
        }
    )

    gateway.get_or_create_device(zigpy_device)
    await gateway.async_device_initialized(zigpy_device)
    await hass.async_block_till_done(wait_background_tasks=True)

    switch_entities = [
        entry
        for entry in entity_registry.entities.values()
        if entry.domain == "switch" and entry.platform == DOMAIN
    ]
    assert len(switch_entities) == 1
    switch_entity = switch_entities[0]
    unique_id = switch_entity.unique_id
    device_id = switch_entity.device_id

    new_entity_id = "switch.my_custom_name"
    entity_registry.async_update_entity(
        switch_entity.entity_id, new_entity_id=new_entity_id
    )
    await hass.async_block_till_done()

    gateway.device_removed(zigpy_device)

    await hass.async_block_till_done(wait_background_tasks=True)

    await asyncio.sleep(0.2)
    await hass.async_block_till_done(wait_background_tasks=True)

    entity_after_removal = entity_registry.async_get_entity_id(
        "switch", DOMAIN, unique_id
    )
    device_after_removal = device_registry.async_get(device_id)

    assert entity_after_removal is None, (
        f"Entity {entity_after_removal} still exists after device removal"
    )
    assert device_after_removal is None, "Device still exists after removal"

"""Tests for the Switch as X."""
from unittest.mock import patch

import pytest

from homeassistant.components.switch_as_x import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


@pytest.mark.parametrize("target_domain", ("light",))
async def test_config_entry_unregistered_uuid(hass: HomeAssistant, target_domain):
    """Test light switch setup from config entry with unknown entity registry id."""
    fake_uuid = "a266a680b608c32770e6c45bfe6b8411"

    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={"entity_id": fake_uuid, "target_domain": target_domain},
        title="ABC",
    )

    config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0


@pytest.mark.parametrize("target_domain", ("light",))
async def test_entity_registry_events(hass: HomeAssistant, target_domain):
    """Test entity registry events are tracked."""
    registry = er.async_get(hass)
    registry_entry = registry.async_get_or_create("switch", "test", "unique")
    switch_entity_id = registry_entry.entity_id
    hass.states.async_set(switch_entity_id, "on")

    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={"entity_id": registry_entry.id, "target_domain": target_domain},
        title="ABC",
    )

    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(f"{target_domain}.abc").state == "on"

    # Change entity_id
    new_switch_entity_id = f"{switch_entity_id}_new"
    registry.async_update_entity(switch_entity_id, new_entity_id=new_switch_entity_id)
    hass.states.async_set(new_switch_entity_id, "off")
    await hass.async_block_till_done()

    # Check tracking the new entity_id
    await hass.async_block_till_done()
    assert hass.states.get(f"{target_domain}.abc").state == "off"

    # The old entity_id should no longer be tracked
    hass.states.async_set(switch_entity_id, "on")
    await hass.async_block_till_done()
    assert hass.states.get(f"{target_domain}.abc").state == "off"

    # Check changing name does not reload the config entry
    with patch(
        "homeassistant.components.switch_as_x.async_unload_entry",
    ) as mock_setup_entry:
        registry.async_update_entity(new_switch_entity_id, name="New name")
        await hass.async_block_till_done()
    mock_setup_entry.assert_not_called()

    # Check removing the entity removes the config entry
    registry.async_remove(new_switch_entity_id)
    await hass.async_block_till_done()

    assert hass.states.get(f"{target_domain}.abc") is None
    assert registry.async_get(f"{target_domain}.abc") is None
    assert len(hass.config_entries.async_entries("switch_as_x")) == 0


@pytest.mark.parametrize("target_domain", ("light",))
async def test_device_registry_config_entry_1(hass: HomeAssistant, target_domain):
    """Test we add our config entry to the tracked switch's device."""
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    test_config_entry = MockConfigEntry()

    device_entry = device_registry.async_get_or_create(
        config_entry_id=test_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    switch_entity_entry = entity_registry.async_get_or_create(
        "switch",
        "test",
        "unique",
        config_entry=test_config_entry,
        device_id=device_entry.id,
    )
    # Add another config entry to the same device
    device_registry.async_update_device(
        device_entry.id, add_config_entry_id=MockConfigEntry().entry_id
    )

    switch_as_x_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={"entity_id": switch_entity_entry.id, "target_domain": target_domain},
        title="ABC",
    )

    switch_as_x_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(switch_as_x_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_entry = entity_registry.async_get(f"{target_domain}.abc")
    assert entity_entry.device_id == switch_entity_entry.device_id

    device_entry = device_registry.async_get(device_entry.id)
    assert switch_as_x_config_entry.entry_id in device_entry.config_entries

    # Remove the wrapped switch's config entry from the device
    device_registry.async_update_device(
        device_entry.id, remove_config_entry_id=test_config_entry.entry_id
    )
    await hass.async_block_till_done()
    device_entry = device_registry.async_get(device_entry.id)
    assert switch_as_x_config_entry.entry_id not in device_entry.config_entries


@pytest.mark.parametrize("target_domain", ("light",))
async def test_device_registry_config_entry_2(hass: HomeAssistant, target_domain):
    """Test we add our config entry to the tracked switch's device."""
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    test_config_entry = MockConfigEntry()

    device_entry = device_registry.async_get_or_create(
        config_entry_id=test_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    switch_entity_entry = entity_registry.async_get_or_create(
        "switch",
        "test",
        "unique",
        config_entry=test_config_entry,
        device_id=device_entry.id,
    )

    switch_as_x_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={"entity_id": switch_entity_entry.id, "target_domain": target_domain},
        title="ABC",
    )

    switch_as_x_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(switch_as_x_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_entry = entity_registry.async_get(f"{target_domain}.abc")
    assert entity_entry.device_id == switch_entity_entry.device_id

    device_entry = device_registry.async_get(device_entry.id)
    assert switch_as_x_config_entry.entry_id in device_entry.config_entries

    # Remove the wrapped switch from the device
    entity_registry.async_update_entity(switch_entity_entry.entity_id, device_id=None)
    await hass.async_block_till_done()
    device_entry = device_registry.async_get(device_entry.id)
    assert switch_as_x_config_entry.entry_id not in device_entry.config_entries

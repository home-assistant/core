"""Tests for the Switch as X."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from homeassistant.components.homeassistant import exposed_entities
from homeassistant.components.lock import LockState
from homeassistant.components.switch_as_x.config_flow import SwitchAsXConfigFlowHandler
from homeassistant.components.switch_as_x.const import (
    CONF_INVERT,
    CONF_TARGET_DOMAIN,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_ENTITY_ID,
    STATE_CLOSED,
    STATE_OFF,
    STATE_ON,
    STATE_OPEN,
    EntityCategory,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from . import PLATFORMS_TO_TEST

from tests.common import MockConfigEntry

EXPOSE_SETTINGS = {
    "cloud.alexa": True,
    "cloud.google_assistant": False,
    "conversation": True,
}


@pytest.mark.parametrize("target_domain", PLATFORMS_TO_TEST)
async def test_config_entry_unregistered_uuid(
    hass: HomeAssistant, target_domain: str
) -> None:
    """Test light switch setup from config entry with unknown entity registry id."""
    fake_uuid = "a266a680b608c32770e6c45bfe6b8411"

    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_ENTITY_ID: fake_uuid,
            CONF_INVERT: False,
            CONF_TARGET_DOMAIN: target_domain,
        },
        title="ABC",
        version=SwitchAsXConfigFlowHandler.VERSION,
        minor_version=SwitchAsXConfigFlowHandler.MINOR_VERSION,
    )

    config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0


@pytest.mark.parametrize(
    ("target_domain", "state_on", "state_off"),
    [
        (Platform.COVER, STATE_OPEN, STATE_CLOSED),
        (Platform.FAN, STATE_ON, STATE_OFF),
        (Platform.LIGHT, STATE_ON, STATE_OFF),
        (Platform.LOCK, LockState.UNLOCKED, LockState.LOCKED),
        (Platform.SIREN, STATE_ON, STATE_OFF),
        (Platform.VALVE, STATE_OPEN, STATE_CLOSED),
    ],
)
async def test_entity_registry_events(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    target_domain: str,
    state_on: str,
    state_off: str,
) -> None:
    """Test entity registry events are tracked."""
    registry_entry = entity_registry.async_get_or_create(
        "switch", "test", "unique", original_name="ABC"
    )
    switch_entity_id = registry_entry.entity_id
    hass.states.async_set(switch_entity_id, STATE_ON)

    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_ENTITY_ID: registry_entry.id,
            CONF_INVERT: False,
            CONF_TARGET_DOMAIN: target_domain,
        },
        title="ABC",
        version=SwitchAsXConfigFlowHandler.VERSION,
        minor_version=SwitchAsXConfigFlowHandler.MINOR_VERSION,
    )

    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(f"{target_domain}.abc").state == state_on

    # Change entity_id
    new_switch_entity_id = f"{switch_entity_id}_new"
    entity_registry.async_update_entity(
        switch_entity_id, new_entity_id=new_switch_entity_id
    )
    hass.states.async_set(new_switch_entity_id, STATE_OFF)
    await hass.async_block_till_done()

    # Check tracking the new entity_id
    await hass.async_block_till_done()
    assert hass.states.get(f"{target_domain}.abc").state == state_off

    # The old entity_id should no longer be tracked
    hass.states.async_set(switch_entity_id, STATE_ON)
    await hass.async_block_till_done()
    assert hass.states.get(f"{target_domain}.abc").state == state_off

    # Check changing name does not reload the config entry
    with patch(
        "homeassistant.components.switch_as_x.async_unload_entry",
    ) as mock_setup_entry:
        entity_registry.async_update_entity(new_switch_entity_id, name="New name")
        await hass.async_block_till_done()
    mock_setup_entry.assert_not_called()

    # Check removing the entity removes the config entry
    entity_registry.async_remove(new_switch_entity_id)
    await hass.async_block_till_done()

    assert hass.states.get(f"{target_domain}.abc") is None
    assert entity_registry.async_get(f"{target_domain}.abc") is None
    assert len(hass.config_entries.async_entries("switch_as_x")) == 0


@pytest.mark.parametrize("target_domain", PLATFORMS_TO_TEST)
async def test_device_registry_config_entry_1(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    target_domain: str,
) -> None:
    """Test we add our config entry to the tracked switch's device."""
    switch_config_entry = MockConfigEntry()
    switch_config_entry.add_to_hass(hass)

    device_entry = device_registry.async_get_or_create(
        config_entry_id=switch_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    switch_entity_entry = entity_registry.async_get_or_create(
        "switch",
        "test",
        "unique",
        config_entry=switch_config_entry,
        device_id=device_entry.id,
        original_name="ABC",
    )
    # Add another config entry to the same device
    other_config_entry = MockConfigEntry()
    other_config_entry.add_to_hass(hass)
    device_registry.async_update_device(
        device_entry.id, add_config_entry_id=other_config_entry.entry_id
    )

    switch_as_x_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_ENTITY_ID: switch_entity_entry.id,
            CONF_INVERT: False,
            CONF_TARGET_DOMAIN: target_domain,
        },
        title="ABC",
        version=SwitchAsXConfigFlowHandler.VERSION,
        minor_version=SwitchAsXConfigFlowHandler.MINOR_VERSION,
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
        device_entry.id, remove_config_entry_id=switch_config_entry.entry_id
    )
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    # Check that the switch_as_x config entry is removed from the device
    device_entry = device_registry.async_get(device_entry.id)
    assert switch_as_x_config_entry.entry_id not in device_entry.config_entries


@pytest.mark.parametrize("target_domain", PLATFORMS_TO_TEST)
async def test_device_registry_config_entry_2(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    target_domain: str,
) -> None:
    """Test we add our config entry to the tracked switch's device."""
    switch_config_entry = MockConfigEntry()
    switch_config_entry.add_to_hass(hass)

    device_entry = device_registry.async_get_or_create(
        config_entry_id=switch_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    switch_entity_entry = entity_registry.async_get_or_create(
        "switch",
        "test",
        "unique",
        config_entry=switch_config_entry,
        device_id=device_entry.id,
        original_name="ABC",
    )

    switch_as_x_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_ENTITY_ID: switch_entity_entry.id,
            CONF_INVERT: False,
            CONF_TARGET_DOMAIN: target_domain,
        },
        title="ABC",
        version=SwitchAsXConfigFlowHandler.VERSION,
        minor_version=SwitchAsXConfigFlowHandler.MINOR_VERSION,
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
    # Check that the switch_as_x config entry is removed from the device
    device_entry = device_registry.async_get(device_entry.id)
    assert switch_as_x_config_entry.entry_id not in device_entry.config_entries


@pytest.mark.parametrize("target_domain", PLATFORMS_TO_TEST)
async def test_config_entry_entity_id(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, target_domain: Platform
) -> None:
    """Test light switch setup from config entry with entity id."""
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_ENTITY_ID: "switch.abc",
            CONF_INVERT: False,
            CONF_TARGET_DOMAIN: target_domain,
        },
        title="ABC",
        version=SwitchAsXConfigFlowHandler.VERSION,
        minor_version=SwitchAsXConfigFlowHandler.MINOR_VERSION,
    )

    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert DOMAIN in hass.config.components

    state = hass.states.get(f"{target_domain}.abc")
    assert state
    assert state.state == "unavailable"
    # Name copied from config entry title
    assert state.name == "ABC"

    # Check the light is added to the entity registry
    entity_entry = entity_registry.async_get(f"{target_domain}.abc")
    assert entity_entry
    assert entity_entry.unique_id == config_entry.entry_id


@pytest.mark.parametrize("target_domain", PLATFORMS_TO_TEST)
async def test_config_entry_uuid(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, target_domain: Platform
) -> None:
    """Test light switch setup from config entry with entity registry id."""
    registry_entry = entity_registry.async_get_or_create(
        "switch", "test", "unique", original_name="ABC"
    )

    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_ENTITY_ID: registry_entry.id,
            CONF_INVERT: False,
            CONF_TARGET_DOMAIN: target_domain,
        },
        title="ABC",
        version=SwitchAsXConfigFlowHandler.VERSION,
        minor_version=SwitchAsXConfigFlowHandler.MINOR_VERSION,
    )

    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(f"{target_domain}.abc")


@pytest.mark.parametrize("target_domain", PLATFORMS_TO_TEST)
async def test_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    target_domain: Platform,
) -> None:
    """Test the entity is added to the wrapped entity's device."""
    test_config_entry = MockConfigEntry()
    test_config_entry.add_to_hass(hass)

    device_entry = device_registry.async_get_or_create(
        config_entry_id=test_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    switch_entity_entry = entity_registry.async_get_or_create(
        "switch", "test", "unique", device_id=device_entry.id, original_name="ABC"
    )

    switch_as_x_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_ENTITY_ID: switch_entity_entry.id,
            CONF_INVERT: False,
            CONF_TARGET_DOMAIN: target_domain,
        },
        title="ABC",
        version=SwitchAsXConfigFlowHandler.VERSION,
        minor_version=SwitchAsXConfigFlowHandler.MINOR_VERSION,
    )

    switch_as_x_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(switch_as_x_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_entry = entity_registry.async_get(f"{target_domain}.abc")
    assert entity_entry
    assert entity_entry.device_id == switch_entity_entry.device_id


@pytest.mark.parametrize("target_domain", PLATFORMS_TO_TEST)
async def test_setup_and_remove_config_entry(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    target_domain: Platform,
) -> None:
    """Test removing a config entry."""
    # Setup the config entry
    switch_as_x_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_ENTITY_ID: "switch.test",
            CONF_INVERT: False,
            CONF_TARGET_DOMAIN: target_domain,
        },
        title="ABC",
        version=SwitchAsXConfigFlowHandler.VERSION,
        minor_version=SwitchAsXConfigFlowHandler.MINOR_VERSION,
    )
    switch_as_x_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(switch_as_x_config_entry.entry_id)
    await hass.async_block_till_done()

    # Check the state and entity registry entry are present
    assert hass.states.get(f"{target_domain}.abc") is not None
    assert entity_registry.async_get(f"{target_domain}.abc") is not None

    # Remove the config entry
    assert await hass.config_entries.async_remove(switch_as_x_config_entry.entry_id)
    await hass.async_block_till_done()

    # Check the state and entity registry entry are removed
    assert hass.states.get(f"{target_domain}.abc") is None
    assert entity_registry.async_get(f"{target_domain}.abc") is None


@pytest.mark.parametrize(
    ("hidden_by_before", "hidden_by_after"),
    [
        (er.RegistryEntryHider.USER, er.RegistryEntryHider.USER),
        (er.RegistryEntryHider.INTEGRATION, None),
    ],
)
@pytest.mark.parametrize("target_domain", PLATFORMS_TO_TEST)
async def test_reset_hidden_by(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    target_domain: Platform,
    hidden_by_before: er.RegistryEntryHider | None,
    hidden_by_after: er.RegistryEntryHider,
) -> None:
    """Test removing a config entry resets hidden by."""
    switch_entity_entry = entity_registry.async_get_or_create(
        "switch", "test", "unique"
    )
    entity_registry.async_update_entity(
        switch_entity_entry.entity_id, hidden_by=hidden_by_before
    )

    # Add the config entry
    switch_as_x_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_ENTITY_ID: switch_entity_entry.id,
            CONF_INVERT: False,
            CONF_TARGET_DOMAIN: target_domain,
        },
        title="ABC",
        version=SwitchAsXConfigFlowHandler.VERSION,
        minor_version=SwitchAsXConfigFlowHandler.MINOR_VERSION,
    )
    switch_as_x_config_entry.add_to_hass(hass)

    # Remove the config entry
    assert await hass.config_entries.async_remove(switch_as_x_config_entry.entry_id)
    await hass.async_block_till_done()

    # Check hidden by is reset
    switch_entity_entry = entity_registry.async_get(switch_entity_entry.entity_id)
    assert switch_entity_entry.hidden_by == hidden_by_after


@pytest.mark.parametrize("target_domain", PLATFORMS_TO_TEST)
async def test_entity_category_inheritance(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    target_domain: Platform,
) -> None:
    """Test the entity category is inherited from source device."""
    switch_entity_entry = entity_registry.async_get_or_create(
        "switch", "test", "unique", original_name="ABC"
    )
    entity_registry.async_update_entity(
        switch_entity_entry.entity_id, entity_category=EntityCategory.CONFIG
    )

    # Add the config entry
    switch_as_x_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_ENTITY_ID: switch_entity_entry.id,
            CONF_INVERT: False,
            CONF_TARGET_DOMAIN: target_domain,
        },
        title="ABC",
        version=SwitchAsXConfigFlowHandler.VERSION,
        minor_version=SwitchAsXConfigFlowHandler.MINOR_VERSION,
    )
    switch_as_x_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(switch_as_x_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_entry = entity_registry.async_get(f"{target_domain}.abc")
    assert entity_entry
    assert entity_entry.device_id == switch_entity_entry.device_id
    assert entity_entry.entity_category is EntityCategory.CONFIG


@pytest.mark.parametrize("target_domain", PLATFORMS_TO_TEST)
async def test_entity_options(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    target_domain: Platform,
) -> None:
    """Test the source entity is stored as an entity option."""
    switch_entity_entry = entity_registry.async_get_or_create(
        "switch", "test", "unique", original_name="ABC"
    )
    entity_registry.async_update_entity(
        switch_entity_entry.entity_id, entity_category=EntityCategory.CONFIG
    )

    # Add the config entry
    switch_as_x_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_ENTITY_ID: switch_entity_entry.id,
            CONF_INVERT: False,
            CONF_TARGET_DOMAIN: target_domain,
        },
        title="ABC",
        version=SwitchAsXConfigFlowHandler.VERSION,
        minor_version=SwitchAsXConfigFlowHandler.MINOR_VERSION,
    )
    switch_as_x_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(switch_as_x_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_entry = entity_registry.async_get(f"{target_domain}.abc")
    assert entity_entry
    assert entity_entry.device_id == switch_entity_entry.device_id
    assert entity_entry.options == {
        DOMAIN: {"entity_id": switch_entity_entry.entity_id, "invert": False},
    }


@pytest.mark.parametrize("target_domain", PLATFORMS_TO_TEST)
async def test_entity_name(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    target_domain: Platform,
) -> None:
    """Test the source entity has entity_name set to True."""
    switch_config_entry = MockConfigEntry()
    switch_config_entry.add_to_hass(hass)

    device_entry = device_registry.async_get_or_create(
        config_entry_id=switch_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        name="Device name",
    )

    switch_entity_entry = entity_registry.async_get_or_create(
        "switch",
        "test",
        "unique",
        device_id=device_entry.id,
        has_entity_name=True,
    )
    switch_entity_entry = entity_registry.async_update_entity(
        switch_entity_entry.entity_id,
        config_entry_id=switch_config_entry.entry_id,
    )

    # Add the config entry
    switch_as_x_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_ENTITY_ID: switch_entity_entry.id,
            CONF_INVERT: False,
            CONF_TARGET_DOMAIN: target_domain,
        },
        title="ABC",
        version=SwitchAsXConfigFlowHandler.VERSION,
        minor_version=SwitchAsXConfigFlowHandler.MINOR_VERSION,
    )
    switch_as_x_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(switch_as_x_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_entry = entity_registry.async_get(f"{target_domain}.device_name")
    assert entity_entry
    assert entity_entry.device_id == switch_entity_entry.device_id
    assert entity_entry.has_entity_name is True
    assert entity_entry.name is None
    assert entity_entry.original_name is None
    assert entity_entry.options == {
        DOMAIN: {"entity_id": switch_entity_entry.entity_id, "invert": False}
    }


@pytest.mark.parametrize("target_domain", PLATFORMS_TO_TEST)
async def test_custom_name_1(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    target_domain: Platform,
) -> None:
    """Test the source entity has a custom name."""
    switch_config_entry = MockConfigEntry()
    switch_config_entry.add_to_hass(hass)

    device_entry = device_registry.async_get_or_create(
        config_entry_id=switch_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        name="Device name",
    )

    switch_entity_entry = entity_registry.async_get_or_create(
        "switch",
        "test",
        "unique",
        device_id=device_entry.id,
        has_entity_name=True,
        original_name="Original entity name",
    )
    switch_entity_entry = entity_registry.async_update_entity(
        switch_entity_entry.entity_id,
        config_entry_id=switch_config_entry.entry_id,
        name="Custom entity name",
    )

    # Add the config entry
    switch_as_x_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_ENTITY_ID: switch_entity_entry.id,
            CONF_INVERT: False,
            CONF_TARGET_DOMAIN: target_domain,
        },
        title="ABC",
        version=SwitchAsXConfigFlowHandler.VERSION,
        minor_version=SwitchAsXConfigFlowHandler.MINOR_VERSION,
    )
    switch_as_x_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(switch_as_x_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_entry = entity_registry.async_get(
        f"{target_domain}.device_name_original_entity_name"
    )
    assert entity_entry
    assert entity_entry.device_id == switch_entity_entry.device_id
    assert entity_entry.has_entity_name is True
    assert entity_entry.name == "Custom entity name"
    assert entity_entry.original_name == "Original entity name"
    assert entity_entry.options == {
        DOMAIN: {"entity_id": switch_entity_entry.entity_id, "invert": False}
    }


@pytest.mark.parametrize("target_domain", PLATFORMS_TO_TEST)
async def test_custom_name_2(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    target_domain: Platform,
) -> None:
    """Test the source entity has a custom name.

    This tests the custom name is only copied from the source device when the
    switch_as_x config entry is setup the first time.
    """
    switch_config_entry = MockConfigEntry()
    switch_config_entry.add_to_hass(hass)

    device_entry = device_registry.async_get_or_create(
        config_entry_id=switch_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        name="Device name",
    )

    switch_entity_entry = entity_registry.async_get_or_create(
        "switch",
        "test",
        "unique",
        device_id=device_entry.id,
        has_entity_name=True,
        original_name="Original entity name",
    )
    switch_entity_entry = entity_registry.async_update_entity(
        switch_entity_entry.entity_id,
        config_entry_id=switch_config_entry.entry_id,
        name="New custom entity name",
    )

    # Add the config entry
    switch_as_x_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_ENTITY_ID: switch_entity_entry.id,
            CONF_INVERT: False,
            CONF_TARGET_DOMAIN: target_domain,
        },
        title="ABC",
        version=SwitchAsXConfigFlowHandler.VERSION,
        minor_version=SwitchAsXConfigFlowHandler.MINOR_VERSION,
    )
    switch_as_x_config_entry.add_to_hass(hass)

    # Register the switch as x entity in the entity registry, this means
    # the entity has been setup before
    switch_as_x_entity_entry = entity_registry.async_get_or_create(
        target_domain,
        "switch_as_x",
        switch_as_x_config_entry.entry_id,
        suggested_object_id="device_name_original_entity_name",
    )
    switch_as_x_entity_entry = entity_registry.async_update_entity(
        switch_as_x_entity_entry.entity_id,
        config_entry_id=switch_config_entry.entry_id,
        name="Old custom entity name",
    )

    assert await hass.config_entries.async_setup(switch_as_x_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_entry = entity_registry.async_get(
        f"{target_domain}.device_name_original_entity_name"
    )
    assert entity_entry
    assert entity_entry.entity_id == switch_as_x_entity_entry.entity_id
    assert entity_entry.device_id == switch_entity_entry.device_id
    assert entity_entry.has_entity_name is True
    assert entity_entry.name == "Old custom entity name"
    assert entity_entry.original_name == "Original entity name"
    assert entity_entry.options == {
        DOMAIN: {"entity_id": switch_entity_entry.entity_id, "invert": False}
    }


@pytest.mark.parametrize("target_domain", PLATFORMS_TO_TEST)
async def test_import_expose_settings_1(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    target_domain: Platform,
) -> None:
    """Test importing assistant expose settings."""
    await async_setup_component(hass, "homeassistant", {})

    switch_entity_entry = entity_registry.async_get_or_create(
        "switch",
        "test",
        "unique",
        original_name="ABC",
    )
    for assistant, should_expose in EXPOSE_SETTINGS.items():
        exposed_entities.async_expose_entity(
            hass, assistant, switch_entity_entry.entity_id, should_expose
        )

    # Add the config entry
    switch_as_x_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_ENTITY_ID: switch_entity_entry.id,
            CONF_INVERT: False,
            CONF_TARGET_DOMAIN: target_domain,
        },
        title="ABC",
        version=SwitchAsXConfigFlowHandler.VERSION,
        minor_version=SwitchAsXConfigFlowHandler.MINOR_VERSION,
    )
    switch_as_x_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(switch_as_x_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_entry = entity_registry.async_get(f"{target_domain}.abc")
    assert entity_entry

    # Check switch_as_x expose settings were copied from the switch
    expose_settings = exposed_entities.async_get_entity_settings(
        hass, entity_entry.entity_id
    )
    for assistant, settings in EXPOSE_SETTINGS.items():
        assert expose_settings[assistant]["should_expose"] == settings

    # Check the switch is no longer exposed
    expose_settings = exposed_entities.async_get_entity_settings(
        hass, switch_entity_entry.entity_id
    )
    for assistant in EXPOSE_SETTINGS:
        assert expose_settings[assistant]["should_expose"] is False


@pytest.mark.parametrize("target_domain", PLATFORMS_TO_TEST)
async def test_import_expose_settings_2(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    target_domain: Platform,
) -> None:
    """Test importing assistant expose settings.

    This tests the expose settings are only copied from the source device when the
    switch_as_x config entry is setup the first time.
    """

    await async_setup_component(hass, "homeassistant", {})

    switch_entity_entry = entity_registry.async_get_or_create(
        "switch",
        "test",
        "unique",
        original_name="ABC",
    )
    for assistant, should_expose in EXPOSE_SETTINGS.items():
        exposed_entities.async_expose_entity(
            hass, assistant, switch_entity_entry.entity_id, should_expose
        )

    # Add the config entry
    switch_as_x_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_ENTITY_ID: switch_entity_entry.id,
            CONF_INVERT: False,
            CONF_TARGET_DOMAIN: target_domain,
        },
        title="ABC",
        version=SwitchAsXConfigFlowHandler.VERSION,
        minor_version=SwitchAsXConfigFlowHandler.MINOR_VERSION,
    )
    switch_as_x_config_entry.add_to_hass(hass)

    # Register the switch as x entity in the entity registry, this means
    # the entity has been setup before
    switch_as_x_entity_entry = entity_registry.async_get_or_create(
        target_domain,
        "switch_as_x",
        switch_as_x_config_entry.entry_id,
        suggested_object_id="abc",
    )
    for assistant, should_expose in EXPOSE_SETTINGS.items():
        exposed_entities.async_expose_entity(
            hass, assistant, switch_as_x_entity_entry.entity_id, not should_expose
        )

    assert await hass.config_entries.async_setup(switch_as_x_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_entry = entity_registry.async_get(f"{target_domain}.abc")
    assert entity_entry

    # Check switch_as_x expose settings were not copied from the switch
    expose_settings = exposed_entities.async_get_entity_settings(
        hass, entity_entry.entity_id
    )
    for assistant, settings in EXPOSE_SETTINGS.items():
        assert expose_settings[assistant]["should_expose"] is not settings

    # Check the switch settings were not modified
    expose_settings = exposed_entities.async_get_entity_settings(
        hass, switch_entity_entry.entity_id
    )
    for assistant, settings in EXPOSE_SETTINGS.items():
        assert expose_settings[assistant]["should_expose"] == settings


@pytest.mark.parametrize("target_domain", PLATFORMS_TO_TEST)
async def test_restore_expose_settings(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    target_domain: Platform,
) -> None:
    """Test removing a config entry restores assistant expose settings."""
    await async_setup_component(hass, "homeassistant", {})

    switch_entity_entry = entity_registry.async_get_or_create(
        "switch",
        "test",
        "unique",
        original_name="ABC",
    )

    # Add the config entry
    switch_as_x_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_ENTITY_ID: switch_entity_entry.id,
            CONF_INVERT: False,
            CONF_TARGET_DOMAIN: target_domain,
        },
        title="ABC",
        version=SwitchAsXConfigFlowHandler.VERSION,
        minor_version=SwitchAsXConfigFlowHandler.MINOR_VERSION,
    )
    switch_as_x_config_entry.add_to_hass(hass)

    # Register the switch as x entity
    switch_as_x_entity_entry = entity_registry.async_get_or_create(
        target_domain,
        "switch_as_x",
        switch_as_x_config_entry.entry_id,
        config_entry=switch_as_x_config_entry,
        suggested_object_id="abc",
    )
    for assistant, should_expose in EXPOSE_SETTINGS.items():
        exposed_entities.async_expose_entity(
            hass, assistant, switch_as_x_entity_entry.entity_id, should_expose
        )

    # Remove the config entry
    assert await hass.config_entries.async_remove(switch_as_x_config_entry.entry_id)
    await hass.async_block_till_done()

    # Check the switch expose settings were restored
    expose_settings = exposed_entities.async_get_entity_settings(
        hass, switch_entity_entry.entity_id
    )
    for assistant, settings in EXPOSE_SETTINGS.items():
        assert expose_settings[assistant]["should_expose"] == settings


@pytest.mark.parametrize("target_domain", PLATFORMS_TO_TEST)
async def test_migrate(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    target_domain: Platform,
) -> None:
    """Test migration."""
    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_ENTITY_ID: "switch.test",
            CONF_TARGET_DOMAIN: target_domain,
        },
        title="ABC",
        version=1,
        minor_version=1,
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check migration was successful and added invert option
    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.options == {
        CONF_ENTITY_ID: "switch.test",
        CONF_INVERT: False,
        CONF_TARGET_DOMAIN: target_domain,
    }
    assert config_entry.version == SwitchAsXConfigFlowHandler.VERSION
    assert config_entry.minor_version == SwitchAsXConfigFlowHandler.MINOR_VERSION

    # Check the state and entity registry entry are present
    assert hass.states.get(f"{target_domain}.abc") is not None
    assert entity_registry.async_get(f"{target_domain}.abc") is not None


@pytest.mark.parametrize("target_domain", PLATFORMS_TO_TEST)
async def test_migrate_from_future(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    target_domain: Platform,
) -> None:
    """Test migration."""
    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_ENTITY_ID: "switch.test",
            CONF_TARGET_DOMAIN: target_domain,
        },
        title="ABC",
        version=2,
        minor_version=1,
    )
    config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check migration was not successful and did not add invert option
    assert config_entry.state is ConfigEntryState.MIGRATION_ERROR
    assert config_entry.options == {
        CONF_ENTITY_ID: "switch.test",
        CONF_TARGET_DOMAIN: target_domain,
    }
    assert config_entry.version == 2
    assert config_entry.minor_version == 1

    # Check the state and entity registry entry are not present
    assert hass.states.get(f"{target_domain}.abc") is None
    assert entity_registry.async_get(f"{target_domain}.abc") is None

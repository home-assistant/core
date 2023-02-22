"""Tests for the Switch as X."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from homeassistant.components.switch_as_x.const import CONF_TARGET_DOMAIN, DOMAIN
from homeassistant.const import (
    CONF_ENTITY_ID,
    STATE_CLOSED,
    STATE_LOCKED,
    STATE_OFF,
    STATE_ON,
    STATE_OPEN,
    STATE_UNLOCKED,
    EntityCategory,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry

PLATFORMS_TO_TEST = (
    Platform.COVER,
    Platform.FAN,
    Platform.LIGHT,
    Platform.LOCK,
    Platform.SIREN,
)


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
            CONF_TARGET_DOMAIN: target_domain,
        },
        title="ABC",
    )

    config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0


@pytest.mark.parametrize(
    ("target_domain", "state_on", "state_off"),
    (
        (Platform.COVER, STATE_OPEN, STATE_CLOSED),
        (Platform.FAN, STATE_ON, STATE_OFF),
        (Platform.LIGHT, STATE_ON, STATE_OFF),
        (Platform.LOCK, STATE_UNLOCKED, STATE_LOCKED),
        (Platform.SIREN, STATE_ON, STATE_OFF),
    ),
)
async def test_entity_registry_events(
    hass: HomeAssistant, target_domain: str, state_on: str, state_off: str
) -> None:
    """Test entity registry events are tracked."""
    registry = er.async_get(hass)
    registry_entry = registry.async_get_or_create("switch", "test", "unique")
    switch_entity_id = registry_entry.entity_id
    hass.states.async_set(switch_entity_id, STATE_ON)

    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_ENTITY_ID: registry_entry.id,
            CONF_TARGET_DOMAIN: target_domain,
        },
        title="ABC",
    )

    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(f"{target_domain}.abc").state == state_on

    # Change entity_id
    new_switch_entity_id = f"{switch_entity_id}_new"
    registry.async_update_entity(switch_entity_id, new_entity_id=new_switch_entity_id)
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
        registry.async_update_entity(new_switch_entity_id, name="New name")
        await hass.async_block_till_done()
    mock_setup_entry.assert_not_called()

    # Check removing the entity removes the config entry
    registry.async_remove(new_switch_entity_id)
    await hass.async_block_till_done()

    assert hass.states.get(f"{target_domain}.abc") is None
    assert registry.async_get(f"{target_domain}.abc") is None
    assert len(hass.config_entries.async_entries("switch_as_x")) == 0


@pytest.mark.parametrize("target_domain", PLATFORMS_TO_TEST)
async def test_device_registry_config_entry_1(
    hass: HomeAssistant, target_domain: str
) -> None:
    """Test we add our config entry to the tracked switch's device."""
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    switch_config_entry = MockConfigEntry()

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
    )
    # Add another config entry to the same device
    device_registry.async_update_device(
        device_entry.id, add_config_entry_id=MockConfigEntry().entry_id
    )

    switch_as_x_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_ENTITY_ID: switch_entity_entry.id,
            CONF_TARGET_DOMAIN: target_domain,
        },
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
        device_entry.id, remove_config_entry_id=switch_config_entry.entry_id
    )
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    # Check that the switch_as_x config entry is removed from the device
    device_entry = device_registry.async_get(device_entry.id)
    assert switch_as_x_config_entry.entry_id not in device_entry.config_entries


@pytest.mark.parametrize("target_domain", PLATFORMS_TO_TEST)
async def test_device_registry_config_entry_2(
    hass: HomeAssistant, target_domain: str
) -> None:
    """Test we add our config entry to the tracked switch's device."""
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    switch_config_entry = MockConfigEntry()

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
    )

    switch_as_x_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_ENTITY_ID: switch_entity_entry.id,
            CONF_TARGET_DOMAIN: target_domain,
        },
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
    # Check that the switch_as_x config entry is removed from the device
    device_entry = device_registry.async_get(device_entry.id)
    assert switch_as_x_config_entry.entry_id not in device_entry.config_entries


@pytest.mark.parametrize("target_domain", PLATFORMS_TO_TEST)
async def test_config_entry_entity_id(
    hass: HomeAssistant, target_domain: Platform
) -> None:
    """Test light switch setup from config entry with entity id."""
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_ENTITY_ID: "switch.abc",
            CONF_TARGET_DOMAIN: target_domain,
        },
        title="ABC",
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
    registry = er.async_get(hass)
    entity_entry = registry.async_get(f"{target_domain}.abc")
    assert entity_entry
    assert entity_entry.unique_id == config_entry.entry_id


@pytest.mark.parametrize("target_domain", PLATFORMS_TO_TEST)
async def test_config_entry_uuid(hass: HomeAssistant, target_domain: Platform) -> None:
    """Test light switch setup from config entry with entity registry id."""
    registry = er.async_get(hass)
    registry_entry = registry.async_get_or_create("switch", "test", "unique")

    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_ENTITY_ID: registry_entry.id,
            CONF_TARGET_DOMAIN: target_domain,
        },
        title="ABC",
    )

    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(f"{target_domain}.abc")


@pytest.mark.parametrize("target_domain", PLATFORMS_TO_TEST)
async def test_device(hass: HomeAssistant, target_domain: Platform) -> None:
    """Test the entity is added to the wrapped entity's device."""
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    test_config_entry = MockConfigEntry()

    device_entry = device_registry.async_get_or_create(
        config_entry_id=test_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    switch_entity_entry = entity_registry.async_get_or_create(
        "switch", "test", "unique", device_id=device_entry.id
    )

    switch_as_x_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_ENTITY_ID: switch_entity_entry.id,
            CONF_TARGET_DOMAIN: target_domain,
        },
        title="ABC",
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
    target_domain: Platform,
) -> None:
    """Test removing a config entry."""
    registry = er.async_get(hass)

    # Setup the config entry
    switch_as_x_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_ENTITY_ID: "switch.test",
            CONF_TARGET_DOMAIN: target_domain,
        },
        title="ABC",
    )
    switch_as_x_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(switch_as_x_config_entry.entry_id)
    await hass.async_block_till_done()

    # Check the state and entity registry entry are present
    assert hass.states.get(f"{target_domain}.abc") is not None
    assert registry.async_get(f"{target_domain}.abc") is not None

    # Remove the config entry
    assert await hass.config_entries.async_remove(switch_as_x_config_entry.entry_id)
    await hass.async_block_till_done()

    # Check the state and entity registry entry are removed
    assert hass.states.get(f"{target_domain}.abc") is None
    assert registry.async_get(f"{target_domain}.abc") is None


@pytest.mark.parametrize(
    ("hidden_by_before", "hidden_by_after"),
    (
        (er.RegistryEntryHider.USER, er.RegistryEntryHider.USER),
        (er.RegistryEntryHider.INTEGRATION, None),
    ),
)
@pytest.mark.parametrize("target_domain", PLATFORMS_TO_TEST)
async def test_reset_hidden_by(
    hass: HomeAssistant,
    target_domain: Platform,
    hidden_by_before: er.RegistryEntryHider | None,
    hidden_by_after: er.RegistryEntryHider,
) -> None:
    """Test removing a config entry resets hidden by."""
    registry = er.async_get(hass)

    switch_entity_entry = registry.async_get_or_create("switch", "test", "unique")
    registry.async_update_entity(
        switch_entity_entry.entity_id, hidden_by=hidden_by_before
    )

    # Add the config entry
    switch_as_x_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_ENTITY_ID: switch_entity_entry.id,
            CONF_TARGET_DOMAIN: target_domain,
        },
        title="ABC",
    )
    switch_as_x_config_entry.add_to_hass(hass)

    # Remove the config entry
    assert await hass.config_entries.async_remove(switch_as_x_config_entry.entry_id)
    await hass.async_block_till_done()

    # Check hidden by is reset
    switch_entity_entry = registry.async_get(switch_entity_entry.entity_id)
    assert switch_entity_entry.hidden_by == hidden_by_after


@pytest.mark.parametrize("target_domain", PLATFORMS_TO_TEST)
async def test_entity_category_inheritance(
    hass: HomeAssistant,
    target_domain: Platform,
) -> None:
    """Test the entity category is inherited from source device."""
    registry = er.async_get(hass)

    switch_entity_entry = registry.async_get_or_create("switch", "test", "unique")
    registry.async_update_entity(
        switch_entity_entry.entity_id, entity_category=EntityCategory.CONFIG
    )

    # Add the config entry
    switch_as_x_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_ENTITY_ID: switch_entity_entry.id,
            CONF_TARGET_DOMAIN: target_domain,
        },
        title="ABC",
    )
    switch_as_x_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(switch_as_x_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_entry = registry.async_get(f"{target_domain}.abc")
    assert entity_entry
    assert entity_entry.device_id == switch_entity_entry.device_id
    assert entity_entry.entity_category is EntityCategory.CONFIG

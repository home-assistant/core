"""Tests for the Inverse helper."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from homeassistant.components.inverse.const import DOMAIN
from homeassistant.const import CONF_ENTITY_ID, STATE_OFF, STATE_ON, Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.event import async_track_entity_registry_updated_event

from tests.common import MockConfigEntry


def track_entity_registry_actions(
    hass: HomeAssistant, entity_id: str
) -> list[er.EventEntityRegistryUpdatedData]:
    """Track entity registry actions for an entity."""
    events: list[er.EventEntityRegistryUpdatedData] = []

    @callback
    def add_event(event: Event[er.EventEntityRegistryUpdatedData]) -> None:
        events.append(event.data)

    async_track_entity_registry_updated_event(hass, entity_id, add_event)
    return events


@pytest.mark.parametrize(
    "platform",
    [
        Platform.SWITCH,
        Platform.BINARY_SENSOR,
        Platform.LIGHT,
        Platform.FAN,
        Platform.SIREN,
        Platform.COVER,
        Platform.VALVE,
        Platform.LOCK,
    ],
)
async def test_config_entry_unregistered_uuid(
    hass: HomeAssistant, platform: Platform
) -> None:
    """Setup fails if entity registry id is unknown."""
    fake_uuid = "a266a680b608c32770e6c45bfe6b8411"

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_ENTITY_ID: fake_uuid},
        title="ABC",
    )
    config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 0


@pytest.mark.parametrize("platform", [Platform.LIGHT, Platform.FAN, Platform.SIREN])
async def test_entity_registry_events_toggle(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    platform: Platform,
) -> None:
    """Test registry id changes are tracked for toggle entities."""
    source = entity_registry.async_get_or_create(
        platform.value, "test", "unique", original_name="ABC"
    )
    hass.states.async_set(source.entity_id, STATE_ON)

    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_ENTITY_ID: source.entity_id}, title="ABC"
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    wrapped_id = f"{platform.value}.abc"
    assert hass.states.get(wrapped_id).state in {STATE_ON, STATE_OFF}

    # Change entity_id
    new_id = f"{source.entity_id}_new"
    entity_registry.async_update_entity(source.entity_id, new_entity_id=new_id)
    hass.states.async_set(new_id, STATE_OFF)
    await hass.async_block_till_done()

    # Verify tracking follows new id
    assert hass.states.get(wrapped_id).state in {STATE_ON, STATE_OFF}

    # Removing entity removes inverse config entry
    entity_registry.async_remove(new_id)
    await hass.async_block_till_done()
    assert hass.states.get(wrapped_id) is None
    assert len(hass.config_entries.async_entries(DOMAIN)) == 0


async def test_device_registry_config_entry(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """We add our config entry to the tracked entity's device, and react to removal."""
    src_entry = MockConfigEntry()
    src_entry.add_to_hass(hass)

    device_entry = device_registry.async_get_or_create(
        config_entry_id=src_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    source_entity_entry = entity_registry.async_get_or_create(
        "switch",
        "test",
        "unique",
        config_entry=src_entry,
        device_id=device_entry.id,
        original_name="ABC",
    )

    inv_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_ENTITY_ID: source_entity_entry.id}, title="ABC"
    )
    inv_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(inv_entry.entry_id)
    await hass.async_block_till_done()

    entity_entry = entity_registry.async_get("switch.abc")
    assert entity_entry.device_id == source_entity_entry.device_id

    events: list[str] = []

    def add_event(event: Event[er.EventEntityRegistryUpdatedData]) -> None:
        events.append(event.data["action"])

    async_track_entity_registry_updated_event(hass, entity_entry.entity_id, add_event)

    # Remove the wrapped source's config entry from the device, this should unload inverse
    with patch(
        "homeassistant.components.inverse.async_unload_entry",
        autospec=True,
    ) as mock_unload:
        device_registry.async_update_device(
            device_entry.id, remove_config_entry_id=src_entry.entry_id
        )
        await hass.async_block_till_done()
        await hass.async_block_till_done()
    mock_unload.assert_called_once()

    # Check the inverse config entry is removed
    assert inv_entry.entry_id not in hass.config_entries.async_entry_ids()

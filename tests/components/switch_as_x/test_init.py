"""Tests for the Switch as X."""
from unittest.mock import patch

import pytest

from homeassistant.components.switch_as_x import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

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
    await hass.async_block_till_done()

    assert hass.states.get(f"{target_domain}.abc").state == "unavailable"

    # The old entity_id should no longer be tracked
    hass.states.async_set(switch_entity_id, "off")
    await hass.async_block_till_done()
    assert hass.states.get(f"{target_domain}.abc").state == "unavailable"

    # Check tracking the new entity_id
    hass.states.async_set(new_switch_entity_id, "off")
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

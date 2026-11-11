"""Test the Hunter Douglas Powerview scene platform."""

from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, async_capture_events

from homeassistant.components.hunterdouglas_powerview.const import DOMAIN
from homeassistant.components.scene import DOMAIN as SCENE_DOMAIN, SERVICE_TURN_ON
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import MOCK_MAC, MOCK_SERIAL


@pytest.mark.usefixtures("mock_hunterdouglas_hub")
@pytest.mark.parametrize("api_version", [1, 2, 3])
async def test_scenes(
    hass: HomeAssistant,
    api_version: int,
) -> None:
    """Test the scenes."""
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "1.2.3.4"}, unique_id=MOCK_MAC)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.async_entity_ids_count(SCENE_DOMAIN) == 18
    assert (
        hass.states.get(
            f"scene.powerview_generation_{api_version}_close_lounge_room"
        ).state
        == STATE_UNKNOWN
    )
    assert (
        hass.states.get(f"scene.powerview_generation_{api_version}_close_bed_4").state
        == STATE_UNKNOWN
    )
    assert (
        hass.states.get(f"scene.powerview_generation_{api_version}_close_bed_2").state
        == STATE_UNKNOWN
    )
    assert (
        hass.states.get(
            f"scene.powerview_generation_{api_version}_close_master_bed"
        ).state
        == STATE_UNKNOWN
    )
    assert (
        hass.states.get(f"scene.powerview_generation_{api_version}_close_family").state
        == STATE_UNKNOWN
    )
    assert (
        hass.states.get(f"scene.powerview_generation_{api_version}_open_bed_4").state
        == STATE_UNKNOWN
    )
    assert (
        hass.states.get(
            f"scene.powerview_generation_{api_version}_open_master_bed"
        ).state
        == STATE_UNKNOWN
    )
    assert (
        hass.states.get(f"scene.powerview_generation_{api_version}_open_bed_3").state
        == STATE_UNKNOWN
    )
    assert (
        hass.states.get(f"scene.powerview_generation_{api_version}_open_family").state
        == STATE_UNKNOWN
    )
    assert (
        hass.states.get(f"scene.powerview_generation_{api_version}_close_study").state
        == STATE_UNKNOWN
    )
    assert (
        hass.states.get(f"scene.powerview_generation_{api_version}_open_all").state
        == STATE_UNKNOWN
    )
    assert (
        hass.states.get(f"scene.powerview_generation_{api_version}_close_all").state
        == STATE_UNKNOWN
    )
    assert (
        hass.states.get(f"scene.powerview_generation_{api_version}_open_kitchen").state
        == STATE_UNKNOWN
    )
    assert (
        hass.states.get(
            f"scene.powerview_generation_{api_version}_open_lounge_room"
        ).state
        == STATE_UNKNOWN
    )
    assert (
        hass.states.get(f"scene.powerview_generation_{api_version}_open_bed_2").state
        == STATE_UNKNOWN
    )
    assert (
        hass.states.get(f"scene.powerview_generation_{api_version}_close_bed_3").state
        == STATE_UNKNOWN
    )
    assert (
        hass.states.get(f"scene.powerview_generation_{api_version}_close_kitchen").state
        == STATE_UNKNOWN
    )
    assert (
        hass.states.get(f"scene.powerview_generation_{api_version}_open_study").state
        == STATE_UNKNOWN
    )

    with patch(
        "homeassistant.components.hunterdouglas_powerview.scene.PvScene.activate"
    ) as mock_activate:
        await hass.services.async_call(
            SCENE_DOMAIN,
            SERVICE_TURN_ON,
            {"entity_id": f"scene.powerview_generation_{api_version}_open_study"},
            blocking=True,
        )
        await hass.async_block_till_done()

    mock_activate.assert_called_once()


@pytest.mark.usefixtures("mock_hunterdouglas_hub")
@pytest.mark.parametrize("api_version", [1, 2, 3])
async def test_stale_scenes_removed_on_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    api_version: int,
) -> None:
    """Test a scene the hub no longer reports is removed when set up again."""
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "1.2.3.4"}, unique_id=MOCK_MAC)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    existing_entity_ids = [
        entity.entity_id
        for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    ]
    phantom = entity_registry.async_get_or_create(
        SCENE_DOMAIN,
        DOMAIN,
        f"{MOCK_SERIAL}_99999",
        config_entry=entry,
        suggested_object_id="phantom_scene",
    )

    events = async_capture_events(hass, er.EVENT_ENTITY_REGISTRY_UPDATED)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    removed = {
        event.data["entity_id"] for event in events if event.data["action"] == "remove"
    }
    assert removed == {phantom.entity_id}
    assert entity_registry.async_get(phantom.entity_id) is None
    for entity_id in existing_entity_ids:
        assert entity_registry.async_is_registered(entity_id)
    assert hass.states.async_entity_ids_count(SCENE_DOMAIN) == 18
    assert entity_registry.async_is_registered(
        f"scene.powerview_generation_{api_version}_open_study"
    )

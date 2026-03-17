"""Test the Hunter Douglas Powerview scene platform."""

from unittest.mock import patch

import pytest

from homeassistant.components.hunterdouglas_powerview.const import DOMAIN
from homeassistant.components.scene import DOMAIN as SCENE_DOMAIN, SERVICE_TURN_ON
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from .const import MOCK_MAC

from tests.common import MockConfigEntry


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
@pytest.mark.parametrize("api_version", [2])
async def test_scene_shade_cross_references_v2(
    hass: HomeAssistant,
    api_version: int,
) -> None:
    """Test scene entities expose shade PV IDs and HA entity IDs for v2."""
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "1.2.3.4"}, unique_id=MOCK_MAC)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # "Open Kitchen" (scene id 64679) has exactly one shade: 40458 ("Kitchen Roller")
    # Kitchen Roller is a DualOverlappedTilt90 (type 9), which creates 3 cover entities.
    state = hass.states.get("scene.powerview_generation_2_open_kitchen")
    assert state is not None
    assert state.attributes["shade_ids"] == [40458]
    assert set(state.attributes["shade_entity_ids"]) == {
        "cover.kitchen_roller",
        "cover.kitchen_roller_front",
        "cover.kitchen_roller_rear",
    }


@pytest.mark.usefixtures("mock_hunterdouglas_hub")
@pytest.mark.parametrize("api_version", [3])
async def test_scene_shade_cross_references_v3(
    hass: HomeAssistant,
    api_version: int,
) -> None:
    """Test scene entities expose shade PV IDs and HA entity IDs for v3."""
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "1.2.3.4"}, unique_id=MOCK_MAC)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # "Close Bed 4" (scene id 220) has exactly one shade: 173 ("Bed 4")
    state = hass.states.get("scene.powerview_generation_3_close_bed_4")
    assert state is not None
    assert state.attributes["shade_ids"] == [173]
    assert "cover.bed_4" in state.attributes["shade_entity_ids"]


@pytest.mark.usefixtures("mock_hunterdouglas_hub")
@pytest.mark.parametrize("api_version", [1])
async def test_scene_shade_cross_references_empty_for_v1(
    hass: HomeAssistant,
    api_version: int,
) -> None:
    """Test that scene shade cross-reference attributes are empty lists on v1."""
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "1.2.3.4"}, unique_id=MOCK_MAC)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("scene.powerview_generation_1_open_kitchen")
    assert state is not None
    assert state.attributes["shade_ids"] == []
    assert state.attributes["shade_entity_ids"] == []
    assert state.attributes["scheduled_event_ids"] == []
    assert state.attributes["scheduled_event_entity_ids"] == []


@pytest.mark.usefixtures("mock_hunterdouglas_hub")
@pytest.mark.parametrize("api_version", [2])
async def test_scene_scheduled_event_cross_references_v2(
    hass: HomeAssistant,
    api_version: int,
) -> None:
    """Test scene entities expose scheduled event PV IDs and HA entity IDs for v2."""
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "1.2.3.4"}, unique_id=MOCK_MAC)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("scene.powerview_generation_2_open_kitchen")
    assert state is not None
    assert 37484 in state.attributes["scheduled_event_ids"]
    assert (
        "switch.powerview_generation_2_open_kitchen_schedule"
        in state.attributes["scheduled_event_entity_ids"]
    )


@pytest.mark.usefixtures("mock_hunterdouglas_hub")
@pytest.mark.parametrize("api_version", [3])
async def test_scene_scheduled_event_cross_references_v3(
    hass: HomeAssistant,
    api_version: int,
) -> None:
    """Test scene entities expose scheduled event PV IDs and HA entity IDs for v3."""
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "1.2.3.4"}, unique_id=MOCK_MAC)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Automation 437 references scene 220 ("Close Bed 4")
    state = hass.states.get("scene.powerview_generation_3_close_bed_4")
    assert state is not None
    assert 437 in state.attributes["scheduled_event_ids"]
    assert (
        "switch.powerview_generation_3_close_bed_4_schedule"
        in state.attributes["scheduled_event_entity_ids"]
    )

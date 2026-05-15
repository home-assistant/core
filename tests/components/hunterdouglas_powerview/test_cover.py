"""Test the Hunter Douglas PowerView cover platform."""

import pytest

from homeassistant.components.hunterdouglas_powerview.const import DOMAIN
from homeassistant.core import HomeAssistant

from .const import MOCK_MAC

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_hunterdouglas_hub")
@pytest.mark.parametrize("api_version", [2])
async def test_cover_scene_cross_references_v2(
    hass: HomeAssistant,
    api_version: int,
) -> None:
    """Test cover entities expose scene PV IDs and HA entity IDs for v2."""
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "1.2.3.4"}, unique_id=MOCK_MAC)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Shade 40458 ("Kitchen Roller") appears in 4 scenes:
    # 61648 (Open All), 64679 (Open Kitchen), 24626 (Close All), 51159 (Close Kitchen)
    state = hass.states.get("cover.kitchen_roller")
    assert state is not None

    scene_ids = state.attributes["scene_ids"]
    assert set(scene_ids) == {61648, 64679, 24626, 51159}

    scene_entity_ids = state.attributes["scene_entity_ids"]
    assert set(scene_entity_ids) == {
        "scene.powerview_generation_2_open_all",
        "scene.powerview_generation_2_open_kitchen",
        "scene.powerview_generation_2_close_all",
        "scene.powerview_generation_2_close_kitchen",
    }


@pytest.mark.usefixtures("mock_hunterdouglas_hub")
@pytest.mark.parametrize("api_version", [3])
async def test_cover_scene_cross_references_v3(
    hass: HomeAssistant,
    api_version: int,
) -> None:
    """Test cover entities expose scene PV IDs and HA entity IDs for v3."""
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "1.2.3.4"}, unique_id=MOCK_MAC)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Shade 173 ("Bed 4") appears in 4 scenes:
    # 220 (Close Bed 4), 255 (Open Bed 4), 299 (Open All), 301 (Close All)
    state = hass.states.get("cover.bed_4")
    assert state is not None

    scene_ids = state.attributes["scene_ids"]
    assert set(scene_ids) == {220, 255, 299, 301}

    scene_entity_ids = state.attributes["scene_entity_ids"]
    assert "scene.powerview_generation_3_close_bed_4" in scene_entity_ids
    assert "scene.powerview_generation_3_open_bed_4" in scene_entity_ids


@pytest.mark.usefixtures("mock_hunterdouglas_hub")
@pytest.mark.parametrize("api_version", [1])
async def test_cover_scene_cross_references_empty_for_v1(
    hass: HomeAssistant,
    api_version: int,
) -> None:
    """Test that cover scene cross-reference attributes are empty lists on v1."""
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "1.2.3.4"}, unique_id=MOCK_MAC)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    cover_ids = hass.states.async_entity_ids("cover")
    assert len(cover_ids) > 0

    for entity_id in cover_ids:
        state = hass.states.get(entity_id)
        assert state.attributes["scene_ids"] == [], entity_id
        assert state.attributes["scene_entity_ids"] == [], entity_id

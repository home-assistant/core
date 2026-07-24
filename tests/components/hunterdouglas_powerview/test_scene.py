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

"""Test the Hunter Douglas Powerview scene platform."""
from unittest.mock import patch

from homeassistant.components.hunterdouglas_powerview.const import DOMAIN
from homeassistant.components.scene import DOMAIN as SCENE_DOMAIN, SERVICE_TURN_ON
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from . import MOCK_MAC

from tests.common import MockConfigEntry


async def test_scenes(hass: HomeAssistant, mock_powerview_v2_hub: None) -> None:
    """Test the scenes."""
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "1.2.3.4"}, unique_id=MOCK_MAC)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 2
    assert hass.states.get("scene.alexanderhd_one").state == STATE_UNKNOWN
    assert hass.states.get("scene.alexanderhd_two").state == STATE_UNKNOWN

    with patch(
        "homeassistant.components.hunterdouglas_powerview.scene.PvScene.activate"
    ) as mock_activate:
        await hass.services.async_call(
            SCENE_DOMAIN,
            SERVICE_TURN_ON,
            {"entity_id": "scene.alexanderhd_one"},
            blocking=True,
        )
        await hass.async_block_till_done()

    mock_activate.assert_called_once()

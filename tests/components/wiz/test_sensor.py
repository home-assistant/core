"""Tests for the sensor platform."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import (
    FAKE_DUAL_HEAD_RGBWW_BULB,
    FAKE_MAC,
    _patch_discovery,
    _patch_wizlight,
    async_push_update,
    async_setup_integration,
)


async def test_signal_strength(hass: HomeAssistant) -> None:
    """Test signal strength."""
    bulb, entry = await async_setup_integration(
        hass, bulb_type=FAKE_DUAL_HEAD_RGBWW_BULB
    )
    entity_id = "sensor.mock_title_signal_strength"
    entity_registry = er.async_get(hass)
    reg_entry = entity_registry.async_get(entity_id)
    assert reg_entry.unique_id == f"{FAKE_MAC}_rssi"
    updated_entity = entity_registry.async_update_entity(
        entity_id=entity_id, disabled_by=None
    )
    assert not updated_entity.disabled

    with _patch_discovery(), _patch_wizlight(device=bulb):
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "-55"

    await async_push_update(hass, bulb, {"mac": FAKE_MAC, "rssi": -50})
    assert hass.states.get(entity_id).state == "-50"

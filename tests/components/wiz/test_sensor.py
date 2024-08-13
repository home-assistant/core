"""Tests for the sensor platform."""

from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import (
    FAKE_DUAL_HEAD_RGBWW_BULB,
    FAKE_MAC,
    FAKE_SOCKET_WITH_POWER_MONITORING,
    _mocked_wizlight,
    _patch_discovery,
    _patch_wizlight,
    async_push_update,
    async_setup_integration,
)


async def test_signal_strength(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test signal strength."""
    bulb, entry = await async_setup_integration(
        hass, bulb_type=FAKE_DUAL_HEAD_RGBWW_BULB
    )
    entity_id = "sensor.mock_title_signal_strength"
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


async def test_power_monitoring(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test power monitoring."""
    socket = _mocked_wizlight(None, None, FAKE_SOCKET_WITH_POWER_MONITORING)
    socket.power_monitoring = None
    socket.get_power = AsyncMock(return_value=5.123)
    _, entry = await async_setup_integration(
        hass, wizlight=socket, bulb_type=FAKE_SOCKET_WITH_POWER_MONITORING
    )
    entity_id = "sensor.mock_title_power"
    reg_entry = entity_registry.async_get(entity_id)
    assert reg_entry.unique_id == f"{FAKE_MAC}_power"
    updated_entity = entity_registry.async_update_entity(
        entity_id=entity_id, disabled_by=None
    )
    assert not updated_entity.disabled

    with _patch_discovery(), _patch_wizlight(device=socket):
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "5.123"
    await async_push_update(hass, socket, {"mac": FAKE_MAC, "pc": 800})
    assert hass.states.get(entity_id).state == "0.8"

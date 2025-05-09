"""Test the Music Assistant integration init."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from music_assistant_models.errors import ActionUnavailable

from homeassistant.components.music_assistant.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from .common import setup_integration_from_fixtures

from tests.typing import WebSocketGenerator


async def test_remove_config_entry_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    music_assistant_client: MagicMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test device removal."""
    assert await async_setup_component(hass, "config", {})
    await setup_integration_from_fixtures(hass, music_assistant_client)
    await hass.async_block_till_done()
    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    client = await hass_ws_client(hass)

    # test if the removal should be denied if the device is still in use
    device_entry = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )[0]
    entity_id = "media_player.test_player_1"
    assert device_entry
    assert entity_registry.async_get(entity_id)
    assert hass.states.get(entity_id)
    music_assistant_client.config.remove_player_config = AsyncMock(
        side_effect=ActionUnavailable
    )
    response = await client.remove_device(device_entry.id, config_entry.entry_id)
    assert music_assistant_client.config.remove_player_config.call_count == 1
    assert response["success"] is False

    # test if the removal should be allowed if the device is not in use
    music_assistant_client.config.remove_player_config = AsyncMock()
    response = await client.remove_device(device_entry.id, config_entry.entry_id)
    assert response["success"] is True
    await hass.async_block_till_done()
    assert not device_registry.async_get(device_entry.id)
    assert not entity_registry.async_get(entity_id)
    assert not hass.states.get(entity_id)

    # test if the removal succeeds if its no longer provided by the server
    mass_player_id = "00:00:00:00:00:02"
    music_assistant_client.players._players.pop(mass_player_id)
    device_entry = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )[0]
    entity_id = "media_player.my_super_test_player_2"
    assert device_entry
    assert entity_registry.async_get(entity_id)
    assert hass.states.get(entity_id)
    music_assistant_client.config.remove_player_config = AsyncMock()
    response = await client.remove_device(device_entry.id, config_entry.entry_id)
    assert music_assistant_client.config.remove_player_config.call_count == 0
    assert response["success"] is True

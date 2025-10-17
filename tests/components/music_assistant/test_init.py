"""Test the Music Assistant integration init."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from music_assistant_models.enums import EventType
from music_assistant_models.errors import ActionUnavailable

from homeassistant.components.music_assistant.const import (
    ATTR_CONF_EXPOSE_PLAYER_TO_HA,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from .common import setup_integration_from_fixtures, trigger_subscription_callback

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


async def test_player_config_expose_to_ha_toggle(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    music_assistant_client: MagicMock,
) -> None:
    """Test player exposure toggle via config update."""
    await setup_integration_from_fixtures(hass, music_assistant_client)
    await hass.async_block_till_done()
    config_entry = hass.config_entries.async_entries(DOMAIN)[0]

    # Initial state: player should be exposed (from fixture)
    entity_id = "media_player.test_player_1"
    player_id = "00:00:00:00:00:01"
    assert hass.states.get(entity_id)
    assert entity_registry.async_get(entity_id)
    device_entry = device_registry.async_get_device({(DOMAIN, player_id)})
    assert device_entry
    assert player_id in config_entry.runtime_data.discovered_players

    # Simulate player config update: expose_to_ha = False
    # Trigger the subscription callback
    event_data = {
        "player_id": player_id,
        "provider": "test",
        "values": {
            ATTR_CONF_EXPOSE_PLAYER_TO_HA: {
                "key": ATTR_CONF_EXPOSE_PLAYER_TO_HA,
                "type": "boolean",
                "value": False,
                "label": ATTR_CONF_EXPOSE_PLAYER_TO_HA,
                "default_value": True,
            }
        },
    }
    await trigger_subscription_callback(
        hass,
        music_assistant_client,
        EventType.PLAYER_CONFIG_UPDATED,
        player_id,
        event_data,
    )

    # Verify player was removed from HA
    assert player_id not in config_entry.runtime_data.discovered_players
    assert not hass.states.get(entity_id)
    assert not entity_registry.async_get(entity_id)
    device_entry = device_registry.async_get_device({(DOMAIN, player_id)})
    assert not device_entry

    # Now test re-adding the player: expose_to_ha = True
    await trigger_subscription_callback(
        hass,
        music_assistant_client,
        EventType.PLAYER_CONFIG_UPDATED,
        player_id,
        {
            "player_id": player_id,
            "provider": "test",
            "values": {
                ATTR_CONF_EXPOSE_PLAYER_TO_HA: {
                    "key": ATTR_CONF_EXPOSE_PLAYER_TO_HA,
                    "type": "boolean",
                    "value": True,
                    "label": ATTR_CONF_EXPOSE_PLAYER_TO_HA,
                    "default_value": True,
                }
            },
        },
    )

    # Verify player was re-added to HA
    assert player_id in config_entry.runtime_data.discovered_players
    assert hass.states.get(entity_id)
    assert entity_registry.async_get(entity_id)
    device_entry = device_registry.async_get_device({(DOMAIN, player_id)})
    assert device_entry

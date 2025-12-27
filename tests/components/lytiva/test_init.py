"""Tests for Lytiva integration initialization."""
from __future__ import annotations

import json
import pytest
from unittest.mock import patch

from homeassistant.components.lytiva.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_entry(
    hass: HomeAssistant, mqtt_mock, mock_config_entry: MockConfigEntry
) -> None:
    """Test successful setup of a config entry."""
    mock_config_entry.add_to_hass(hass)
    
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    
    assert mock_config_entry.state == ConfigEntryState.LOADED
    
    # Verify online status was published
    mqtt_mock.async_publish.assert_called_with(
        "LYT/homeassistant/status", "online", 1, True
    )
    
    # Verify discovery topic was subscribed
    mqtt_mock.async_subscribe.assert_called()
    # Topic could be in args[0] or args[1] depending on how mqtt_mock is patched
    subscribed_topics = []
    for call in mqtt_mock.async_subscribe.call_args_list:
        for arg in call[0]:
            if isinstance(arg, str) and arg.startswith("LYT/"):
                subscribed_topics.append(arg)
    assert "LYT/homeassistant/+/+/config" in subscribed_topics


async def test_setup_entry_mqtt_not_available(
    hass: HomeAssistant, mqtt_mock, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup fails when MQTT is not available."""
    mock_config_entry.add_to_hass(hass)
    
    mock_config_entry.add_to_hass(hass)
    
    with patch("homeassistant.components.mqtt.async_wait_for_mqtt_client", return_value=False):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state == ConfigEntryState.SETUP_RETRY


async def test_unload_entry(
    hass: HomeAssistant, mqtt_mock, setup_integration
) -> None:
    """Test successful unload of a config entry."""
    assert await hass.config_entries.async_unload(setup_integration.entry_id)
    await hass.async_block_till_done()
    
    assert setup_integration.state == ConfigEntryState.NOT_LOADED
    
    # Verify offline status was published
    mqtt_mock.async_publish.assert_any_call(
        "LYT/homeassistant/status", "offline", 0, True # Default qos for unload publish might be 0 if not specified
    )
    # Wait, in __init__.py it was: await mqtt.async_publish(hass, "LYT/homeassistant/status", "offline", retain=True)
    # So qos is default (0)


async def test_remove_entity_via_discovery(
    hass: HomeAssistant, mqtt_mock, setup_integration
) -> None:
    """Test removing an entity via empty discovery payload."""
    from homeassistant.helpers import entity_registry as er, device_registry as dr
    
    # 1. First discover a light to create it
    payload = {
        "unique_id": "remove_me",
        "name": "Removal Test",
        "command_topic": "LYT/99/COMMAND",
        "address": 99,
        "device": {
            "identifiers": ["dev_remove_me"],
            "name": "Device to Remove",
        }
    }
    
    # Trigger discovery
    # Find the callback from mqtt_mock calls
    discovery_callback = None
    for call in mqtt_mock.async_subscribe.call_args_list:
        # Loop through args to find the topic and the callback
        args = call[0]
        if any(isinstance(arg, str) and arg == "LYT/homeassistant/+/+/config" for arg in args):
            # The callback is usually the last or second to last arg
            for arg in reversed(args):
                if callable(arg):
                    discovery_callback = arg
                    break
            if discovery_callback:
                break
            
    assert discovery_callback is not None
    
    # Create the entity
    class MockMsg:
        def __init__(self, topic, payload):
            self.topic = topic
            self.payload = payload
            
    await discovery_callback(MockMsg("LYT/homeassistant/light/remove_me/config", json.dumps(payload)))
    await hass.async_block_till_done()
    
    # Verify it exists
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    
    entity_id = ent_reg.async_get_entity_id("light", DOMAIN, "remove_me")
    assert entity_id is not None
    entry = ent_reg.async_get(entity_id)
    device_id = entry.device_id
    assert device_id is not None
    
    # 2. Now send empty payload to remove it
    await discovery_callback(MockMsg("LYT/homeassistant/light/remove_me/config", "{}"))
    await hass.async_block_till_done()
    
    # Verify entity is gone
    assert ent_reg.async_get_entity_id("light", DOMAIN, "remove_me") is None
    # Verify device is gone (since it was the only entity)
    assert dev_reg.async_get(device_id) is None


async def test_init_error_paths(
    hass: HomeAssistant, mqtt_mock, setup_integration
) -> None:
    """Test error paths in __init__.py discovery."""
    discovery_callback = None
    for call in mqtt_mock.async_subscribe.call_args_list:
        args = call[0]
        if any(isinstance(arg, str) and arg == "LYT/homeassistant/+/+/config" for arg in args):
            for arg in reversed(args):
                if callable(arg):
                    discovery_callback = arg
                    break
    assert discovery_callback is not None

    class MockMsg:
        def __init__(self, topic, payload):
            self.topic = topic
            self.payload = payload

    # 1. Invalid JSON
    await discovery_callback(MockMsg("LYT/homeassistant/light/invalid/config", "invalid{json}"))
    await hass.async_block_till_done()

    # 2. Short topic
    await discovery_callback(MockMsg("LYT/config", "{}"))
    await hass.async_block_till_done()

    # 3. Payload without address/unique_id (should use topic ID)
    await discovery_callback(MockMsg("LYT/homeassistant/light/auto_id/config", '{"name": "Auto ID"}'))
    await hass.async_block_till_done()
    
    from homeassistant.helpers import entity_registry as er
    ent_reg = er.async_get(hass)
    assert ent_reg.async_get_entity_id("light", DOMAIN, "auto_id") is not None


async def test_init_setup_publish_error(
    hass: HomeAssistant, mqtt_mock, mock_config_entry: MockConfigEntry
) -> None:
    """Test publish error during setup."""
    mock_config_entry.add_to_hass(hass)
    
    with patch("homeassistant.components.mqtt.async_publish", side_effect=Exception("Publish failed")):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    
    assert mock_config_entry.state == ConfigEntryState.LOADED


async def test_init_remove_device_error(
    hass: HomeAssistant, mqtt_mock, setup_integration
) -> None:
    """Test error during device removal."""
    from homeassistant.helpers import entity_registry as er, device_registry as dr
    
    # Setup entity
    discovery_callback = None
    for call in mqtt_mock.async_subscribe.call_args_list:
        args = call[0]
        if any(isinstance(arg, str) and arg == "LYT/homeassistant/+/+/config" for arg in args):
            for arg in reversed(args):
                if callable(arg):
                    discovery_callback = arg
                    break
    
    class MockMsg:
        def __init__(self, topic, payload):
            self.topic = topic
            self.payload = payload

    payload = {
        "unique_id": "err_remove",
        "name": "Error Remove",
        "address": 77,
        "device": {"identifiers": ["err_dev"]}
    }
    await discovery_callback(MockMsg("LYT/homeassistant/light/err_remove/config", json.dumps(payload)))
    await hass.async_block_till_done()

    ent_reg = er.async_get(hass)
    entity_id = ent_reg.async_get_entity_id("light", DOMAIN, "err_remove")
    entry = ent_reg.async_get(entity_id)

    # Mock device registry to fail removal
    with patch("homeassistant.helpers.device_registry.DeviceRegistry.async_remove_device", side_effect=Exception("Remove failed")):
        await discovery_callback(MockMsg("LYT/homeassistant/light/err_remove/config", "{}"))
        await hass.async_block_till_done()

    # Entity should be gone even if device removal failed
    assert ent_reg.async_get_entity_id("light", DOMAIN, "err_remove") is None

"""Additional tests for Lytiva __init__.py to improve coverage."""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from homeassistant.components.lytiva.const import DOMAIN
from homeassistant.core import HomeAssistant


class MockMessage:
    """Mock MQTT message."""

    def __init__(self, topic: str, payload: bytes):
        self.topic = topic
        self.payload = payload


async def test_mqtt_handler_device_removal(
    hass: HomeAssistant, mock_mqtt_client: MagicMock, setup_integration
) -> None:
    """Test device removal with empty discovery payload."""
    # First, discover a device
    discovery_callback = None
    for call in mock_mqtt_client.message_callback_add.call_args_list:
        args, _ = call
        if "config" in str(args[0]):
            discovery_callback = args[1]
            break

    assert discovery_callback is not None

    # Discover a light
    payload = {
        "unique_id": "test_removal",
        "name": "Test Removal",
        "type": "dimmer",
        "command_topic": "LYT/99/NODE/E/COMMAND",
        "address": 99,
    }
    msg = MockMessage(
        "homeassistant/light/test_removal/config", json.dumps(payload).encode()
    )
    discovery_callback(mock_mqtt_client, None, msg)
    await hass.async_block_till_done()

    # Verify it was created
    state = hass.states.get("light.test_removal")
    assert state is not None

    # Send empty payload to remove it
    empty_msg = MockMessage("homeassistant/light/test_removal/config", b"{}")
    discovery_callback(mock_mqtt_client, None, empty_msg)
    await hass.async_block_till_done()


async def test_mqtt_handler_invalid_discovery_json(
    hass: HomeAssistant, mock_mqtt_client: MagicMock, setup_integration
) -> None:
    """Test handling of invalid JSON in discovery."""
    discovery_callback = None
    for call in mock_mqtt_client.message_callback_add.call_args_list:
        args, _ = call
        if "config" in str(args[0]):
            discovery_callback = args[1]
            break

    # Send invalid JSON
    msg = MockMessage("homeassistant/light/invalid/config", b"not json")
    discovery_callback(mock_mqtt_client, None, msg)
    await hass.async_block_till_done()
    # Should not crash


async def test_mqtt_handler_discovery_without_unique_id(
    hass: HomeAssistant, mock_mqtt_client: MagicMock, setup_integration
) -> None:
    """Test discovery payload without unique_id."""
    discovery_callback = None
    for call in mock_mqtt_client.message_callback_add.call_args_list:
        args, _ = call
        if "config" in str(args[0]):
            discovery_callback = args[1]
            break

    # Send payload without unique_id or address
    payload = {"name": "No ID Light", "type": "dimmer"}
    msg = MockMessage(
        "homeassistant/light/noid/config", json.dumps(payload).encode()
    )
    discovery_callback(mock_mqtt_client, None, msg)
    await hass.async_block_till_done()
    # Should not crash, just log and ignore


async def test_mqtt_handler_invalid_status_json(
    hass: HomeAssistant, mock_mqtt_client: MagicMock, setup_integration
) -> None:
    """Test handling of invalid JSON in status."""
    status_callback = None
    for call in mock_mqtt_client.message_callback_add.call_args_list:
        args, _ = call
        if "STATUS" in str(args[0]):
            status_callback = args[1]
            break

    # Send invalid JSON
    msg = MockMessage("LYT/1/NODE/E/STATUS", b"invalid json")
    status_callback(mock_mqtt_client, None, msg)
    await hass.async_block_till_done()
    # Should not crash


async def test_mqtt_handler_status_for_unknown_entity(
    hass: HomeAssistant, mock_mqtt_client: MagicMock, setup_integration
) -> None:
    """Test status message for non-existent entity."""
    status_callback = None
    for call in mock_mqtt_client.message_callback_add.call_args_list:
        args, _ = call
        if "STATUS" in str(args[0]):
            status_callback = args[1]
            break

    # Send status for unknown address
    payload = {"address": 9999, "dimming": 50}
    msg = MockMessage("LYT/9999/NODE/E/STATUS", json.dumps(payload).encode())
    status_callback(mock_mqtt_client, None, msg)
    await hass.async_block_till_done()
    # Should not crash, just log


async def test_mqtt_connection_failure(
    hass: HomeAssistant, mock_mqtt_client: MagicMock, mock_config_entry
) -> None:
    """Test handling of MQTT connection failure."""
    from unittest.mock import patch

    mock_config_entry.add_to_hass(hass)

    # Make connect fail
    mock_mqtt_client.connect.side_effect = Exception("Connection failed")

    with patch(
        "homeassistant.components.lytiva.mqtt_client.Client",
        return_value=mock_mqtt_client,
    ):
        result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
        assert result is False


async def test_mqtt_publish_failure_handling(
    hass: HomeAssistant, mock_mqtt_client: MagicMock, setup_integration
) -> None:
    """Test handling of MQTT publish failures."""
    # Discover a light
    discovery_callback = None
    for call in mock_mqtt_client.message_callback_add.call_args_list:
        args, _ = call
        if "config" in str(args[0]):
            discovery_callback = args[1]
            break

    payload = {
        "unique_id": "publish_fail",
        "name": "Publish Fail",
        "type": "dimmer",
        "command_topic": "LYT/100/NODE/E/COMMAND",
        "address": 100,
    }
    msg = MockMessage(
        "homeassistant/light/publish_fail/config", json.dumps(payload).encode()
    )
    discovery_callback(mock_mqtt_client, None, msg)
    await hass.async_block_till_done()

    # Make publish fail
    mock_mqtt_client.publish.side_effect = Exception("Publish failed")

    # Try to turn on - should not crash
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.publish_fail"},
        blocking=True,
    )
    # Should handle exception gracefully


async def test_mqtt_handler_subscribe_failure(
    hass: HomeAssistant, mock_mqtt_client: MagicMock, mock_config_entry
) -> None:
    """Test handling of subscription failures."""
    from unittest.mock import patch

    mock_config_entry.add_to_hass(hass)

    # Make subscribe fail
    mock_mqtt_client.subscribe.side_effect = Exception("Subscribe failed")

    with patch(
        "homeassistant.components.lytiva.mqtt_client.Client",
        return_value=mock_mqtt_client,
    ):
        # Should still set up successfully but log errors
        result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
        assert result is True

        # Trigger on_connect
        if mock_mqtt_client.on_connect:
            mock_mqtt_client.on_connect(mock_mqtt_client, None, {}, 0)
            await hass.async_block_till_done()


async def test_mqtt_handler_connection_refused(
    hass: HomeAssistant, mock_mqtt_client: MagicMock, mock_config_entry
) -> None:
    """Test MQTT connection refused (non-zero reason code)."""
    from unittest.mock import patch

    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.lytiva.mqtt_client.Client",
        return_value=mock_mqtt_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Trigger on_connect with error code
        if mock_mqtt_client.on_connect:
            mock_mqtt_client.on_connect(mock_mqtt_client, None, {}, 5)  # Connection refused
            await hass.async_block_till_done()

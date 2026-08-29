"""Tests for iNELS integration."""

from unittest.mock import ANY, AsyncMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import HA_INELS_PATH
from .common import DOMAIN

from tests.common import MockConfigEntry
from tests.typing import MqttMockHAClient


async def test_ha_mqtt_publish(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test that MQTT publish function works correctly."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={})
    config_entry.add_to_hass(hass)

    with (
        patch(f"{HA_INELS_PATH}.InelsDiscovery") as mock_discovery_class,
        patch("homeassistant.components.inels.PLATFORMS", []),
    ):
        mock_discovery = AsyncMock()
        mock_discovery.start.return_value = []
        mock_discovery_class.return_value = mock_discovery

        await hass.config_entries.async_setup(config_entry.entry_id)

        topic, payload, qos, retain = "test/topic", "test_payload", 1, True

        await config_entry.runtime_data.mqtt.publish(topic, payload, qos, retain)
        mqtt_mock.async_publish.assert_called_once_with(
            topic, payload, qos, retain, message_expiry_interval=None
        )


async def test_ha_mqtt_subscribe(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test that MQTT subscribe function works correctly."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={})
    config_entry.add_to_hass(hass)

    with (
        patch(f"{HA_INELS_PATH}.InelsDiscovery") as mock_discovery_class,
        patch("homeassistant.components.inels.PLATFORMS", []),
    ):
        mock_discovery = AsyncMock()
        mock_discovery.start.return_value = []
        mock_discovery_class.return_value = mock_discovery

        await hass.config_entries.async_setup(config_entry.entry_id)

        topic = "test/topic"

        await config_entry.runtime_data.mqtt.subscribe(topic)
        mqtt_mock.async_subscribe.assert_any_call(topic, ANY, 0, "utf-8", None)


async def test_ha_mqtt_not_available(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test that ConfigEntryNotReady is raised when MQTT is not available."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={})
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.mqtt.async_wait_for_mqtt_client",
        return_value=False,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient, mock_mqtt
) -> None:
    """Test unload entry."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={})
    config_entry.add_to_hass(hass)

    with (
        patch(f"{HA_INELS_PATH}.InelsDiscovery") as mock_discovery_class,
        patch("homeassistant.components.inels.PLATFORMS", []),
    ):
        mock_discovery = AsyncMock()
        mock_discovery.start.return_value = []
        mock_discovery_class.return_value = mock_discovery

        assert await hass.config_entries.async_setup(config_entry.entry_id)

        result = await hass.config_entries.async_unload(config_entry.entry_id)

        assert result is True
        mock_mqtt.unsubscribe_topics.assert_called_once()
        mock_mqtt.unsubscribe_listeners.assert_called_once()

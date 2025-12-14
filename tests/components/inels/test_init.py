"""Tests for iNELS integration."""

from unittest.mock import ANY, AsyncMock, patch

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from . import HA_INELS_PATH
from .common import DOMAIN, inels

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
        patch(
            "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
            return_value=None,
        ),
    ):
        mock_discovery = AsyncMock()
        mock_discovery.start.return_value = []
        mock_discovery_class.return_value = mock_discovery

        await inels.async_setup_entry(hass, config_entry)

        topic, payload, qos, retain = "test/topic", "test_payload", 1, True

        await config_entry.runtime_data.mqtt.publish(topic, payload, qos, retain)
        mqtt_mock.async_publish.assert_called_once_with(topic, payload, qos, retain)


async def test_ha_mqtt_subscribe(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test that MQTT subscribe function works correctly."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={})
    config_entry.add_to_hass(hass)

    with (
        patch(f"{HA_INELS_PATH}.InelsDiscovery") as mock_discovery_class,
        patch(
            "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
            return_value=None,
        ),
    ):
        mock_discovery = AsyncMock()
        mock_discovery.start.return_value = []
        mock_discovery_class.return_value = mock_discovery

        await inels.async_setup_entry(hass, config_entry)

        topic = "test/topic"

        await config_entry.runtime_data.mqtt.subscribe(topic)
        mqtt_mock.async_subscribe.assert_any_call(topic, ANY, 0, "utf-8", None)


async def test_ha_mqtt_not_available(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test that ConfigEntryNotReady is raised when MQTT is not available."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={})
    config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.mqtt.async_wait_for_mqtt_client",
            return_value=False,
        ),
        pytest.raises(ConfigEntryNotReady, match="MQTT integration not available"),
    ):
        await inels.async_setup_entry(hass, config_entry)


async def test_unload_entry(hass: HomeAssistant, mock_mqtt) -> None:
    """Test unload entry."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={})
    config_entry.add_to_hass(hass)

    config_entry.runtime_data = inels.InelsData(mqtt=mock_mqtt, devices=[])

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
        return_value=True,
    ) as mock_unload_platforms:
        result = await inels.async_unload_entry(hass, config_entry)

        assert result is True
        mock_mqtt.unsubscribe_topics.assert_called_once()
        mock_mqtt.unsubscribe_listeners.assert_called_once()
        mock_unload_platforms.assert_called_once()

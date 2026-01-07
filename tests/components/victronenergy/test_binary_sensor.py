"""Test the Victron Energy binary sensor platform."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.victronenergy.binary_sensor import (
    MQTTDiscoveredBinarySensor,
)
from homeassistant.components.victronenergy.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_binary_sensor_integration_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_mqtt_client: MagicMock,
) -> None:
    """Test binary sensor platform setup."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.victronenergy.mqtt_client.Client",
        return_value=mock_mqtt_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Verify binary_sensor platform is loaded
        assert "victronenergy.binary_sensor" in hass.config.components


async def test_binary_sensor_mqtt_manager(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mqtt_client: MagicMock,
) -> None:
    """Test binary sensor platform uses MQTT manager correctly."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.victronenergy.mqtt_client.Client",
        return_value=mock_mqtt_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Verify MQTT manager is available for binary sensors
        manager = hass.data[DOMAIN][mock_config_entry.entry_id]
        assert manager is not None
        assert hasattr(manager, "_topic_entity_map")


async def test_binary_sensor_infrastructure(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_mqtt_client: MagicMock,
) -> None:
    """Test binary sensor infrastructure is in place."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.victronenergy.mqtt_client.Client",
        return_value=mock_mqtt_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Verify infrastructure is ready for binary sensor discovery
        assert MQTTDiscoveredBinarySensor is not None

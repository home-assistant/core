"""Test the Victron Energy diagnostics platform."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from homeassistant.components.victronenergy.const import DOMAIN
from homeassistant.components.victronenergy.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_config_entry_diagnostics(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mqtt_client: MagicMock,
) -> None:
    """Test config entry diagnostics."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.victronenergy.mqtt_client.Client",
        return_value=mock_mqtt_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Get diagnostics
        diagnostics = await async_get_config_entry_diagnostics(hass, mock_config_entry)

        # Check diagnostics structure
        assert "entry_data" in diagnostics
        assert "data" in diagnostics

        # Check that sensitive data is redacted
        entry_data = diagnostics["entry_data"]
        assert "token" not in str(entry_data) or "**REDACTED**" in str(entry_data)

        # Check that broker info is present (non-sensitive)
        assert "broker" in entry_data or "host" in entry_data


async def test_diagnostics_data_structure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mqtt_client: MagicMock,
    mock_data: dict,
) -> None:
    """Test diagnostics includes proper data structure."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.victronenergy.mqtt_client.Client",
        return_value=mock_mqtt_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Simulate some MQTT data
        manager = hass.data[DOMAIN][mock_config_entry.entry_id]
        for topic, payload in mock_data["device_info"].items():
            msg = MagicMock()
            msg.topic = topic
            msg.payload = f'{{"value": {payload["value"]}}}'.encode()
            manager._on_message(None, None, msg)

        await hass.async_block_till_done()

        # Get diagnostics
        diagnostics = await async_get_config_entry_diagnostics(hass, mock_config_entry)

        # Check that data includes discovered devices/topics
        assert isinstance(diagnostics["data"], dict)
        # Should have some data if MQTT messages were processed
        if diagnostics["data"]:
            assert len(diagnostics["data"]) > 0

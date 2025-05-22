"""Tests for the EnergyID diagnostics platform."""

from unittest.mock import MagicMock

from homeassistant.components.energyid.const import DATA_CLIENT, DOMAIN
from homeassistant.components.energyid.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_entry_diagnostics(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
) -> None:
    """Test config entry diagnostics."""
    mock_config_entry.add_to_hass(hass)
    hass.data.setdefault(DOMAIN, {})[mock_config_entry.entry_id] = {
        DATA_CLIENT: mock_webhook_client
    }

    result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    assert "client_information" in result
    assert "config_entry_title" in result
    assert result["config_entry_title"] == mock_config_entry.title
    assert "config_entry_unique_id" in result

    client_info = result["client_information"]
    assert "device_id_for_eid" in client_info
    assert "device_name_for_eid" in client_info
    assert "is_claimed" in client_info
    assert "webhook_url" in client_info
    assert "webhook_policy" in client_info

    if mock_webhook_client.auth_valid_until is not None:
        assert "auth_valid_until" in client_info
    if mock_webhook_client.last_sync_time is not None:
        assert "last_sync_time" in client_info


async def test_entry_diagnostics_no_client(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test config entry diagnostics when client is not found in hass data."""
    mock_config_entry.add_to_hass(hass)
    hass.data.setdefault(DOMAIN, {})[mock_config_entry.entry_id] = {}

    result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    assert "client_information" in result
    assert result["client_information"] == {"status": "Client not found in hass.data"}
    assert "config_entry_title" in result
    assert result["config_entry_title"] == mock_config_entry.title


async def test_entry_diagnostics_no_integration_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test config entry diagnostics when integration data structure is missing."""
    mock_config_entry.add_to_hass(hass)
    if DOMAIN in hass.data:
        del hass.data[DOMAIN]

    result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    assert "client_information" in result
    assert result["client_information"] == {
        "status": "Integration data not found in hass.data"
    }
    assert "config_entry_title" in result
    assert result["config_entry_title"] == mock_config_entry.title

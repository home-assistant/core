"""Test the SMN init module."""

import pytest

from homeassistant.components.smn_argentina import DOMAIN, _parse_alerts
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import init_integration

async def test_setup_entry(
    hass: HomeAssistant,
    mock_smn_api_client,
    mock_token_manager,
) -> None:
    """Test successful setup of entry."""
    entry = await init_integration(hass)

    assert entry.state == ConfigEntryState.LOADED
    assert entry.runtime_data is not None


async def test_unload_entry(
    hass: HomeAssistant,
    mock_smn_api_client,
    mock_token_manager,
) -> None:
    """Test successful unload of entry."""
    entry = await init_integration(hass)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state == ConfigEntryState.NOT_LOADED


async def test_service_get_alerts_for_location(
    hass: HomeAssistant,
    mock_smn_api_client,
    mock_token_manager,
) -> None:
    """Test get_alerts_for_location service."""
    await init_integration(hass)

    # The API client is already mocked to return empty alerts
    # Call the service with location_id
    response = await hass.services.async_call(
        DOMAIN,
        "get_alerts_for_location",
        {"location_id": "1234"},
        blocking=True,
        return_response=True,
    )

    assert response is not None
    assert isinstance(response, dict)
    assert "active_alerts" in response
    assert "max_severity" in response


async def test_service_get_alerts_for_location_no_integration(
    hass: HomeAssistant,
    mock_smn_api_client,
    mock_token_manager,
) -> None:
    """Test get_alerts_for_location service when no integration is configured."""
    # Setup then unload to register service but leave no active entries
    entry = await init_integration(hass)
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    # Call the service - should raise exception because no loaded entries (or no entries at all if checking async_entries)
    # Note: async_unload doesn't remove entry from hass.config_entries, just unloads it.
    # Logic checks async_entries(DOMAIN). It returns entries even if not loaded?
    # Yes. But service logic checks if `smn_entries` is empty.
    # If I verify code: `smn_entries = hass.config_entries.async_entries(DOMAIN)`.
    # `async_unload` keeps it. `async_remove` removes it.
    # I should use `async_remove`.

    await hass.config_entries.async_remove(entry.entry_id)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            "get_alerts_for_location",
            {"location_id": "1234"},
            blocking=True,
            return_response=True,
        )


async def test_service_get_alerts_for_location_with_error(
    hass: HomeAssistant,
    mock_smn_api_client,
    mock_token_manager,
) -> None:
    """Test get_alerts_for_location service with API error."""
    await init_integration(hass)

    # Make API client raise an error
    mock_smn_api_client.async_get_alerts.side_effect = Exception("API Error")

    # Call the service - should raise HomeAssistantError
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            "get_alerts_for_location",
            {"location_id": "1234"},
            blocking=True,
            return_response=True,
        )


async def test_parse_alerts_empty_data(
    hass: HomeAssistant,
) -> None:
    """Test alert parsing with empty/None data."""
    # Test with None
    result = _parse_alerts(None)
    assert result["active_alerts"] == []
    assert result["max_severity"] == "info"

    # Test with empty dict
    result = _parse_alerts({})
    assert result["active_alerts"] == []
    assert result["max_severity"] == "info"

    # Test with empty warnings
    result = _parse_alerts({"warnings": [], "reports": []})
    assert result["active_alerts"] == []
    assert result["max_severity"] == "info"


async def test_parse_alerts_level_1_filtered(
    hass: HomeAssistant,
) -> None:
    """Test that level 1 alerts are filtered out."""
    # Alert data with only level 1 (should be filtered)
    data = {
        "warnings": [
            {
                "date": "2025-12-30",
                "max_level": 1,
                "events": [
                    {"id": 37, "max_level": 1, "levels": {"night": 1}},
                ],
            }
        ],
        "reports": [],
        "area_id": 762,
    }

    result = _parse_alerts(data)
    assert result["active_alerts"] == []
    assert result["max_severity"] == "info"
    assert result["max_level"] == 1

"""Tests for integrations of modules."""


from unittest.mock import MagicMock

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_integration_different_modules(
    hass: HomeAssistant,
    mock_api: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensors."""
    assert mock_config_entry.state == ConfigEntryState.LOADED
    # print_hass(hass)
    # print_entry(mock_config_entry)
    assert mock_config_entry.domain == "instructure"
    mock_api.access_token = "mock_access_token"
    mock_api.host = "https://chalmers.instructure.com/api/v1"
    
    coordinator = hass.data["instructure"][mock_config_entry.entry_id]["coordinator"]
    coordinator.api = mock_api
    
    assert coordinator.selected_courses is mock_config_entry.options["courses"]
    assert coordinator.api.access_token == "mock_access_token"
    assert coordinator.api.host == "https://chalmers.instructure.com/api/v1"
    assert coordinator.config_entry is mock_config_entry

    assert mock_config_entry.domain == "instructure"


# def print_hass(hass: HomeAssistant):
#     print_dict_separately(hass.data)

#     print("\n state")
#     print(hass.state)

#     print("\n states")
#     print(hass.states)

#     print("\n data instructure")
#     print(hass.data["instructure"])

#     print("\n data entity_registry")
#     print(hass.data["entity_registry"])

#     print("\n data component")
#     print(hass.data["components"]["instructure"])


# def print_entry(mock_config_entry: MockConfigEntry):
#     print(f"\n Domain: {mock_config_entry.domain}")
#     print(f"\n Entry ID: {mock_config_entry.entry_id}")
#     print(f"\n State: {mock_config_entry.state}")
#     print("\n Entry data:")
#     print(mock_config_entry.data)
#     print("\n Entry options:")
#     print(mock_config_entry.options)


# def print_dict_separately(data_dict):
#     for key, value in data_dict.items():
#         print(f"{key}: {value}")

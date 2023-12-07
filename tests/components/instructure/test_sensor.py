"""Tests for Instucture sensor platform."""

from unittest.mock import patch

import pytest

from homeassistant.core import HomeAssistant

from . import (
    ANNOUNCEMENTS_KEY,
    ASSIGNMENT,
    ASSIGNMENTS_KEY,
    CONVERSATIONS_KEY,
    GRADES_KEY,
    QUICK_LINKS_KEY,
)

from tests.common import MockConfigEntry

new_data = {
    ASSIGNMENTS_KEY: ASSIGNMENT,
    ANNOUNCEMENTS_KEY: {},
    CONVERSATIONS_KEY: {},
    GRADES_KEY: {},
    QUICK_LINKS_KEY: {},
}

pytestmark = pytest.mark.usefixtures("mock_integration")


async def test_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensors."""
    assert mock_config_entry.domain == "instructure"
    coordinator = hass.data["instructure"][mock_config_entry.entry_id]["coordinator"]
    assert coordinator.selected_courses is mock_config_entry.options["courses"]
    assert coordinator.api.access_token == "mock_access_token"
    assert coordinator.api.host == "https://chalmers.instructure.com/api/v1"
    assert coordinator.config_entry is mock_config_entry

    with patch(
        "homeassistant.components.instructure.CanvasUpdateCoordinator.async_update_data",
        return_value=new_data,
    ):
        patch(
            "homeassistant.components.instructure.CanvasAPI.async_get_upcoming_assignments",
            return_value=ASSIGNMENT,
        )

        await coordinator.async_refresh()

    #print_hass(hass)
    assert mock_config_entry.domain == "x"


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

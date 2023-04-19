"""Utilities for Linear Garage Door testing."""

from unittest.mock import patch

from homeassistant.components.linear_garage_door.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def async_init_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Initialize mock integration."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "email": "test-email",
            "password": "test-password",
            "site_id": "test-site-id",
            "device_id": "test-uuid",
        },
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.linear_garage_door.coordinator.Linear.login",
        return_value=True,
    ), patch(
        "homeassistant.components.linear_garage_door.coordinator.Linear.get_devices",
        return_value=[
            {"id": "test1", "name": "Test Garage 1", "subdevices": ["GDO", "Light"]},
            {"id": "test2", "name": "Test Garage 2", "subdevices": ["GDO", "Light"]},
        ],
    ), patch(
        "homeassistant.components.linear_garage_door.coordinator.Linear.get_device_state",
        side_effect=lambda id: {
            "test1": {
                "GDO": {"Open_B": "true", "Open_P": "100"},
                "Light": {"On_B": "true", "On_P": "100"},
            },
            "test2": {
                "GDO": {"Open_B": "false", "Open_P": "0"},
                "Light": {"On_B": "false", "On_P": "0"},
            },
        }[id],
    ), patch(
        "homeassistant.components.linear_garage_door.coordinator.Linear.close",
        return_value=True,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return config_entry

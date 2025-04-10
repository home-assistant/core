"""Tests for the LK Systems integration."""

from unittest.mock import patch

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

VALID_CONFIG = {
    CONF_EMAIL: "test@example.com",
    CONF_PASSWORD: "password123",
}

MOCK_MAIN_DATA = {
    "get_room_deg": ["2100", "2200"],
    "set_room_deg": ["2000", "2100"],
    "active": ["1", "1"],
    "name": ["5A6F6E652031", "5A6F6E652032"],  # Hex-encoded "Zone 1", "Zone 2"
}


def mocked_lk_login():
    """Mock LK API login."""
    return patch("homeassistant.components.lk_systems.LKWebServerAPI.login")


def mocked_lk_get_main_data():
    """Mock fetching main data."""
    return patch(
        "homeassistant.components.lk_systems.LKWebServerAPI.get_main_data",
        return_value=MOCK_MAIN_DATA,
    )


def mocked_lk_setup_entry():
    """Mock setup entry for LK Systems."""
    return patch(
        "homeassistant.components.lk_systems.async_setup_entry",
        return_value=True,
    )

"""Tests for the LIVISI Smart Home integration."""
from unittest.mock import patch

from homeassistant.components.livisi.const import CONF_HOST, CONF_PASSWORD, DOMAIN
from homeassistant.config_entries import ConfigEntry

from tests.common import MockConfigEntry

VALID_CONFIG = {
    CONF_HOST: "1.1.1.1",
    CONF_PASSWORD: "test",
}

DEVICE_CONFIG = {
    "serialNumber": "1234",
    "controllerType": "Classic",
}


def mocked_livisi_login():
    """Create mock for LIVISI login."""
    return patch(
        "homeassistant.components.livisi.config_flow.AioLivisi.async_set_token"
    )


def mocked_livisi_controller():
    """Create mock data for LIVISI controller."""
    return patch(
        "homeassistant.components.livisi.config_flow.AioLivisi.async_get_controller",
        return_value=DEVICE_CONFIG,
    )


def mocked_livisi_setup_entry():
    """Create mock for LIVISI setup entry."""
    return patch(
        "homeassistant.components.livisi.async_setup_entry",
        return_value=True,
    )


def create_entry() -> ConfigEntry:
    """Add config entry in Home Assistant."""
    entry = MockConfigEntry(domain=DOMAIN, data=VALID_CONFIG, entry_id="1234")
    return entry

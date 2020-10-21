"""Tests for the devolo Home Control integration."""
import pytest

from homeassistant.components.devolo_home_control import async_setup_entry
from homeassistant.components.devolo_home_control.const import DOMAIN
from homeassistant.exceptions import ConfigEntryNotReady

from tests.async_mock import patch
from tests.common import MockConfigEntry


async def test_setup_entry_credentials_invalid(hass):
    """Test setup entry fails if credentials are invalid."""
    config = {
        "username": "test-username",
        "password": "test-password",
        "home_control_url": "https://test_url.test",
        "mydevolo_url": "https://test_mydevolo_url.test",
    }
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.devolo_home_control.Mydevolo.credentials_valid",
        return_value=False,
    ):
        await hass.config_entries.async_setup(entry.entry_id)

    assert not hass.data[DOMAIN]


async def test_setup_entry_maintenance(hass):
    """Test setup entry fails if mydevolo is in maintenance mode."""
    config = {
        "username": "test-username",
        "password": "test-password",
        "home_control_url": "https://test_url.test",
        "mydevolo_url": "https://test_mydevolo_url.test",
    }
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.devolo_home_control.Mydevolo.credentials_valid",
        return_value=True,
    ), patch(
        "homeassistant.components.devolo_home_control.Mydevolo.maintenance",
        return_value=True,
    ), pytest.raises(
        ConfigEntryNotReady
    ):
        await async_setup_entry(hass, entry)

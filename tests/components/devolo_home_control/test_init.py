"""Tests for the devolo Home Control integration."""
import pytest

from homeassistant.components.devolo_home_control import async_setup_entry
from homeassistant.components.devolo_home_control.const import DOMAIN
from homeassistant.exceptions import ConfigEntryNotReady

from tests.async_mock import patch
from tests.components.devolo_home_control import configure_integration


async def test_setup_entry_credentials_invalid(hass):
    """Test setup entry fails if credentials are invalid."""
    entry = configure_integration(hass)

    with patch(
        "homeassistant.components.devolo_home_control.Mydevolo.credentials_valid",
        return_value=False,
    ):
        await hass.config_entries.async_setup(entry.entry_id)

    assert not hass.data[DOMAIN]


async def test_setup_entry_maintenance(hass):
    """Test setup entry fails if mydevolo is in maintenance mode."""
    entry = configure_integration(hass)

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

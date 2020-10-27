"""Tests for the devolo Home Control integration."""
import pytest

from homeassistant.components.devolo_home_control import async_setup_entry
from homeassistant.components.devolo_home_control.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from tests.async_mock import patch
from tests.components.devolo_home_control import configure_integration


@pytest.mark.usefixtures("patch_mydevolo")
@pytest.mark.credentials_valid(True)
@pytest.mark.maintenance(False)
async def test_setup_entry(hass: HomeAssistant):
    """Test setup entry."""
    entry = configure_integration(hass)
    with patch("homeassistant.components.devolo_home_control.HomeControl"):
        assert await hass.config_entries.async_setup(entry.entry_id)
        assert hass.data[DOMAIN]


@pytest.mark.usefixtures("patch_mydevolo")
@pytest.mark.credentials_valid(False)
@pytest.mark.maintenance(False)
async def test_setup_entry_credentials_invalid(hass: HomeAssistant):
    """Test setup entry fails if credentials are invalid."""
    entry = configure_integration(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert not hass.data[DOMAIN]


@pytest.mark.usefixtures("patch_mydevolo")
@pytest.mark.credentials_valid(True)
@pytest.mark.maintenance(True)
async def test_setup_entry_maintenance(hass: HomeAssistant):
    """Test setup entry fails if mydevolo is in maintenance mode."""
    entry = configure_integration(hass)
    with pytest.raises(ConfigEntryNotReady):
        await async_setup_entry(hass, entry)


@pytest.mark.usefixtures("patch_mydevolo")
@pytest.mark.credentials_valid(True)
@pytest.mark.maintenance(False)
async def test_setup_connection_error(hass: HomeAssistant):
    """Test setup entry fails on connection error."""
    entry = configure_integration(hass)
    with patch(
        "devolo_home_control_api.homecontrol.HomeControl.__init__",
        side_effect=ConnectionError,
    ), pytest.raises(ConfigEntryNotReady):
        await async_setup_entry(hass, entry)

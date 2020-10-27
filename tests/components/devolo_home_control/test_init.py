"""Tests for the devolo Home Control integration."""
import pytest

from homeassistant.components.devolo_home_control import async_setup_entry
from homeassistant.components.devolo_home_control.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from tests.async_mock import patch
from tests.components.devolo_home_control import configure_integration


@pytest.mark.usefixtures("patch_mydevolo")
async def test_setup_entry(hass: HomeAssistant):
    """Test setup entry."""
    entry = configure_integration(hass)

    with patch(
        "homeassistant.components.devolo_home_control.Mydevolo.maintenance",
        return_value=False,
    ), patch(
        "homeassistant.components.devolo_home_control.Mydevolo.get_gateway_ids",
        return_value=["1400000000000001", "1400000000000002"],
    ), patch(
        "homeassistant.components.devolo_home_control.HomeControl"
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        assert hass.data[DOMAIN]


async def test_setup_entry_credentials_invalid(hass: HomeAssistant):
    """Test setup entry fails if credentials are invalid."""
    entry = configure_integration(hass)

    with patch(
        "homeassistant.components.devolo_home_control.Mydevolo.credentials_valid",
        return_value=False,
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        assert not hass.data[DOMAIN]


async def test_setup_entry_maintenance(hass: HomeAssistant):
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


async def test_setup_connection_error(hass: HomeAssistant):
    """Test setup entry fails on connection error."""
    entry = configure_integration(hass)

    with patch(
        "homeassistant.components.devolo_home_control.Mydevolo.credentials_valid",
        return_value=True,
    ), patch(
        "homeassistant.components.devolo_home_control.Mydevolo.maintenance",
        return_value=False,
    ), patch(
        "homeassistant.components.devolo_home_control.Mydevolo.get_gateway_ids",
        return_value=["1400000000000001", "1400000000000002"],
    ), patch(
        "devolo_home_control_api.homecontrol.HomeControl.__init__",
        return_value=None,
        side_effect=ConnectionError,
    ), pytest.raises(
        ConfigEntryNotReady
    ):
        await async_setup_entry(hass, entry)

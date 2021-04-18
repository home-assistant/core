"""Tests for the devolo Home Control binary sensors."""
from unittest.mock import patch

from homeassistant.components.binary_sensor import DOMAIN
from homeassistant.const import STATE_OFF
from homeassistant.core import HomeAssistant

from . import configure_integration
from .mocks import (
    HomeControlMock,
    HomeControlMockBinarySensor,
    HomeControlMockDisabledBinarySensor,
    HomeControlMockRemoteControl,
)


async def test_setup_entry_binary_sensor(hass: HomeAssistant, mock_zeroconf):
    """Test setup entry with binary sensor device."""
    entry = configure_integration(hass)
    with patch(
        "homeassistant.components.devolo_home_control.HomeControl",
        side_effect=[HomeControlMockBinarySensor, HomeControlMock],
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        state = hass.states.get(f"{DOMAIN}.test")
        assert state is not None
        assert state.state == STATE_OFF


async def test_setup_entry_remote_control(hass: HomeAssistant, mock_zeroconf):
    """Test setup entry with remote control device."""
    entry = configure_integration(hass)
    with patch(
        "homeassistant.components.devolo_home_control.HomeControl",
        side_effect=[HomeControlMockRemoteControl, HomeControlMock],
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert hass.states.get(f"{DOMAIN}.test") is not None


async def test_setup_entry_disabled(hass: HomeAssistant, mock_zeroconf):
    """Test setup entry with disabled device."""
    entry = configure_integration(hass)
    with patch(
        "homeassistant.components.devolo_home_control.HomeControl",
        side_effect=[HomeControlMockDisabledBinarySensor, HomeControlMock],
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert hass.states.get(f"{DOMAIN}.devolo.WarningBinaryFI:Test") is None

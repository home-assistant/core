"""Tests for the devolo Home Control binary sensors."""
from unittest.mock import patch

import pytest

from homeassistant.components.binary_sensor import DOMAIN as COMPONENTS_DOMAIN
from homeassistant.components.devolo_home_control import DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from . import configure_integration
from .mocks import (
    DeviceMock,
    HomeControlMock,
    HomeControlMockBinarySensor,
    HomeControlMockDisabledBinarySensor,
    HomeControlMockRemoteControl,
)


@pytest.mark.usefixtures("mock_zeroconf")
async def test_binary_sensor(hass: HomeAssistant):
    """Test setup and state change of a binary sensor device."""
    entry = configure_integration(hass)
    DeviceMock.available = True
    with patch(
        "homeassistant.components.devolo_home_control.HomeControl",
        side_effect=[HomeControlMockBinarySensor, HomeControlMock],
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(f"{COMPONENTS_DOMAIN}.test")
    assert state is not None
    assert state.state == STATE_OFF

    # Emulate websocket message: sensor turned on
    hass.data[DOMAIN][entry.entry_id]["gateways"][0].publisher.dispatch(
        "Test", ("Test", True)
    )
    await hass.async_block_till_done()

    assert hass.states.get(f"{COMPONENTS_DOMAIN}.test").state == STATE_ON

    # Emulate websocket message: device went offline
    DeviceMock.available = False
    hass.data[DOMAIN][entry.entry_id]["gateways"][0].publisher.dispatch(
        "Test", ("Status", False, "status")
    )
    await hass.async_block_till_done()

    assert hass.states.get(f"{COMPONENTS_DOMAIN}.test").state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("mock_zeroconf")
async def test_remote_control(hass: HomeAssistant):
    """Test setup and state change of a remote control device."""
    entry = configure_integration(hass)
    DeviceMock.available = True
    with patch(
        "homeassistant.components.devolo_home_control.HomeControl",
        side_effect=[HomeControlMockRemoteControl, HomeControlMock],
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(f"{COMPONENTS_DOMAIN}.test")
    assert state is not None
    assert state.state == STATE_OFF

    # Emulate websocket message: button pressed
    hass.data[DOMAIN][entry.entry_id]["gateways"][0].publisher.dispatch(
        "Test", ("Test", 1)
    )
    await hass.async_block_till_done()
    assert hass.states.get(f"{COMPONENTS_DOMAIN}.test").state == STATE_ON

    # Emulate websocket message: button released
    hass.data[DOMAIN][entry.entry_id]["gateways"][0].publisher.dispatch(
        "Test", ("Test", 0)
    )
    await hass.async_block_till_done()
    assert hass.states.get(f"{COMPONENTS_DOMAIN}.test").state == STATE_OFF

    # Emulate websocket message: device went offline
    DeviceMock.available = False
    hass.data[DOMAIN][entry.entry_id]["gateways"][0].publisher.dispatch(
        "Test", ("Status", False, "status")
    )
    await hass.async_block_till_done()

    assert hass.states.get(f"{COMPONENTS_DOMAIN}.test").state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("mock_zeroconf")
async def test_disabled(hass: HomeAssistant):
    """Test setup of a disabled device."""
    entry = configure_integration(hass)
    with patch(
        "homeassistant.components.devolo_home_control.HomeControl",
        side_effect=[HomeControlMockDisabledBinarySensor, HomeControlMock],
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get(f"{COMPONENTS_DOMAIN}.devolo.WarningBinaryFI:Test") is None


@pytest.mark.usefixtures("mock_zeroconf")
async def test_remove_from_hass(hass: HomeAssistant):
    """Test removing entity."""
    entry = configure_integration(hass)
    with patch(
        "homeassistant.components.devolo_home_control.HomeControl",
        side_effect=[HomeControlMockBinarySensor, HomeControlMock],
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        await hass.config_entries.async_remove(entry.entry_id)
        await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    HomeControlMockBinarySensor.publisher.unregister.assert_called_once()

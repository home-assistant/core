"""Tests for the devolo Home Control binary sensors."""
from unittest.mock import patch

import pytest

from homeassistant.components.binary_sensor import DOMAIN as COMPONENTS_DOMAIN
from homeassistant.components.devolo_home_control import DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from .mocks import (
    DeviceMock,
    HomeControlMock,
    HomeControlMockBinarySensor,
    HomeControlMockDisabledBinarySensor,
    HomeControlMockRemoteControl,
)

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_zeroconf")
async def test_binary_sensor(hass: HomeAssistant, entry: MockConfigEntry):
    """Test setup and state change of a binary sensor device."""
    with patch(
        "homeassistant.components.devolo_home_control.HomeControl",
        side_effect=[HomeControlMockBinarySensor, HomeControlMock],
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(f"{COMPONENTS_DOMAIN}.test")
    assert state is not None
    assert state.state == STATE_OFF

    # Emulate websocket message
    hass.data[DOMAIN][entry.entry_id]["gateways"][0].publisher.dispatch(
        "Test", ("Test", True)
    )
    await hass.async_block_till_done()

    assert hass.states.get(f"{COMPONENTS_DOMAIN}.test").state == STATE_ON


@pytest.mark.usefixtures("mock_zeroconf")
async def test_remote_control(hass: HomeAssistant, entry: MockConfigEntry):
    """Test setup and state change of a remote control device."""
    with patch(
        "homeassistant.components.devolo_home_control.HomeControl",
        side_effect=[HomeControlMockRemoteControl, HomeControlMock],
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(f"{COMPONENTS_DOMAIN}.test")
    assert state is not None
    assert state.state == STATE_OFF

    # Emulate websocket message
    hass.data[DOMAIN][entry.entry_id]["gateways"][0].publisher.dispatch(
        "Test", ("Test", 1)
    )
    await hass.async_block_till_done()
    assert hass.states.get(f"{COMPONENTS_DOMAIN}.test").state == STATE_ON

    # Emulate websocket message
    hass.data[DOMAIN][entry.entry_id]["gateways"][0].publisher.dispatch(
        "Test", ("Test", 0)
    )
    await hass.async_block_till_done()
    assert hass.states.get(f"{COMPONENTS_DOMAIN}.test").state == STATE_OFF


@pytest.mark.usefixtures("mock_zeroconf")
async def test_disabled(hass: HomeAssistant, entry: MockConfigEntry):
    """Test setup of a disabled device."""
    with patch(
        "homeassistant.components.devolo_home_control.HomeControl",
        side_effect=[HomeControlMockDisabledBinarySensor, HomeControlMock],
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get(f"{COMPONENTS_DOMAIN}.devolo.WarningBinaryFI:Test") is None


@pytest.mark.usefixtures("mock_zeroconf")
async def test_binary_sensor_device_status(hass: HomeAssistant, entry: MockConfigEntry):
    """Test change of device status."""
    with patch(
        "homeassistant.components.devolo_home_control.HomeControl",
        side_effect=[HomeControlMockBinarySensor, HomeControlMock],
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(f"{COMPONENTS_DOMAIN}.test")
    assert state is not None
    assert state.state == STATE_OFF

    # Emulate websocket message
    DeviceMock.available = False
    hass.data[DOMAIN][entry.entry_id]["gateways"][0].publisher.dispatch(
        "Test", ("Status", False, "status")
    )
    await hass.async_block_till_done()

    assert hass.states.get(f"{COMPONENTS_DOMAIN}.test").state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("mock_zeroconf")
async def test_remote_control_device_status(
    hass: HomeAssistant, entry: MockConfigEntry
):
    """Test change of device status."""
    with patch(
        "homeassistant.components.devolo_home_control.HomeControl",
        side_effect=[HomeControlMockRemoteControl, HomeControlMock],
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(f"{COMPONENTS_DOMAIN}.test")
    assert state is not None
    assert state.state == STATE_OFF

    # Emulate websocket message
    DeviceMock.available = False
    hass.data[DOMAIN][entry.entry_id]["gateways"][0].publisher.dispatch(
        "Test", ("Status", False, "status")
    )
    await hass.async_block_till_done()

    assert hass.states.get(f"{COMPONENTS_DOMAIN}.test").state == STATE_UNAVAILABLE

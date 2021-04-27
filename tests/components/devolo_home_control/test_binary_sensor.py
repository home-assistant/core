"""Tests for the devolo Home Control binary sensors."""
from unittest.mock import patch

from homeassistant.components.binary_sensor import DOMAIN as COMPONENTS_DOMAIN
from homeassistant.components.devolo_home_control import DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from . import configure_integration
from .mocks import (
    HomeControlMock,
    HomeControlMockBinarySensor,
    HomeControlMockDisabledBinarySensor,
    HomeControlMockRemoteControl,
)


async def test_binary_sensor(hass: HomeAssistant, mock_zeroconf):
    """Test setup and state change of a binary sensor device."""
    entry = configure_integration(hass)
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
    await hass.async_add_executor_job(
        hass.data[DOMAIN][entry.entry_id]["gateways"][0].publisher.dispatch,
        "Test",
        ("Test", True),
    )
    await hass.async_block_till_done()

    state = hass.states.get(f"{COMPONENTS_DOMAIN}.test")
    assert state.state == STATE_ON

    await hass.config_entries.async_unload(entry.entry_id)


async def test_remote_control(hass: HomeAssistant, mock_zeroconf):
    """Test setup and state change of a remote control device."""
    entry = configure_integration(hass)
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
    await hass.async_add_executor_job(
        hass.data[DOMAIN][entry.entry_id]["gateways"][0].publisher.dispatch,
        "Test",
        ("Test", 1),
    )
    await hass.async_block_till_done()

    state = hass.states.get(f"{COMPONENTS_DOMAIN}.test")
    assert state.state == STATE_ON

    # Emulate websocket message
    await hass.async_add_executor_job(
        hass.data[DOMAIN][entry.entry_id]["gateways"][0].publisher.dispatch,
        "Test",
        ("Test", 0),
    )
    await hass.async_block_till_done()

    state = hass.states.get(f"{COMPONENTS_DOMAIN}.test")
    assert state.state == STATE_OFF

    await hass.config_entries.async_unload(entry.entry_id)


async def test_disabled(hass: HomeAssistant, mock_zeroconf):
    """Test setup of a disabled device."""
    entry = configure_integration(hass)
    with patch(
        "homeassistant.components.devolo_home_control.HomeControl",
        side_effect=[HomeControlMockDisabledBinarySensor, HomeControlMock],
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get(f"{COMPONENTS_DOMAIN}.devolo.WarningBinaryFI:Test") is None
    await hass.config_entries.async_unload(entry.entry_id)


async def test_binary_sensor_device_status(hass: HomeAssistant, mock_zeroconf):
    """Test change of device status."""
    entry = configure_integration(hass)
    with patch(
        "homeassistant.components.devolo_home_control.HomeControl",
        side_effect=[HomeControlMockBinarySensor, HomeControlMock],
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    with patch(
        "tests.components.devolo_home_control.mocks.DeviceMock.is_online",
        return_value=False,
    ):
        # Emulate websocket message
        await hass.async_add_executor_job(
            hass.data[DOMAIN][entry.entry_id]["gateways"][0].publisher.dispatch,
            "Test",
            ("Status", False, "status"),
        )
        await hass.async_block_till_done()

    state = hass.states.get(f"{COMPONENTS_DOMAIN}.test")
    assert state.state == STATE_UNAVAILABLE

    await hass.config_entries.async_unload(entry.entry_id)


async def test_remote_control_device_status(hass: HomeAssistant, mock_zeroconf):
    """Test change of device status."""
    entry = configure_integration(hass)
    with patch(
        "homeassistant.components.devolo_home_control.HomeControl",
        side_effect=[HomeControlMockRemoteControl, HomeControlMock],
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    with patch(
        "tests.components.devolo_home_control.mocks.DeviceMock.is_online",
        return_value=False,
    ):
        # Emulate websocket message
        await hass.async_add_executor_job(
            hass.data[DOMAIN][entry.entry_id]["gateways"][0].publisher.dispatch,
            "Test",
            ("Status", False, "status"),
        )
        await hass.async_block_till_done()

    state = hass.states.get(f"{COMPONENTS_DOMAIN}.test")
    assert state.state == STATE_UNAVAILABLE

    await hass.config_entries.async_unload(entry.entry_id)

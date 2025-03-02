"""Tests for the devolo Home Control binary sensors."""

from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import configure_integration
from .mocks import (
    HomeControlMock,
    HomeControlMockBinarySensor,
    HomeControlMockDisabledBinarySensor,
    HomeControlMockRemoteControl,
)


@pytest.mark.usefixtures("mock_zeroconf")
async def test_binary_sensor(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, snapshot: SnapshotAssertion
) -> None:
    """Test setup and state change of a binary sensor device."""
    entry = configure_integration(hass)
    test_gateway = HomeControlMockBinarySensor()
    test_gateway.devices["Test"].status = 0
    with patch(
        "homeassistant.components.devolo_home_control.HomeControl",
        side_effect=[test_gateway, HomeControlMock()],
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(f"{BINARY_SENSOR_DOMAIN}.test_door")
    assert state == snapshot
    assert entity_registry.async_get(f"{BINARY_SENSOR_DOMAIN}.test_door") == snapshot

    state = hass.states.get(f"{BINARY_SENSOR_DOMAIN}.test_overload")
    assert state == snapshot
    assert (
        entity_registry.async_get(f"{BINARY_SENSOR_DOMAIN}.test_overload") == snapshot
    )

    # Emulate websocket message: sensor turned on
    test_gateway.publisher.dispatch("Test", ("Test", True))
    await hass.async_block_till_done()
    assert hass.states.get(f"{BINARY_SENSOR_DOMAIN}.test_door").state == STATE_ON

    # Emulate websocket message: device went offline
    test_gateway.devices["Test"].status = 1
    test_gateway.publisher.dispatch("Test", ("Status", False, "status"))
    await hass.async_block_till_done()
    assert (
        hass.states.get(f"{BINARY_SENSOR_DOMAIN}.test_door").state == STATE_UNAVAILABLE
    )


@pytest.mark.usefixtures("mock_zeroconf")
async def test_remote_control(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, snapshot: SnapshotAssertion
) -> None:
    """Test setup and state change of a remote control device."""
    entry = configure_integration(hass)
    test_gateway = HomeControlMockRemoteControl()
    test_gateway.devices["Test"].status = 0
    with patch(
        "homeassistant.components.devolo_home_control.HomeControl",
        side_effect=[test_gateway, HomeControlMock()],
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(f"{BINARY_SENSOR_DOMAIN}.test_button_1")
    assert state == snapshot
    assert (
        entity_registry.async_get(f"{BINARY_SENSOR_DOMAIN}.test_button_1") == snapshot
    )

    # Emulate websocket message: button pressed
    test_gateway.publisher.dispatch("Test", ("Test", 1))
    await hass.async_block_till_done()
    assert hass.states.get(f"{BINARY_SENSOR_DOMAIN}.test_button_1").state == STATE_ON

    # Emulate websocket message: button released
    test_gateway.publisher.dispatch("Test", ("Test", 0))
    await hass.async_block_till_done()
    assert hass.states.get(f"{BINARY_SENSOR_DOMAIN}.test_button_1").state == STATE_OFF

    # Emulate websocket message: device went offline
    test_gateway.devices["Test"].status = 1
    test_gateway.publisher.dispatch("Test", ("Status", False, "status"))
    await hass.async_block_till_done()
    assert (
        hass.states.get(f"{BINARY_SENSOR_DOMAIN}.test_button_1").state
        == STATE_UNAVAILABLE
    )


@pytest.mark.usefixtures("mock_zeroconf")
async def test_disabled(hass: HomeAssistant) -> None:
    """Test setup of a disabled device."""
    entry = configure_integration(hass)
    with patch(
        "homeassistant.components.devolo_home_control.HomeControl",
        side_effect=[HomeControlMockDisabledBinarySensor(), HomeControlMock()],
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get(f"{BINARY_SENSOR_DOMAIN}.test_door") is None


@pytest.mark.usefixtures("mock_zeroconf")
async def test_remove_from_hass(hass: HomeAssistant) -> None:
    """Test removing entity."""
    entry = configure_integration(hass)
    test_gateway = HomeControlMockBinarySensor()
    with patch(
        "homeassistant.components.devolo_home_control.HomeControl",
        side_effect=[test_gateway, HomeControlMock()],
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(f"{BINARY_SENSOR_DOMAIN}.test_door")
    assert state is not None
    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    assert test_gateway.publisher.unregister.call_count == 2

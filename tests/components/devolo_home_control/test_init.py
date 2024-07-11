"""Tests for the devolo Home Control integration."""

from unittest.mock import patch

from devolo_home_control_api.exceptions.gateway import GatewayOfflineError
import pytest

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.devolo_home_control.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from . import configure_integration
from .mocks import HomeControlMock, HomeControlMockBinarySensor

from tests.typing import WebSocketGenerator


@pytest.mark.usefixtures("mock_zeroconf")
async def test_setup_entry(hass: HomeAssistant) -> None:
    """Test setup entry."""
    entry = configure_integration(hass)
    with patch("homeassistant.components.devolo_home_control.HomeControl"):
        await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state is ConfigEntryState.LOADED


@pytest.mark.parametrize("credentials_valid", [False])
async def test_setup_entry_credentials_invalid(hass: HomeAssistant) -> None:
    """Test setup entry fails if credentials are invalid."""
    entry = configure_integration(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.parametrize("maintenance", [True])
async def test_setup_entry_maintenance(hass: HomeAssistant) -> None:
    """Test setup entry fails if mydevolo is in maintenance mode."""
    entry = configure_integration(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("mock_zeroconf")
async def test_setup_gateway_offline(hass: HomeAssistant) -> None:
    """Test setup entry fails on gateway offline."""
    entry = configure_integration(hass)
    with patch(
        "homeassistant.components.devolo_home_control.HomeControl",
        side_effect=GatewayOfflineError,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test unload entry."""
    entry = configure_integration(hass)
    with patch("homeassistant.components.devolo_home_control.HomeControl"):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        await hass.config_entries.async_unload(entry.entry_id)
        assert entry.state is ConfigEntryState.NOT_LOADED


async def test_home_assistant_stop(hass: HomeAssistant) -> None:
    """Test home assistant stop."""
    entry = configure_integration(hass)
    test_gateway = HomeControlMock()
    test_gateway2 = HomeControlMock()
    with patch(
        "homeassistant.components.devolo_home_control.HomeControl",
        side_effect=[test_gateway, test_gateway2],
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()
        assert test_gateway.websocket_disconnect.called
        assert test_gateway2.websocket_disconnect.called


async def test_remove_device(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test removing a device."""
    assert await async_setup_component(hass, "config", {})
    entry = configure_integration(hass)
    test_gateway = HomeControlMockBinarySensor()
    with patch(
        "homeassistant.components.devolo_home_control.HomeControl",
        side_effect=[test_gateway, HomeControlMock()],
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        device_entry = device_registry.async_get_device(identifiers={(DOMAIN, "Test")})
        assert device_entry

        client = await hass_ws_client(hass)
        response = await client.remove_device(device_entry.id, entry.entry_id)
        assert response["success"]
        assert device_registry.async_get_device(identifiers={(DOMAIN, "Test")}) is None
        assert hass.states.get(f"{BINARY_SENSOR_DOMAIN}.test") is None

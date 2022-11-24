"""Tests for the devolo spencer Control integration."""
from collections.abc import Awaitable, Callable
from unittest.mock import patch

from aiohttp import ClientWebSocketResponse
from devolo_spencer_control_api.exceptions.gateway import GatewayOfflineError
import pytest

from spencerassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from spencerassistant.components.devolo_spencer_control import DOMAIN
from spencerassistant.config_entries import ConfigEntryState
from spencerassistant.core import spencerAssistant
from spencerassistant.helpers import device_registry as dr
from spencerassistant.setup import async_setup_component

from . import configure_integration
from .mocks import spencerControlMock, spencerControlMockBinarySensor


async def test_setup_entry(hass: spencerAssistant, mock_zeroconf):
    """Test setup entry."""
    entry = configure_integration(hass)
    with patch("spencerassistant.components.devolo_spencer_control.spencerControl"):
        await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state is ConfigEntryState.LOADED


@pytest.mark.credentials_invalid
async def test_setup_entry_credentials_invalid(hass: spencerAssistant):
    """Test setup entry fails if credentials are invalid."""
    entry = configure_integration(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.maintenance
async def test_setup_entry_maintenance(hass: spencerAssistant):
    """Test setup entry fails if mydevolo is in maintenance mode."""
    entry = configure_integration(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_gateway_offline(hass: spencerAssistant, mock_zeroconf):
    """Test setup entry fails on gateway offline."""
    entry = configure_integration(hass)
    with patch(
        "spencerassistant.components.devolo_spencer_control.spencerControl",
        side_effect=GatewayOfflineError,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(hass: spencerAssistant):
    """Test unload entry."""
    entry = configure_integration(hass)
    with patch("spencerassistant.components.devolo_spencer_control.spencerControl"):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        await hass.config_entries.async_unload(entry.entry_id)
        assert entry.state is ConfigEntryState.NOT_LOADED


async def test_remove_device(
    hass: spencerAssistant,
    hass_ws_client: Callable[[spencerAssistant], Awaitable[ClientWebSocketResponse]],
):
    """Test removing a device."""
    assert await async_setup_component(hass, "config", {})
    entry = configure_integration(hass)
    test_gateway = spencerControlMockBinarySensor()
    with patch(
        "spencerassistant.components.devolo_spencer_control.spencerControl",
        side_effect=[test_gateway, spencerControlMock()],
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        device_registry = dr.async_get(hass)
        device_entry = device_registry.async_get_device(identifiers={(DOMAIN, "Test")})
        assert device_entry

        client = await hass_ws_client(hass)
        await client.send_json(
            {
                "id": 1,
                "type": "config/device_registry/remove_config_entry",
                "config_entry_id": entry.entry_id,
                "device_id": device_entry.id,
            }
        )
        response = await client.receive_json()
        assert response["success"]
        assert device_registry.async_get_device(identifiers={(DOMAIN, "Test")}) is None
        assert hass.states.get(f"{BINARY_SENSOR_DOMAIN}.test") is None

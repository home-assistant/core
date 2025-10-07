"""Tests for the Fluss Buttons."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from fluss_api import FlussApiClient
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.fluss.button import async_setup_entry
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("init_integration")


@pytest.mark.asyncio
async def test_async_setup_entry_multiple_devices(
    hass: HomeAssistant,
    mock_api_client: FlussApiClient,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test setup with multiple devices."""
    mock_api_client.async_get_devices.return_value = {
        "devices": [
            {"deviceId": "2a303030sdj1", "deviceName": "Device 1"},
            {"deviceId": "ape93k9302j2", "deviceName": "Device 2"},
        ]
    }

    with patch("fluss_api.FlussApiClient", return_value=mock_api_client):
        assert await async_setup_entry(hass, init_integration, MagicMock())
        await hass.async_block_till_done()

    state1 = hass.states.get("button.device_1")
    assert state1
    assert state1 == snapshot(name="device1_state")

    state2 = hass.states.get("button.device_2")
    assert state2
    assert state2 == snapshot(name="device2_state")


@pytest.mark.asyncio
async def test_button_press_success(
    hass: HomeAssistant,
    mock_api_client: FlussApiClient,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test successful button press."""
    state = hass.states.get("button.test_device")
    assert state
    assert state == snapshot(name="button_state")

    entry_reg = entity_registry.async_get(state.entity_id)
    assert entry_reg
    assert entry_reg.device_info == snapshot(name="device_info")

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.test_device"},
        blocking=True,
    )

    mock_api_client.async_trigger_device.assert_called_once_with("1")


@pytest.mark.asyncio
async def test_button_press_error(
    hass: HomeAssistant,
    mock_api_client: FlussApiClient,
    init_integration: MockConfigEntry,
) -> None:
    """Test button press with API error."""
    state = hass.states.get("button.test_device")
    assert state

    mock_api_client.async_trigger_device.side_effect = Exception("API Boom")

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.test_device"},
            blocking=True,
        )
    assert "button_error" in str(exc_info.value)


@pytest.mark.asyncio
async def test_no_devices_setup(
    hass: HomeAssistant,
    mock_api_client: FlussApiClient,
    init_integration: MockConfigEntry,
) -> None:
    """Test setup with no devices."""
    mock_api_client.async_get_devices.return_value = {"devices": []}

    with patch("fluss_api.FlussApiClient", return_value=mock_api_client):
        assert await async_setup_entry(hass, init_integration, MagicMock())
        await hass.async_block_till_done()

    assert hass.states.get("button.test_device") is None


@pytest.mark.asyncio
async def test_unload_entry(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test unloading the entry."""
    assert init_integration.state is ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()
    assert init_integration.state is ConfigEntryState.NOT_LOADED
    assert hass.states.get("button.test_device") is None
"""Tests for the Fluss Buttons."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fluss_api import FlussApiClient, FlussApiClientError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.asyncio
async def test_async_setup_entry_multiple_devices(
    hass: HomeAssistant,
    mock_api_client_multiple_devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test setup with multiple devices."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_api_client_multiple_devices.async_get_devices.assert_called_once()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


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

    device_registry = dr.async_get(hass)
    device = device_registry.async_get(entry_reg.device_id)
    assert device == snapshot(name="device_info")

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

    mock_api_client.async_trigger_device.side_effect = FlussApiClientError("API Boom")

    with pytest.raises(HomeAssistantError, match="Failed to trigger device: API Boom"):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.test_device"},
            blocking=True,
        )


@pytest.mark.asyncio
async def test_no_devices_setup(
    hass: HomeAssistant,
    mock_api_client: FlussApiClient,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup with no devices."""
    mock_api_client.async_get_devices.return_value = {"devices": []}
    mock_config_entry.add_to_hass(hass)

    with patch("fluss_api.FlussApiClient", return_value=mock_api_client):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
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

    state = hass.states.get("button.test_device")
    if state:
        assert state.state == "unavailable"
        assert state.attributes.get("restored") is True
    else:
        assert state is None

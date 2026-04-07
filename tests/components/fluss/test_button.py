"""Tests for the Fluss Buttons."""

from __future__ import annotations

from unittest.mock import AsyncMock

from fluss_api import FlussApiClient, FlussApiClientError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_buttons(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test button entities are created for devices without openCloseStatus."""
    # Override: no valid openCloseStatus → button fallback
    mock_api_client.async_get_device_status.side_effect = None
    mock_api_client.async_get_device_status.return_value = {}

    await setup_integration(hass, mock_config_entry, [Platform.BUTTON])

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_button_press(
    hass: HomeAssistant,
    mock_api_client: FlussApiClient,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful button press."""
    mock_api_client.async_get_device_status.side_effect = None
    mock_api_client.async_get_device_status.return_value = {}

    await setup_integration(hass, mock_config_entry, [Platform.BUTTON])

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.device_1_trigger"},
        blocking=True,
    )

    mock_api_client.async_trigger_device.assert_called_once_with("2a303030sdj1")


async def test_button_press_error(
    hass: HomeAssistant,
    mock_api_client: FlussApiClient,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test button press with API error."""
    mock_api_client.async_get_device_status.side_effect = None
    mock_api_client.async_get_device_status.return_value = {}

    await setup_integration(hass, mock_config_entry, [Platform.BUTTON])

    mock_api_client.async_trigger_device.side_effect = FlussApiClientError("API Boom")

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.device_1_trigger"},
            blocking=True,
        )


async def test_no_button_when_cover_status_available(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that no button entities are created when openCloseStatus is present."""
    # Default fixture has openCloseStatus → should produce covers, not buttons
    await setup_integration(hass, mock_config_entry, [Platform.BUTTON])

    assert hass.states.get("button.device_1_trigger") is None
    assert hass.states.get("button.device_2_trigger") is None

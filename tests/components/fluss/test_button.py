"""Tests for the Fluss Buttons."""

from __future__ import annotations

from unittest.mock import AsyncMock

from fluss_api import FlussApiClient, FlussApiClientError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID
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
    """Test setup with multiple devices."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_button_press(
    hass: HomeAssistant,
    mock_api_client: FlussApiClient,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful button press."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.device_1"},
        blocking=True,
    )

    mock_api_client.async_trigger_device.assert_called_once_with("2a303030sdj1")


async def test_button_press_error(
    hass: HomeAssistant,
    mock_api_client: FlussApiClient,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test button press with API error."""
    await setup_integration(hass, mock_config_entry)

    mock_api_client.async_trigger_device.side_effect = FlussApiClientError("API Boom")

    with pytest.raises(HomeAssistantError, match="Failed to trigger device: API Boom"):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.device_1"},
            blocking=True,
        )

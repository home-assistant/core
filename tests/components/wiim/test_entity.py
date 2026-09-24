"""Tests for WiiM entities."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.wiim.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_wiim_controller")
async def test_device_info_uses_http_api_url(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wiim_device: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the HTTP API URL is used when no presentation URL is available."""
    mock_wiim_device.presentation_url = None

    await setup_integration(hass, mock_config_entry)

    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_wiim_device.udn), mock_config_entry.entry_id
    )
    assert device_entry is not None
    assert device_entry.configuration_url == mock_wiim_device.http_api_url

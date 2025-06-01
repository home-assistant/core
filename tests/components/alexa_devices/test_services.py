"""Tests for Amazon Devices services."""

from unittest.mock import AsyncMock

from homeassistant.components.amazon_devices.const import DOMAIN
from homeassistant.components.amazon_devices.services import (
    SERVICE_SOUND_NOTIFICATION,
    SERVICE_TEXT_COMMAND,
)
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_setup_services(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup of Fritz!Tools services."""
    await setup_integration(hass, mock_config_entry)

    assert (services := hass.services.async_services_for_domain(DOMAIN))
    assert SERVICE_TEXT_COMMAND in services
    assert SERVICE_SOUND_NOTIFICATION in services

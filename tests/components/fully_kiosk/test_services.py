"""Test Fully Kiosk Browser services."""
from unittest.mock import MagicMock

from homeassistant.components.fully_kiosk.const import (
    ATTR_APPLICATION,
    ATTR_URL,
    DOMAIN,
    SERVICE_LOAD_URL,
    SERVICE_START_APPLICATION,
)
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


async def test_services(
    hass: HomeAssistant,
    mock_fully_kiosk: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test the Fully Kiosk Browser services."""
    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, "abcdef-123456")}
    )

    assert device_entry

    await hass.services.async_call(
        DOMAIN,
        SERVICE_LOAD_URL,
        {ATTR_DEVICE_ID: [device_entry.id], ATTR_URL: "https://example.com"},
        blocking=True,
    )

    assert len(mock_fully_kiosk.loadUrl.mock_calls) == 1

    await hass.services.async_call(
        DOMAIN,
        SERVICE_START_APPLICATION,
        {ATTR_DEVICE_ID: [device_entry.id], ATTR_APPLICATION: "de.ozerov.fully"},
        blocking=True,
    )

    assert len(mock_fully_kiosk.startApplication.mock_calls) == 1

"""Test Fully Kiosk Browser services."""
from unittest.mock import MagicMock

import pytest

from homeassistant.components.fully_kiosk.const import (
    ATTR_APPLICATION,
    ATTR_URL,
    DOMAIN,
    SERVICE_LOAD_URL,
    SERVICE_START_APPLICATION,
)
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
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

    url = "https://example.com"
    await hass.services.async_call(
        DOMAIN,
        SERVICE_LOAD_URL,
        {ATTR_DEVICE_ID: [device_entry.id], ATTR_URL: url},
        blocking=True,
    )

    mock_fully_kiosk.loadUrl.assert_called_once_with(url)

    app = "de.ozerov.fully"
    await hass.services.async_call(
        DOMAIN,
        SERVICE_START_APPLICATION,
        {ATTR_DEVICE_ID: [device_entry.id], ATTR_APPLICATION: app},
        blocking=True,
    )

    mock_fully_kiosk.startApplication.assert_called_once_with(app)


async def test_service_unloaded_entry(
    hass: HomeAssistant,
    mock_fully_kiosk: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test service not called when config entry unloaded."""
    await init_integration.async_unload(hass)

    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, "abcdef-123456")}
    )

    assert device_entry

    await hass.services.async_call(
        DOMAIN,
        SERVICE_LOAD_URL,
        {ATTR_DEVICE_ID: [device_entry.id], ATTR_URL: "https://nabucasa.com"},
        blocking=True,
    )

    mock_fully_kiosk.loadUrl.assert_not_called()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_START_APPLICATION,
        {ATTR_DEVICE_ID: [device_entry.id], ATTR_APPLICATION: "de.ozerov.fully"},
        blocking=True,
    )
    mock_fully_kiosk.startApplication.assert_not_called()


async def test_service_bad_device_id(
    hass: HomeAssistant,
    mock_fully_kiosk: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test Fully Kiosk Browser service invocation with bad device id."""
    with pytest.raises(HomeAssistantError) as excinfo:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_LOAD_URL,
            {ATTR_DEVICE_ID: ["bad-device_id"], ATTR_URL: "https://example.com"},
            blocking=True,
        )

    assert "Device 'bad-device_id' not found in device registry" in str(excinfo)

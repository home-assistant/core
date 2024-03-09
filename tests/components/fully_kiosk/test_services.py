"""Test Fully Kiosk Browser services."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.fully_kiosk.const import (
    ATTR_APPLICATION,
    ATTR_KEY,
    ATTR_URL,
    ATTR_VALUE,
    DOMAIN,
    SERVICE_LOAD_URL,
    SERVICE_SET_CONFIG,
    SERVICE_START_APPLICATION,
)
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


async def test_services(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_fully_kiosk: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test the Fully Kiosk Browser services."""
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

    key = "test_key"
    value = "test_value"

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_CONFIG,
        {
            ATTR_DEVICE_ID: [device_entry.id],
            ATTR_KEY: key,
            ATTR_VALUE: value,
        },
        blocking=True,
    )

    mock_fully_kiosk.setConfigurationString.assert_called_once_with(key, value)

    key = "test_key"
    value = "true"
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_CONFIG,
        {
            ATTR_DEVICE_ID: [device_entry.id],
            ATTR_KEY: key,
            ATTR_VALUE: value,
        },
        blocking=True,
    )

    mock_fully_kiosk.setConfigurationBool.assert_called_once_with(key, value)

    key = "test_key"
    value = True
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_CONFIG,
        {
            ATTR_DEVICE_ID: [device_entry.id],
            ATTR_KEY: key,
            ATTR_VALUE: value,
        },
        blocking=True,
    )

    mock_fully_kiosk.setConfigurationBool.assert_called_with(key, value)


async def test_service_unloaded_entry(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_fully_kiosk: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test service not called when config entry unloaded."""
    await init_integration.async_unload(hass)

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, "abcdef-123456")}
    )

    assert device_entry

    with pytest.raises(HomeAssistantError) as excinfo:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_LOAD_URL,
            {ATTR_DEVICE_ID: [device_entry.id], ATTR_URL: "https://nabucasa.com"},
            blocking=True,
        )
    assert "Test device is not loaded" in str(excinfo)
    mock_fully_kiosk.loadUrl.assert_not_called()

    with pytest.raises(HomeAssistantError) as excinfo:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_START_APPLICATION,
            {ATTR_DEVICE_ID: [device_entry.id], ATTR_APPLICATION: "de.ozerov.fully"},
            blocking=True,
        )
    assert "Test device is not loaded" in str(excinfo)
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


async def test_service_called_with_non_fkb_target_devices(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_fully_kiosk: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Services raise exception when no valid devices provided."""
    other_domain = "NotFullyKiosk"
    other_config_id = "555"
    other_mock_config_entry = MockConfigEntry(
        title="Not Fully Kiosk", domain=other_domain, entry_id=other_config_id
    )
    other_mock_config_entry.add_to_hass(hass)

    device_entry = device_registry.async_get_or_create(
        config_entry_id=other_config_id,
        identifiers={
            (other_domain, 1),
        },
    )

    with pytest.raises(HomeAssistantError) as excinfo:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_LOAD_URL,
            {
                ATTR_DEVICE_ID: [device_entry.id],
                ATTR_URL: "https://example.com",
            },
            blocking=True,
        )

    assert f"Device '{device_entry.id}' is not a fully_kiosk device" in str(excinfo)

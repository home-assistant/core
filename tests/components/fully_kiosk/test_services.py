"""Test Fully Kiosk Browser services."""

from unittest.mock import MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.fully_kiosk.const import DOMAIN
from homeassistant.components.fully_kiosk.services import (
    FullyKioskService,
    FullyKioskServiceArgument,
)
from homeassistant.const import CommonServiceArgument
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr


async def test_services(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_fully_kiosk: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test the Fully Kiosk Browser services."""
    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, "abcdef-123456"), init_integration.entry_id
    )

    assert device_entry

    url = "https://example.com"
    await hass.services.async_call(
        DOMAIN,
        FullyKioskService.LOAD_URL,
        {
            CommonServiceArgument.DEVICE_ID: [device_entry.id],
            FullyKioskServiceArgument.URL: url,
        },
        blocking=True,
    )

    mock_fully_kiosk.loadUrl.assert_called_once_with(url)

    app = "de.ozerov.fully"
    await hass.services.async_call(
        DOMAIN,
        FullyKioskService.START_APPLICATION,
        {
            CommonServiceArgument.DEVICE_ID: [device_entry.id],
            FullyKioskServiceArgument.APPLICATION: app,
        },
        blocking=True,
    )

    mock_fully_kiosk.startApplication.assert_called_once_with(app)

    key = "test_key"
    value = "test_value"

    await hass.services.async_call(
        DOMAIN,
        FullyKioskService.SET_CONFIG,
        {
            CommonServiceArgument.DEVICE_ID: [device_entry.id],
            FullyKioskServiceArgument.KEY: key,
            FullyKioskServiceArgument.VALUE: value,
        },
        blocking=True,
    )

    mock_fully_kiosk.setConfigurationString.assert_called_once_with(key, value)

    key = "test_key"
    value = 1234

    await hass.services.async_call(
        DOMAIN,
        FullyKioskService.SET_CONFIG,
        {
            CommonServiceArgument.DEVICE_ID: [device_entry.id],
            FullyKioskServiceArgument.KEY: key,
            FullyKioskServiceArgument.VALUE: value,
        },
        blocking=True,
    )

    mock_fully_kiosk.setConfigurationString.assert_called_with(key, str(value))

    key = "test_key"
    value = "true"
    await hass.services.async_call(
        DOMAIN,
        FullyKioskService.SET_CONFIG,
        {
            CommonServiceArgument.DEVICE_ID: [device_entry.id],
            FullyKioskServiceArgument.KEY: key,
            FullyKioskServiceArgument.VALUE: value,
        },
        blocking=True,
    )

    mock_fully_kiosk.setConfigurationBool.assert_called_once_with(key, value)

    key = "test_key"
    value = True
    await hass.services.async_call(
        DOMAIN,
        FullyKioskService.SET_CONFIG,
        {
            CommonServiceArgument.DEVICE_ID: [device_entry.id],
            FullyKioskServiceArgument.KEY: key,
            FullyKioskServiceArgument.VALUE: value,
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
    await hass.config_entries.async_unload(init_integration.entry_id)

    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, "abcdef-123456"), init_integration.entry_id
    )

    assert device_entry

    with pytest.raises(HomeAssistantError) as excinfo:
        await hass.services.async_call(
            DOMAIN,
            FullyKioskService.LOAD_URL,
            {
                CommonServiceArgument.DEVICE_ID: [device_entry.id],
                FullyKioskServiceArgument.URL: "https://nabucasa.com",
            },
            blocking=True,
        )
    assert excinfo.value.translation_domain == HOMEASSISTANT_DOMAIN
    assert excinfo.value.translation_key == "service_config_entry_not_loaded"
    mock_fully_kiosk.loadUrl.assert_not_called()

    with pytest.raises(HomeAssistantError) as excinfo:
        await hass.services.async_call(
            DOMAIN,
            FullyKioskService.START_APPLICATION,
            {
                CommonServiceArgument.DEVICE_ID: [device_entry.id],
                FullyKioskServiceArgument.APPLICATION: "de.ozerov.fully",
            },
            blocking=True,
        )
    assert excinfo.value.translation_domain == HOMEASSISTANT_DOMAIN
    assert excinfo.value.translation_key == "service_config_entry_not_loaded"
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
            FullyKioskService.LOAD_URL,
            {
                CommonServiceArgument.DEVICE_ID: ["bad-device_id"],
                FullyKioskServiceArgument.URL: "https://example.com",
            },
            blocking=True,
        )

    assert excinfo.value.translation_domain == HOMEASSISTANT_DOMAIN
    assert excinfo.value.translation_key == "service_device_not_found"
    assert excinfo.value.translation_placeholders == {"device_id": "bad-device_id"}


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
            FullyKioskService.LOAD_URL,
            {
                CommonServiceArgument.DEVICE_ID: [device_entry.id],
                FullyKioskServiceArgument.URL: "https://example.com",
            },
            blocking=True,
        )

    assert excinfo.value.translation_domain == HOMEASSISTANT_DOMAIN
    assert excinfo.value.translation_key == "service_device_wrong_domain"
    assert excinfo.value.translation_placeholders == {
        "device_name": device_entry.name,
        "domain": DOMAIN,
    }

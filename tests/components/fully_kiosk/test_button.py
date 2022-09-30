"""Test the Fully Kiosk Browser buttons."""
from unittest.mock import MagicMock

import homeassistant.components.button as button
from homeassistant.components.fully_kiosk.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


async def test_buttons(
    hass: HomeAssistant,
    mock_fully_kiosk: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test standard Fully Kiosk buttons."""
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    entry = entity_registry.async_get("button.amazon_fire_restart_browser")
    assert entry
    assert entry.unique_id == "abcdef-123456-restartApp"
    await call_service(hass, "press", "button.amazon_fire_restart_browser")
    assert len(mock_fully_kiosk.restartApp.mock_calls) == 1

    entry = entity_registry.async_get("button.amazon_fire_reboot_device")
    assert entry
    assert entry.unique_id == "abcdef-123456-rebootDevice"
    await call_service(hass, "press", "button.amazon_fire_reboot_device")
    assert len(mock_fully_kiosk.rebootDevice.mock_calls) == 1

    entry = entity_registry.async_get("button.amazon_fire_bring_to_foreground")
    assert entry
    assert entry.unique_id == "abcdef-123456-toForeground"
    await call_service(hass, "press", "button.amazon_fire_bring_to_foreground")
    assert len(mock_fully_kiosk.toForeground.mock_calls) == 1

    entry = entity_registry.async_get("button.amazon_fire_send_to_background")
    assert entry
    assert entry.unique_id == "abcdef-123456-toBackground"
    await call_service(hass, "press", "button.amazon_fire_send_to_background")
    assert len(mock_fully_kiosk.toBackground.mock_calls) == 1

    entry = entity_registry.async_get("button.amazon_fire_load_start_url")
    assert entry
    assert entry.unique_id == "abcdef-123456-loadStartUrl"
    await call_service(hass, "press", "button.amazon_fire_load_start_url")
    assert len(mock_fully_kiosk.loadStartUrl.mock_calls) == 1

    assert entry.device_id
    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.configuration_url == "http://192.168.1.234:2323"
    assert device_entry.entry_type is None
    assert device_entry.hw_version is None
    assert device_entry.identifiers == {(DOMAIN, "abcdef-123456")}
    assert device_entry.manufacturer == "amzn"
    assert device_entry.model == "KFDOWI"
    assert device_entry.name == "Amazon Fire"
    assert device_entry.sw_version == "1.42.5"


def call_service(hass, service, entity_id):
    """Call any service on entity."""
    return hass.services.async_call(
        button.DOMAIN, service, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )

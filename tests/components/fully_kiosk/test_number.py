"""Test the Fully Kiosk Browser number entities."""

from unittest.mock import MagicMock

from homeassistant.components import number
from homeassistant.components.fully_kiosk.const import DOMAIN, UPDATE_INTERVAL
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_numbers(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_fully_kiosk: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test standard Fully Kiosk numbers."""
    state = hass.states.get("number.amazon_fire_screensaver_timer")
    assert state
    assert state.state == "900"
    entry = entity_registry.async_get("number.amazon_fire_screensaver_timer")
    assert entry
    assert entry.unique_id == "abcdef-123456-timeToScreensaverV2"
    await set_value(hass, "number.amazon_fire_screensaver_timer", 600)
    assert len(mock_fully_kiosk.setConfigurationString.mock_calls) == 1

    state = hass.states.get("number.amazon_fire_screensaver_brightness")
    assert state
    assert state.state == "0"
    entry = entity_registry.async_get("number.amazon_fire_screensaver_brightness")
    assert entry
    assert entry.unique_id == "abcdef-123456-screensaverBrightness"

    state = hass.states.get("number.amazon_fire_screen_off_timer")
    assert state
    assert state.state == "0"
    entry = entity_registry.async_get("number.amazon_fire_screen_off_timer")
    assert entry
    assert entry.unique_id == "abcdef-123456-timeToScreenOffV2"

    state = hass.states.get("number.amazon_fire_screen_brightness")
    assert state
    assert state.state == "9"
    entry = entity_registry.async_get("number.amazon_fire_screen_brightness")
    assert entry
    assert entry.unique_id == "abcdef-123456-screenBrightness"

    # Test invalid numeric data
    mock_fully_kiosk.getSettings.return_value = {"screenBrightness": "invalid"}
    async_fire_time_changed(hass, dt_util.utcnow() + UPDATE_INTERVAL)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("number.amazon_fire_screen_brightness")
    assert state
    assert state.state == STATE_UNKNOWN

    # Test unknown/missing data
    mock_fully_kiosk.getSettings.return_value = {}
    async_fire_time_changed(hass, dt_util.utcnow() + UPDATE_INTERVAL)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("number.amazon_fire_screensaver_timer")
    assert state
    assert state.state == STATE_UNKNOWN

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


def set_value(hass, entity_id, value):
    """Set the value of a number entity."""
    return hass.services.async_call(
        number.DOMAIN,
        "set_value",
        {ATTR_ENTITY_ID: entity_id, number.ATTR_VALUE: value},
        blocking=True,
    )

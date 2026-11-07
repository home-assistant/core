"""Tests for Daikin sensor entities."""

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.daikin.const import DOMAIN, KEY_MAC
from homeassistant.const import CONF_HOST, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from .conftest import ZoneDevice

HOST = "127.0.0.1"
HUMIDITY_ENTITY_ID = "sensor.daikin_test_humidity"
TARGET_HUMIDITY_ENTITY_ID = "sensor.daikin_test_target_humidity"


async def _async_setup_daikin(hass: HomeAssistant, zone_device: ZoneDevice) -> None:
    """Set up a Daikin config entry with a mocked library device."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=zone_device.mac,
        data={CONF_HOST: HOST, KEY_MAC: zone_device.mac},
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("target_humidity", "expected_state"),
    [
        pytest.param(50.0, "50.0", id="target"),
        pytest.param(40.0, "40.0", id="room-at-target"),
        pytest.param(None, STATE_UNKNOWN, id="no-target-in-this-mode"),
    ],
)
async def test_target_humidity(
    hass: HomeAssistant,
    zone_device: ZoneDevice,
    target_humidity: float | None,
    expected_state: str,
) -> None:
    """Test the target humidity sensor reports the target, not the room humidity."""
    zone_device.support_humidity = True
    zone_device.support_target_humidity = True
    zone_device.humidity = 40.0
    zone_device.target_humidity = target_humidity

    await _async_setup_daikin(hass, zone_device)

    assert hass.states.get(HUMIDITY_ENTITY_ID).state == "40.0"
    assert hass.states.get(TARGET_HUMIDITY_ENTITY_ID).state == expected_state


async def test_target_humidity_not_created_without_target(
    hass: HomeAssistant, zone_device: ZoneDevice
) -> None:
    """Test devices that do not report a humidity target get no target sensor."""
    zone_device.support_humidity = True
    zone_device.support_target_humidity = False
    zone_device.humidity = 40.0

    await _async_setup_daikin(hass, zone_device)

    assert hass.states.get(HUMIDITY_ENTITY_ID).state == "40.0"
    assert hass.states.get(TARGET_HUMIDITY_ENTITY_ID) is None


async def test_target_humidity_not_created_without_humidity(
    hass: HomeAssistant, zone_device: ZoneDevice
) -> None:
    """Test devices without a humidity sensor get no target sensor either."""
    zone_device.support_humidity = False
    zone_device.support_target_humidity = True
    zone_device.target_humidity = 50.0

    await _async_setup_daikin(hass, zone_device)

    assert hass.states.get(HUMIDITY_ENTITY_ID) is None
    assert hass.states.get(TARGET_HUMIDITY_ENTITY_ID) is None

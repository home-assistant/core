"""Test Lock Nano entities from protocol advertisements."""

from collections.abc import Callable
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.bluetooth import inject_bluetooth_service_info
from switchbot import parse_advertisement_data

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.const import ATTR_DEVICE_CLASS, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from . import LOCK_NANO_SERVICE_INFO


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_lock_nano_advertisement_entities(
    hass: HomeAssistant,
    mock_entry_encrypted_factory: Callable[..., MockConfigEntry],
) -> None:
    """Expose battery and charging without deriving a door sensor from reserved bits."""
    advertisement = LOCK_NANO_SERVICE_INFO
    parsed = parse_advertisement_data(advertisement.device, advertisement.advertisement)
    assert parsed.data["modelName"].value == "Lock Nano"
    inject_bluetooth_service_info(hass, advertisement)
    entry = mock_entry_encrypted_factory(sensor_type="lock_nano")
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.switchbot.lock.switchbot.SwitchbotLock.update",
        new=AsyncMock(),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get("sensor.test_name_battery").state == "100"
    charging = [
        entity
        for entity in hass.states.async_all("binary_sensor")
        if entity.attributes.get(ATTR_DEVICE_CLASS)
        == BinarySensorDeviceClass.BATTERY_CHARGING
    ]
    assert len(charging) == 1
    assert charging[0].state == STATE_OFF
    assert hass.states.get("binary_sensor.test_name_unlocked_alarm").state == STATE_ON
    assert not any(
        entity.attributes.get(ATTR_DEVICE_CLASS) == BinarySensorDeviceClass.DOOR
        for entity in hass.states.async_all("binary_sensor")
    )

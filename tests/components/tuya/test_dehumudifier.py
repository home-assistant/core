"""Test for Tuya Dehumidifier."""

from homeassistant.components.tuya.const import DPCode
from homeassistant.components.tuya.sensor import (
    SENSORS,
    TuyaSensorEntity,
    TuyaSensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant

from .common import load_device_from_json

from tests.common import MockConfigEntry


async def test_dehumidifier_fault_sensor(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that fault sensor can obtain it value."""
    faultEntity: TuyaSensorEntityDescription = next(
        filter(lambda e: e.key == DPCode.FAULT, SENSORS["cs"])
    )

    assert faultEntity.entity_category == EntityCategory.DIAGNOSTIC
    assert faultEntity.icon == "mdi:alert"
    assert faultEntity.translation_key == "fault"

    device = await load_device_from_json("full_dehumidifier.json")
    sensor = TuyaSensorEntity(device, None, faultEntity)

    assert sensor.native_value == 16  # FL - Full tank

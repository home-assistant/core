"""Tests for handling accessories on a Homespan esp32 daikin bridge."""
from homeassistant.components.climate import ClimateEntityFeature
from homeassistant.core import HomeAssistant

from ..common import (
    HUB_TEST_ACCESSORY_ID,
    DeviceTestInfo,
    EntityTestInfo,
    assert_devices_and_entities_created,
    setup_accessories_from_file,
    setup_test_accessories,
)


async def test_homespan_daikin_bridge_setup(hass: HomeAssistant) -> None:
    """Test that aHomespan esp32 daikin bridge can be correctly setup in HA via HomeKit."""
    accessories = await setup_accessories_from_file(hass, "homespan_daikin_bridge.json")
    await setup_test_accessories(hass, accessories)

    await assert_devices_and_entities_created(
        hass,
        DeviceTestInfo(
            unique_id=HUB_TEST_ACCESSORY_ID,
            name="Air Conditioner",
            model="Daikin-fwec3a-esp32-homekit-bridge",
            manufacturer="Garzola Marco",
            sw_version="1.0.0",
            hw_version="1.0.0",
            serial_number="00000001",
            devices=[],
            entities=[
                EntityTestInfo(
                    entity_id="climate.air_conditioner_slaveid_1",
                    friendly_name="Air Conditioner SlaveID 1",
                    unique_id="00:00:00:00:00:00_1_9",
                    supported_features=(
                        ClimateEntityFeature.TARGET_TEMPERATURE
                        | ClimateEntityFeature.FAN_MODE
                    ),
                    capabilities={
                        "hvac_modes": ["heat_cool", "heat", "cool", "off"],
                        "min_temp": 18,
                        "max_temp": 32,
                        "target_temp_step": 0.5,
                        "fan_modes": ["off", "low", "medium", "high"],
                    },
                    state="cool",
                ),
            ],
        ),
    )

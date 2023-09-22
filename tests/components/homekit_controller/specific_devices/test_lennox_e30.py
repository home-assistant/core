"""Regression tests for Aqara Gateway V3.

https://github.com/home-assistant/core/issues/20885
"""
from homeassistant.components.climate import (
    SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_TARGET_TEMPERATURE_RANGE,
)
from homeassistant.core import HomeAssistant

from ..common import (
    HUB_TEST_ACCESSORY_ID,
    DeviceTestInfo,
    EntityTestInfo,
    assert_devices_and_entities_created,
    setup_accessories_from_file,
    setup_test_accessories,
)


async def test_lennox_e30_setup(hass: HomeAssistant) -> None:
    """Test that a Lennox E30 can be correctly setup in HA."""
    accessories = await setup_accessories_from_file(hass, "lennox_e30.json")
    await setup_test_accessories(hass, accessories)

    await assert_devices_and_entities_created(
        hass,
        DeviceTestInfo(
            unique_id=HUB_TEST_ACCESSORY_ID,
            name="Lennox",
            model="E30 2B",
            manufacturer="Lennox",
            sw_version="3.40.XX",
            hw_version="3.0.XX",
            serial_number="XXXXXXXX",
            devices=[],
            entities=[
                EntityTestInfo(
                    entity_id="climate.lennox",
                    friendly_name="Lennox",
                    unique_id="00:00:00:00:00:00_1_100",
                    supported_features=(
                        SUPPORT_TARGET_TEMPERATURE | SUPPORT_TARGET_TEMPERATURE_RANGE
                    ),
                    capabilities={
                        "hvac_modes": ["off", "heat", "cool", "heat_cool"],
                        "max_temp": 37,
                        "min_temp": 4.5,
                    },
                    state="heat_cool",
                ),
            ],
        ),
    )

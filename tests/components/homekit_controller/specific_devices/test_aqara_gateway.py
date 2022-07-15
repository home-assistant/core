"""
Regression tests for Aqara Gateway V3.

https://github.com/home-assistant/core/issues/20957
"""
from homeassistant.components.alarm_control_panel import (
    SUPPORT_ALARM_ARM_AWAY,
    SUPPORT_ALARM_ARM_HOME,
    SUPPORT_ALARM_ARM_NIGHT,
)
from homeassistant.components.number import NumberMode
from homeassistant.helpers.entity import EntityCategory

from tests.components.homekit_controller.common import (
    HUB_TEST_ACCESSORY_ID,
    DeviceTestInfo,
    EntityTestInfo,
    assert_devices_and_entities_created,
    setup_accessories_from_file,
    setup_test_accessories,
)


async def test_aqara_gateway_setup(hass):
    """Test that a Aqara Gateway can be correctly setup in HA."""
    accessories = await setup_accessories_from_file(hass, "aqara_gateway.json")
    await setup_test_accessories(hass, accessories)

    await assert_devices_and_entities_created(
        hass,
        DeviceTestInfo(
            unique_id=HUB_TEST_ACCESSORY_ID,
            name="Aqara Hub-1563",
            model="ZHWA11LM",
            manufacturer="Aqara",
            sw_version="1.4.7",
            hw_version="",
            serial_number="0000000123456789",
            devices=[],
            entities=[
                EntityTestInfo(
                    "alarm_control_panel.aqara_hub_1563_security_system",
                    friendly_name="Aqara Hub-1563 Security System",
                    unique_id="homekit-0000000123456789-66304",
                    supported_features=SUPPORT_ALARM_ARM_NIGHT
                    | SUPPORT_ALARM_ARM_HOME
                    | SUPPORT_ALARM_ARM_AWAY,
                    state="disarmed",
                ),
                EntityTestInfo(
                    "light.aqara_hub_1563_lightbulb_1563",
                    friendly_name="Aqara Hub-1563 Lightbulb-1563",
                    unique_id="homekit-0000000123456789-65792",
                    supported_features=0,
                    capabilities={"supported_color_modes": ["hs"]},
                    state="off",
                ),
                EntityTestInfo(
                    "number.aqara_hub_1563_volume",
                    friendly_name="Aqara Hub-1563 Volume",
                    unique_id="homekit-0000000123456789-aid:1-sid:65536-cid:65541",
                    capabilities={
                        "max": 100,
                        "min": 0,
                        "mode": NumberMode.AUTO,
                        "step": 1,
                    },
                    entity_category=EntityCategory.CONFIG,
                    state="40",
                ),
                EntityTestInfo(
                    "switch.aqara_hub_1563_pairing_mode",
                    friendly_name="Aqara Hub-1563 Pairing Mode",
                    unique_id="homekit-0000000123456789-aid:1-sid:65536-cid:65538",
                    entity_category=EntityCategory.CONFIG,
                    state="off",
                ),
            ],
        ),
    )


async def test_aqara_gateway_e1_setup(hass):
    """Test that an Aqara E1 Gateway can be correctly setup in HA."""
    accessories = await setup_accessories_from_file(hass, "aqara_e1.json")
    await setup_test_accessories(hass, accessories)

    await assert_devices_and_entities_created(
        hass,
        DeviceTestInfo(
            unique_id=HUB_TEST_ACCESSORY_ID,
            name="Aqara-Hub-E1-00A0",
            model="HE1-G01",
            manufacturer="Aqara",
            sw_version="3.3.0",
            hw_version="1.0",
            serial_number="00aa00000a0",
            devices=[],
            entities=[
                EntityTestInfo(
                    "alarm_control_panel.aqara_hub_e1_00a0_security_system",
                    friendly_name="Aqara-Hub-E1-00A0 Security System",
                    unique_id="homekit-00aa00000a0-16",
                    supported_features=SUPPORT_ALARM_ARM_NIGHT
                    | SUPPORT_ALARM_ARM_HOME
                    | SUPPORT_ALARM_ARM_AWAY,
                    state="disarmed",
                ),
                EntityTestInfo(
                    "number.aqara_hub_e1_00a0_volume",
                    friendly_name="Aqara-Hub-E1-00A0 Volume",
                    unique_id="homekit-00aa00000a0-aid:1-sid:17-cid:1114116",
                    capabilities={
                        "max": 100,
                        "min": 0,
                        "mode": NumberMode.AUTO,
                        "step": 1,
                    },
                    entity_category=EntityCategory.CONFIG,
                    state="40",
                ),
                EntityTestInfo(
                    "switch.aqara_hub_e1_00a0_pairing_mode",
                    friendly_name="Aqara-Hub-E1-00A0 Pairing Mode",
                    unique_id="homekit-00aa00000a0-aid:1-sid:17-cid:1114117",
                    entity_category=EntityCategory.CONFIG,
                    state="off",
                ),
            ],
        ),
    )

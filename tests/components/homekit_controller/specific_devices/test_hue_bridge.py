"""Tests for handling accessories on a Hue bridge via HomeKit."""

from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import PERCENTAGE

from tests.components.homekit_controller.common import (
    HUB_TEST_ACCESSORY_ID,
    DeviceTestInfo,
    DeviceTriggerInfo,
    EntityTestInfo,
    assert_devices_and_entities_created,
    setup_accessories_from_file,
    setup_test_accessories,
)


async def test_hue_bridge_setup(hass):
    """Test that a Hue hub can be correctly setup in HA via HomeKit."""
    accessories = await setup_accessories_from_file(hass, "hue_bridge.json")
    await setup_test_accessories(hass, accessories)

    await assert_devices_and_entities_created(
        hass,
        DeviceTestInfo(
            unique_id=HUB_TEST_ACCESSORY_ID,
            name="Philips hue - 482544",
            model="BSB002",
            manufacturer="Philips Lighting",
            sw_version="1.32.1932126170",
            hw_version="",
            serial_number="123456",
            devices=[
                DeviceTestInfo(
                    name="Hue dimmer switch",
                    model="RWL021",
                    manufacturer="Philips",
                    sw_version="45.1.17846",
                    hw_version="",
                    serial_number="6623462389072572",
                    unique_id="00:00:00:00:00:00:aid:6623462389072572",
                    devices=[],
                    entities=[
                        EntityTestInfo(
                            entity_id="sensor.hue_dimmer_switch_battery",
                            capabilities={"state_class": SensorStateClass.MEASUREMENT},
                            friendly_name="Hue dimmer switch battery",
                            unique_id="homekit-6623462389072572-644245094400",
                            unit_of_measurement=PERCENTAGE,
                            state="100",
                        )
                    ],
                    stateless_triggers=[
                        DeviceTriggerInfo(type="button1", subtype="single_press"),
                        DeviceTriggerInfo(type="button2", subtype="single_press"),
                        DeviceTriggerInfo(type="button3", subtype="single_press"),
                        DeviceTriggerInfo(type="button4", subtype="single_press"),
                    ],
                ),
            ],
            entities=[],
        ),
    )

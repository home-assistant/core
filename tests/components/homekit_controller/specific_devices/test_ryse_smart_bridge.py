"""Test against characteristics captured from a ryse smart bridge platforms."""

from homeassistant.components.cover import (
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    SUPPORT_SET_POSITION,
)
from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import PERCENTAGE

from tests.components.homekit_controller.common import (
    HUB_TEST_ACCESSORY_ID,
    DeviceTestInfo,
    EntityTestInfo,
    assert_devices_and_entities_created,
    setup_accessories_from_file,
    setup_test_accessories,
)

RYSE_SUPPORTED_FEATURES = SUPPORT_CLOSE | SUPPORT_SET_POSITION | SUPPORT_OPEN


async def test_ryse_smart_bridge_setup(hass):
    """Test that a Ryse smart bridge can be correctly setup in HA."""
    accessories = await setup_accessories_from_file(hass, "ryse_smart_bridge.json")
    await setup_test_accessories(hass, accessories)

    await assert_devices_and_entities_created(
        hass,
        DeviceTestInfo(
            unique_id=HUB_TEST_ACCESSORY_ID,
            name="RYSE SmartBridge",
            model="RYSE SmartBridge",
            manufacturer="RYSE Inc.",
            sw_version="1.3.0",
            hw_version="0101.3521.0436",
            devices=[
                DeviceTestInfo(
                    unique_id="00:00:00:00:00:00:aid:2",
                    name="Master Bath South",
                    model="RYSE Shade",
                    manufacturer="RYSE Inc.",
                    sw_version="3.0.8",
                    hw_version="1.0.0",
                    serial_number="",
                    devices=[],
                    entities=[
                        EntityTestInfo(
                            entity_id="cover.master_bath_south_ryse_shade",
                            friendly_name="Master Bath South RYSE Shade",
                            unique_id="homekit-00:00:00:00:00:00-2-48",
                            supported_features=RYSE_SUPPORTED_FEATURES,
                            state="closed",
                        ),
                        EntityTestInfo(
                            entity_id="sensor.master_bath_south_ryse_shade_battery",
                            friendly_name="Master Bath South RYSE Shade Battery",
                            capabilities={"state_class": SensorStateClass.MEASUREMENT},
                            unique_id="homekit-00:00:00:00:00:00-2-64",
                            unit_of_measurement=PERCENTAGE,
                            state="100",
                        ),
                    ],
                ),
                DeviceTestInfo(
                    unique_id="00:00:00:00:00:00:aid:3",
                    name="RYSE SmartShade",
                    model="RYSE Shade",
                    manufacturer="RYSE Inc.",
                    sw_version="",
                    hw_version="",
                    serial_number="",
                    devices=[],
                    entities=[
                        EntityTestInfo(
                            entity_id="cover.ryse_smartshade_ryse_shade",
                            friendly_name="RYSE SmartShade RYSE Shade",
                            unique_id="homekit-00:00:00:00:00:00-3-48",
                            supported_features=RYSE_SUPPORTED_FEATURES,
                            state="open",
                        ),
                        EntityTestInfo(
                            entity_id="sensor.ryse_smartshade_ryse_shade_battery",
                            friendly_name="RYSE SmartShade RYSE Shade Battery",
                            capabilities={"state_class": SensorStateClass.MEASUREMENT},
                            unique_id="homekit-00:00:00:00:00:00-3-64",
                            unit_of_measurement=PERCENTAGE,
                            state="100",
                        ),
                    ],
                ),
            ],
            entities=[],
        ),
    )


async def test_ryse_smart_bridge_four_shades_setup(hass):
    """Test that a Ryse smart bridge with four shades can be correctly setup in HA."""
    accessories = await setup_accessories_from_file(
        hass, "ryse_smart_bridge_four_shades.json"
    )
    await setup_test_accessories(hass, accessories)

    await assert_devices_and_entities_created(
        hass,
        DeviceTestInfo(
            unique_id=HUB_TEST_ACCESSORY_ID,
            name="RYSE SmartBridge",
            model="RYSE SmartBridge",
            manufacturer="RYSE Inc.",
            sw_version="1.3.0",
            hw_version="0401.3521.0679",
            devices=[
                DeviceTestInfo(
                    unique_id="00:00:00:00:00:00:aid:2",
                    name="LR Left",
                    model="RYSE Shade",
                    manufacturer="RYSE Inc.",
                    sw_version="3.0.8",
                    hw_version="1.0.0",
                    serial_number="",
                    devices=[],
                    entities=[
                        EntityTestInfo(
                            entity_id="cover.lr_left_ryse_shade",
                            friendly_name="LR Left RYSE Shade",
                            unique_id="homekit-00:00:00:00:00:00-2-48",
                            supported_features=RYSE_SUPPORTED_FEATURES,
                            state="closed",
                        ),
                        EntityTestInfo(
                            entity_id="sensor.lr_left_ryse_shade_battery",
                            friendly_name="LR Left RYSE Shade Battery",
                            capabilities={"state_class": SensorStateClass.MEASUREMENT},
                            unique_id="homekit-00:00:00:00:00:00-2-64",
                            unit_of_measurement=PERCENTAGE,
                            state="89",
                        ),
                    ],
                ),
                DeviceTestInfo(
                    unique_id="00:00:00:00:00:00:aid:3",
                    name="LR Right",
                    model="RYSE Shade",
                    manufacturer="RYSE Inc.",
                    sw_version="3.0.8",
                    hw_version="1.0.0",
                    serial_number="",
                    devices=[],
                    entities=[
                        EntityTestInfo(
                            entity_id="cover.lr_right_ryse_shade",
                            friendly_name="LR Right RYSE Shade",
                            unique_id="homekit-00:00:00:00:00:00-3-48",
                            supported_features=RYSE_SUPPORTED_FEATURES,
                            state="closed",
                        ),
                        EntityTestInfo(
                            entity_id="sensor.lr_right_ryse_shade_battery",
                            friendly_name="LR Right RYSE Shade Battery",
                            capabilities={"state_class": SensorStateClass.MEASUREMENT},
                            unique_id="homekit-00:00:00:00:00:00-3-64",
                            unit_of_measurement=PERCENTAGE,
                            state="100",
                        ),
                    ],
                ),
                DeviceTestInfo(
                    unique_id="00:00:00:00:00:00:aid:4",
                    name="BR Left",
                    model="RYSE Shade",
                    manufacturer="RYSE Inc.",
                    sw_version="3.0.8",
                    hw_version="1.0.0",
                    serial_number="",
                    devices=[],
                    entities=[
                        EntityTestInfo(
                            entity_id="cover.br_left_ryse_shade",
                            friendly_name="BR Left RYSE Shade",
                            unique_id="homekit-00:00:00:00:00:00-4-48",
                            supported_features=RYSE_SUPPORTED_FEATURES,
                            state="open",
                        ),
                        EntityTestInfo(
                            entity_id="sensor.br_left_ryse_shade_battery",
                            friendly_name="BR Left RYSE Shade Battery",
                            capabilities={"state_class": SensorStateClass.MEASUREMENT},
                            unique_id="homekit-00:00:00:00:00:00-4-64",
                            unit_of_measurement=PERCENTAGE,
                            state="100",
                        ),
                    ],
                ),
                DeviceTestInfo(
                    unique_id="00:00:00:00:00:00:aid:5",
                    name="RZSS",
                    model="RYSE Shade",
                    manufacturer="RYSE Inc.",
                    sw_version="3.0.8",
                    hw_version="1.0.0",
                    serial_number="",
                    devices=[],
                    entities=[
                        EntityTestInfo(
                            entity_id="cover.rzss_ryse_shade",
                            friendly_name="RZSS RYSE Shade",
                            unique_id="homekit-00:00:00:00:00:00-5-48",
                            supported_features=RYSE_SUPPORTED_FEATURES,
                            state="open",
                        ),
                        EntityTestInfo(
                            entity_id="sensor.rzss_ryse_shade_battery",
                            capabilities={"state_class": SensorStateClass.MEASUREMENT},
                            friendly_name="RZSS RYSE Shade Battery",
                            unique_id="homekit-00:00:00:00:00:00-5-64",
                            unit_of_measurement=PERCENTAGE,
                            state="0",
                        ),
                    ],
                ),
            ],
            entities=[],
        ),
    )

"""Tests for handling accessories on a Lutron Caseta bridge via HomeKit."""

from homeassistant.const import STATE_OFF

from tests.components.homekit_controller.common import (
    HUB_TEST_ACCESSORY_ID,
    DeviceTestInfo,
    EntityTestInfo,
    assert_devices_and_entities_created,
    setup_accessories_from_file,
    setup_test_accessories,
)


async def test_lutron_caseta_bridge_setup(hass):
    """Test that a Lutron Caseta bridge can be correctly setup in HA via HomeKit."""
    accessories = await setup_accessories_from_file(hass, "lutron_caseta_bridge.json")
    await setup_test_accessories(hass, accessories)

    await assert_devices_and_entities_created(
        hass,
        DeviceTestInfo(
            unique_id=HUB_TEST_ACCESSORY_ID,
            name="Smart Bridge 2",
            model="L-BDG2-WH",
            manufacturer="Lutron Electronics Co., Inc",
            sw_version="08.08",
            hw_version="",
            serial_number="12344331",
            devices=[
                DeviceTestInfo(
                    name="Cas\u00e9ta\u00ae Wireless Fan Speed Control",
                    model="PD-FSQN-XX",
                    manufacturer="Lutron Electronics Co., Inc",
                    sw_version="001.005",
                    hw_version="",
                    serial_number="39024290",
                    unique_id="00:00:00:00:00:00:aid:21474836482",
                    devices=[],
                    entities=[
                        EntityTestInfo(
                            entity_id="fan.caseta_r_wireless_fan_speed_control",
                            friendly_name="Caséta® Wireless Fan Speed Control",
                            unique_id="homekit-39024290-2",
                            unit_of_measurement=None,
                            supported_features=1,
                            state=STATE_OFF,
                            capabilities={"preset_modes": None},
                        )
                    ],
                ),
            ],
            entities=[],
        ),
    )

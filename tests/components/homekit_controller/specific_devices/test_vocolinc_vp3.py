"""Make sure that existing VOCOlinc VP3 support isn't broken."""
from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import POWER_WATT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from ..common import (
    HUB_TEST_ACCESSORY_ID,
    DeviceTestInfo,
    EntityTestInfo,
    assert_devices_and_entities_created,
    setup_accessories_from_file,
    setup_test_accessories,
)


async def test_vocolinc_vp3_setup(hass: HomeAssistant) -> None:
    """Test that a VOCOlinc VP3 can be correctly setup in HA."""

    entity_registry = er.async_get(hass)
    outlet = entity_registry.async_get_or_create(
        "switch",
        "homekit_controller",
        "homekit-EU0121203xxxxx07-48",
        suggested_object_id="original_vocolinc_vp3_outlet",
    )
    sensor = entity_registry.async_get_or_create(
        "sensor",
        "homekit_controller",
        "homekit-EU0121203xxxxx07-aid:1-sid:48-cid:97",
        suggested_object_id="original_vocolinc_vp3_power",
    )

    accessories = await setup_accessories_from_file(hass, "vocolinc_vp3.json")
    await setup_test_accessories(hass, accessories)

    await assert_devices_and_entities_created(
        hass,
        DeviceTestInfo(
            unique_id=HUB_TEST_ACCESSORY_ID,
            name="VOCOlinc-VP3-123456",
            model="VP3",
            manufacturer="VOCOlinc",
            sw_version="1.101.2",
            hw_version="1.0.3",
            serial_number="EU0121203xxxxx07",
            devices=[],
            entities=[
                EntityTestInfo(
                    entity_id="switch.original_vocolinc_vp3_outlet",
                    friendly_name="VOCOlinc-VP3-123456 Outlet",
                    unique_id="00:00:00:00:00:00_1_48",
                    state="on",
                ),
                EntityTestInfo(
                    entity_id="sensor.original_vocolinc_vp3_power",
                    friendly_name="VOCOlinc-VP3-123456 Power",
                    unique_id="00:00:00:00:00:00_1_48_97",
                    unit_of_measurement=POWER_WATT,
                    capabilities={"state_class": SensorStateClass.MEASUREMENT},
                    state="0",
                ),
            ],
        ),
    )

    assert (
        entity_registry.async_get(outlet.entity_id).unique_id
        == "00:00:00:00:00:00_1_48"
    )
    assert (
        entity_registry.async_get(sensor.entity_id).unique_id
        == "00:00:00:00:00:00_1_48_97"
    )

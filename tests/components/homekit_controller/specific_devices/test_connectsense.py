"""Make sure that ConnectSense Smart Outlet2 / In-Wall Outlet is enumerated properly."""

from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import (
    ELECTRIC_CURRENT_AMPERE,
    ENERGY_KILO_WATT_HOUR,
    POWER_WATT,
)

from tests.components.homekit_controller.common import (
    HUB_TEST_ACCESSORY_ID,
    DeviceTestInfo,
    EntityTestInfo,
    assert_devices_and_entities_created,
    setup_accessories_from_file,
    setup_test_accessories,
)


async def test_connectsense_setup(hass):
    """Test that the accessory can be correctly setup in HA."""
    accessories = await setup_accessories_from_file(hass, "connectsense.json")
    await setup_test_accessories(hass, accessories)

    await assert_devices_and_entities_created(
        hass,
        DeviceTestInfo(
            unique_id=HUB_TEST_ACCESSORY_ID,
            name="InWall Outlet-0394DE",
            model="CS-IWO",
            manufacturer="ConnectSense",
            sw_version="1.0.0",
            hw_version="",
            serial_number="1020301376",
            devices=[],
            entities=[
                EntityTestInfo(
                    entity_id="sensor.inwall_outlet_0394de_current",
                    friendly_name="InWall Outlet-0394DE Current",
                    unique_id="homekit-1020301376-aid:1-sid:13-cid:18",
                    capabilities={"state_class": SensorStateClass.MEASUREMENT},
                    unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
                    state="0.03",
                ),
                EntityTestInfo(
                    entity_id="sensor.inwall_outlet_0394de_power",
                    friendly_name="InWall Outlet-0394DE Power",
                    unique_id="homekit-1020301376-aid:1-sid:13-cid:19",
                    capabilities={"state_class": SensorStateClass.MEASUREMENT},
                    unit_of_measurement=POWER_WATT,
                    state="0.8",
                ),
                EntityTestInfo(
                    entity_id="sensor.inwall_outlet_0394de_energy_kwh",
                    friendly_name="InWall Outlet-0394DE Energy kWh",
                    unique_id="homekit-1020301376-aid:1-sid:13-cid:20",
                    capabilities={"state_class": SensorStateClass.MEASUREMENT},
                    unit_of_measurement=ENERGY_KILO_WATT_HOUR,
                    state="379.69299",
                ),
                EntityTestInfo(
                    entity_id="switch.inwall_outlet_0394de_outlet_a",
                    friendly_name="InWall Outlet-0394DE Outlet A",
                    unique_id="homekit-1020301376-13",
                    state="on",
                ),
                EntityTestInfo(
                    entity_id="sensor.inwall_outlet_0394de_current_2",
                    friendly_name="InWall Outlet-0394DE Current",
                    unique_id="homekit-1020301376-aid:1-sid:25-cid:30",
                    capabilities={"state_class": SensorStateClass.MEASUREMENT},
                    unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
                    state="0.05",
                ),
                EntityTestInfo(
                    entity_id="sensor.inwall_outlet_0394de_power_2",
                    friendly_name="InWall Outlet-0394DE Power",
                    unique_id="homekit-1020301376-aid:1-sid:25-cid:31",
                    capabilities={"state_class": SensorStateClass.MEASUREMENT},
                    unit_of_measurement=POWER_WATT,
                    state="0.8",
                ),
                EntityTestInfo(
                    entity_id="sensor.inwall_outlet_0394de_energy_kwh_2",
                    friendly_name="InWall Outlet-0394DE Energy kWh",
                    unique_id="homekit-1020301376-aid:1-sid:25-cid:32",
                    capabilities={"state_class": SensorStateClass.MEASUREMENT},
                    unit_of_measurement=ENERGY_KILO_WATT_HOUR,
                    state="175.85001",
                ),
                EntityTestInfo(
                    entity_id="switch.inwall_outlet_0394de_outlet_b",
                    friendly_name="InWall Outlet-0394DE Outlet B",
                    unique_id="homekit-1020301376-25",
                    state="on",
                ),
            ],
        ),
    )

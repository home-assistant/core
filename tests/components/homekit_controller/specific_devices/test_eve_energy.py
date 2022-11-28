"""Make sure that Eve Degree (via Eve Extend) is enumerated properly."""

from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import (
    ELECTRIC_CURRENT_AMPERE,
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_KILO_WATT_HOUR,
    POWER_WATT,
)
from homeassistant.helpers.entity import EntityCategory

from tests.components.homekit_controller.common import (
    HUB_TEST_ACCESSORY_ID,
    DeviceTestInfo,
    EntityTestInfo,
    assert_devices_and_entities_created,
    setup_accessories_from_file,
    setup_test_accessories,
)


async def test_eve_degree_setup(hass):
    """Test that the accessory can be correctly setup in HA."""
    accessories = await setup_accessories_from_file(hass, "eve_energy.json")
    await setup_test_accessories(hass, accessories)

    await assert_devices_and_entities_created(
        hass,
        DeviceTestInfo(
            unique_id=HUB_TEST_ACCESSORY_ID,
            name="Eve Energy 50FF",
            model="Eve Energy 20EAO8601",
            manufacturer="Elgato",
            sw_version="1.2.9",
            hw_version="1.0.0",
            serial_number="AA00A0A00000",
            devices=[],
            entities=[
                EntityTestInfo(
                    entity_id="switch.eve_energy_50ff",
                    unique_id="homekit-AA00A0A00000-28",
                    friendly_name="Eve Energy 50FF",
                    state="off",
                ),
                EntityTestInfo(
                    entity_id="sensor.eve_energy_50ff_amps",
                    unique_id="homekit-AA00A0A00000-aid:1-sid:28-cid:33",
                    friendly_name="Eve Energy 50FF Amps",
                    unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
                    capabilities={"state_class": SensorStateClass.MEASUREMENT},
                    state="0",
                ),
                EntityTestInfo(
                    entity_id="sensor.eve_energy_50ff_volts",
                    unique_id="homekit-AA00A0A00000-aid:1-sid:28-cid:32",
                    friendly_name="Eve Energy 50FF Volts",
                    unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
                    capabilities={"state_class": SensorStateClass.MEASUREMENT},
                    state="0.400000005960464",
                ),
                EntityTestInfo(
                    entity_id="sensor.eve_energy_50ff_power",
                    unique_id="homekit-AA00A0A00000-aid:1-sid:28-cid:34",
                    friendly_name="Eve Energy 50FF Power",
                    unit_of_measurement=POWER_WATT,
                    capabilities={"state_class": SensorStateClass.MEASUREMENT},
                    state="0",
                ),
                EntityTestInfo(
                    entity_id="sensor.eve_energy_50ff_energy_kwh",
                    unique_id="homekit-AA00A0A00000-aid:1-sid:28-cid:35",
                    friendly_name="Eve Energy 50FF Energy kWh",
                    capabilities={"state_class": SensorStateClass.MEASUREMENT},
                    unit_of_measurement=ENERGY_KILO_WATT_HOUR,
                    state="0.28999999165535",
                ),
                EntityTestInfo(
                    entity_id="switch.eve_energy_50ff_lock_physical_controls",
                    unique_id="homekit-AA00A0A00000-aid:1-sid:28-cid:36",
                    friendly_name="Eve Energy 50FF Lock Physical Controls",
                    entity_category=EntityCategory.CONFIG,
                    state="off",
                ),
                EntityTestInfo(
                    entity_id="button.eve_energy_50ff_identify",
                    unique_id="homekit-AA00A0A00000-aid:1-sid:1-cid:3",
                    friendly_name="Eve Energy 50FF Identify",
                    entity_category=EntityCategory.DIAGNOSTIC,
                    state="unknown",
                ),
            ],
        ),
    )

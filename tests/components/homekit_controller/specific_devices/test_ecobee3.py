"""Regression tests for Ecobee 3.

https://github.com/home-assistant/core/issues/15336
"""
from typing import Any
from unittest import mock

from aiohomekit import AccessoryNotFoundError
from aiohomekit.testing import FakePairing

from homeassistant.components.climate import ClimateEntityFeature
from homeassistant.components.sensor import SensorStateClass
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from ..common import (
    HUB_TEST_ACCESSORY_ID,
    DeviceTestInfo,
    EntityTestInfo,
    assert_devices_and_entities_created,
    device_config_changed,
    setup_accessories_from_file,
    setup_test_accessories,
    time_changed,
)


async def test_ecobee3_setup(hass: HomeAssistant) -> None:
    """Test that a Ecbobee 3 can be correctly setup in HA."""
    accessories = await setup_accessories_from_file(hass, "ecobee3.json")
    await setup_test_accessories(hass, accessories)

    await assert_devices_and_entities_created(
        hass,
        DeviceTestInfo(
            unique_id=HUB_TEST_ACCESSORY_ID,
            name="HomeW",
            model="ecobee3",
            manufacturer="ecobee Inc.",
            sw_version="4.2.394",
            hw_version="",
            serial_number="123456789012",
            devices=[
                DeviceTestInfo(
                    name="Kitchen",
                    model="REMOTE SENSOR",
                    manufacturer="ecobee Inc.",
                    sw_version="1.0.0",
                    hw_version="",
                    serial_number="AB1C",
                    unique_id="00:00:00:00:00:00:aid:2",
                    devices=[],
                    entities=[
                        EntityTestInfo(
                            entity_id="binary_sensor.kitchen",
                            friendly_name="Kitchen",
                            unique_id="00:00:00:00:00:00_2_56",
                            state="off",
                        ),
                    ],
                ),
                DeviceTestInfo(
                    name="Porch",
                    model="REMOTE SENSOR",
                    manufacturer="ecobee Inc.",
                    sw_version="1.0.0",
                    hw_version="",
                    serial_number="AB2C",
                    unique_id="00:00:00:00:00:00:aid:3",
                    devices=[],
                    entities=[
                        EntityTestInfo(
                            entity_id="binary_sensor.porch",
                            friendly_name="Porch",
                            unique_id="00:00:00:00:00:00_3_56",
                            state="off",
                        ),
                    ],
                ),
                DeviceTestInfo(
                    name="Basement",
                    model="REMOTE SENSOR",
                    manufacturer="ecobee Inc.",
                    sw_version="1.0.0",
                    hw_version="",
                    serial_number="AB3C",
                    unique_id="00:00:00:00:00:00:aid:4",
                    devices=[],
                    entities=[
                        EntityTestInfo(
                            entity_id="binary_sensor.basement",
                            friendly_name="Basement",
                            unique_id="00:00:00:00:00:00_4_56",
                            state="off",
                        ),
                    ],
                ),
            ],
            entities=[
                EntityTestInfo(
                    entity_id="climate.homew",
                    friendly_name="HomeW",
                    unique_id="00:00:00:00:00:00_1_16",
                    supported_features=(
                        ClimateEntityFeature.TARGET_TEMPERATURE
                        | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
                        | ClimateEntityFeature.TARGET_HUMIDITY
                        | ClimateEntityFeature.TURN_OFF
                        | ClimateEntityFeature.TURN_ON
                    ),
                    capabilities={
                        "hvac_modes": ["off", "heat", "cool", "heat_cool"],
                        "min_temp": 7.2,
                        "max_temp": 33.3,
                        "min_humidity": 20,
                        "max_humidity": 50,
                    },
                    state="heat",
                ),
                EntityTestInfo(
                    entity_id="sensor.homew_current_temperature",
                    friendly_name="HomeW Current Temperature",
                    unique_id="00:00:00:00:00:00_1_16_19",
                    capabilities={"state_class": SensorStateClass.MEASUREMENT},
                    unit_of_measurement=UnitOfTemperature.CELSIUS,
                    state="21.8",
                ),
                EntityTestInfo(
                    entity_id="select.homew_current_mode",
                    friendly_name="HomeW Current Mode",
                    unique_id="00:00:00:00:00:00_1_16_33",
                    capabilities={"options": ["home", "sleep", "away"]},
                    state="home",
                ),
            ],
        ),
    )


async def test_ecobee3_setup_from_cache(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    hass_storage: dict[str, Any],
) -> None:
    """Test that Ecbobee can be correctly setup from its cached entity map."""
    accessories = await setup_accessories_from_file(hass, "ecobee3.json")

    hass_storage["homekit_controller-entity-map"] = {
        "version": 1,
        "data": {
            "pairings": {
                HUB_TEST_ACCESSORY_ID: {
                    "config_num": 1,
                    "accessories": [
                        a.to_accessory_and_service_list() for a in accessories
                    ],
                }
            }
        },
    }

    await setup_test_accessories(hass, accessories)

    climate = entity_registry.async_get("climate.homew")
    assert climate.unique_id == "00:00:00:00:00:00_1_16"

    occ1 = entity_registry.async_get("binary_sensor.kitchen")
    assert occ1.unique_id == "00:00:00:00:00:00_2_56"

    occ2 = entity_registry.async_get("binary_sensor.porch")
    assert occ2.unique_id == "00:00:00:00:00:00_3_56"

    occ3 = entity_registry.async_get("binary_sensor.basement")
    assert occ3.unique_id == "00:00:00:00:00:00_4_56"


async def test_ecobee3_setup_connection_failure(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test that Ecbobee can be correctly setup from its cached entity map."""
    accessories = await setup_accessories_from_file(hass, "ecobee3.json")

    # Test that the connection fails during initial setup.
    # No entities should be created.
    with mock.patch.object(FakePairing, "async_populate_accessories_state") as laac:
        laac.side_effect = AccessoryNotFoundError("Connection failed")

        # If there is no cached entity map and the accessory connection is
        # failing then we have to fail the config entry setup.
        config_entry, pairing = await setup_test_accessories(hass, accessories)
        assert config_entry.state is ConfigEntryState.SETUP_RETRY

    climate = entity_registry.async_get("climate.homew")
    assert climate is None

    # When accessory raises ConfigEntryNoteReady HA will retry - lets make
    # sure there is no cruft causing conflicts left behind by now doing
    # a successful setup.

    # We just advance time by 5 minutes so that the retry happens, rather
    # than manually invoking async_setup_entry.
    await time_changed(hass, 5 * 60)

    climate = entity_registry.async_get("climate.homew")
    assert climate.unique_id == "00:00:00:00:00:00_1_16"

    occ1 = entity_registry.async_get("binary_sensor.kitchen")
    assert occ1.unique_id == "00:00:00:00:00:00_2_56"

    occ2 = entity_registry.async_get("binary_sensor.porch")
    assert occ2.unique_id == "00:00:00:00:00:00_3_56"

    occ3 = entity_registry.async_get("binary_sensor.basement")
    assert occ3.unique_id == "00:00:00:00:00:00_4_56"


async def test_ecobee3_add_sensors_at_runtime(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test that new sensors are automatically added."""

    # Set up a base Ecobee 3 with no additional sensors.
    # There shouldn't be any entities but climate visible.
    accessories = await setup_accessories_from_file(hass, "ecobee3_no_sensors.json")
    await setup_test_accessories(hass, accessories)

    climate = entity_registry.async_get("climate.homew")
    assert climate.unique_id == "00:00:00:00:00:00_1_16"

    occ1 = entity_registry.async_get("binary_sensor.kitchen")
    assert occ1 is None

    occ2 = entity_registry.async_get("binary_sensor.porch")
    assert occ2 is None

    occ3 = entity_registry.async_get("binary_sensor.basement")
    assert occ3 is None

    # Now added 3 new sensors at runtime - sensors should appear and climate
    # shouldn't be duplicated.
    accessories = await setup_accessories_from_file(hass, "ecobee3.json")
    await device_config_changed(hass, accessories)

    occ1 = entity_registry.async_get("binary_sensor.kitchen")
    assert occ1.unique_id == "00:00:00:00:00:00_2_56"

    occ2 = entity_registry.async_get("binary_sensor.porch")
    assert occ2.unique_id == "00:00:00:00:00:00_3_56"

    occ3 = entity_registry.async_get("binary_sensor.basement")
    assert occ3.unique_id == "00:00:00:00:00:00_4_56"


async def test_ecobee3_remove_sensors_at_runtime(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test that sensors are automatically removed."""

    # Set up a base Ecobee 3 with additional sensors.
    accessories = await setup_accessories_from_file(hass, "ecobee3.json")
    await setup_test_accessories(hass, accessories)

    climate = entity_registry.async_get("climate.homew")
    assert climate.unique_id == "00:00:00:00:00:00_1_16"

    occ1 = entity_registry.async_get("binary_sensor.kitchen")
    assert occ1.unique_id == "00:00:00:00:00:00_2_56"

    occ2 = entity_registry.async_get("binary_sensor.porch")
    assert occ2.unique_id == "00:00:00:00:00:00_3_56"

    occ3 = entity_registry.async_get("binary_sensor.basement")
    assert occ3.unique_id == "00:00:00:00:00:00_4_56"

    assert hass.states.get("binary_sensor.kitchen") is not None
    assert hass.states.get("binary_sensor.porch") is not None
    assert hass.states.get("binary_sensor.basement") is not None

    # Now remove 3 new sensors at runtime - sensors should disappear and climate
    # shouldn't be duplicated.
    accessories = await setup_accessories_from_file(hass, "ecobee3_no_sensors.json")
    await device_config_changed(hass, accessories)

    assert hass.states.get("binary_sensor.kitchen") is None
    assert entity_registry.async_get("binary_sensor.kitchen") is None

    assert hass.states.get("binary_sensor.porch") is None
    assert entity_registry.async_get("binary_sensor.porch") is None

    assert hass.states.get("binary_sensor.basement") is None
    assert entity_registry.async_get("binary_sensor.basement") is None

    # Now add the sensors back
    accessories = await setup_accessories_from_file(hass, "ecobee3.json")
    await device_config_changed(hass, accessories)

    occ1 = entity_registry.async_get("binary_sensor.kitchen")
    assert occ1.unique_id == "00:00:00:00:00:00_2_56"

    occ2 = entity_registry.async_get("binary_sensor.porch")
    assert occ2.unique_id == "00:00:00:00:00:00_3_56"

    occ3 = entity_registry.async_get("binary_sensor.basement")
    assert occ3.unique_id == "00:00:00:00:00:00_4_56"

    # Ensure the sensors are back
    assert hass.states.get("binary_sensor.kitchen") is not None
    assert occ1.id == entity_registry.async_get("binary_sensor.kitchen").id

    assert hass.states.get("binary_sensor.porch") is not None
    assert occ2.id == entity_registry.async_get("binary_sensor.porch").id

    assert hass.states.get("binary_sensor.basement") is not None
    assert occ3.id == entity_registry.async_get("binary_sensor.basement").id


async def test_ecobee3_services_and_chars_removed(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test handling removal of some services and chars."""

    # Set up a base Ecobee 3 with additional sensors.
    accessories = await setup_accessories_from_file(hass, "ecobee3.json")
    await setup_test_accessories(hass, accessories)

    climate = entity_registry.async_get("climate.homew")
    assert climate.unique_id == "00:00:00:00:00:00_1_16"

    assert hass.states.get("sensor.basement_temperature") is not None
    assert hass.states.get("sensor.kitchen_temperature") is not None
    assert hass.states.get("sensor.porch_temperature") is not None

    assert hass.states.get("select.homew_current_mode") is not None
    assert hass.states.get("button.homew_clear_hold") is not None

    # Reconfigure with some of the chars removed and the basement temperature sensor
    accessories = await setup_accessories_from_file(
        hass, "ecobee3_service_removed.json"
    )
    await device_config_changed(hass, accessories)

    # Make sure the climate entity is still there
    assert hass.states.get("climate.homew") is not None
    assert entity_registry.async_get("climate.homew") is not None

    # Make sure the basement temperature sensor is gone
    assert hass.states.get("sensor.basement_temperature") is None
    assert entity_registry.async_get("select.basement_temperature") is None

    # Make sure the current mode select and clear hold button are gone
    assert hass.states.get("select.homew_current_mode") is None
    assert entity_registry.async_get("select.homew_current_mode") is None

    assert hass.states.get("button.homew_clear_hold") is None
    assert entity_registry.async_get("button.homew_clear_hold") is None

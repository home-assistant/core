"""Test the Aranet sensors."""

import pytest

from homeassistant.components.aranet.const import DOMAIN
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components.bluetooth.passive_update_processor import STORAGE_KEY
from homeassistant.components.sensor import (
    ATTR_OPTIONS,
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    UnitOfRadiationConcentration,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util.unit_system import (
    METRIC_SYSTEM,
    US_CUSTOMARY_SYSTEM,
    UnitSystem,
)

from . import (
    DISABLED_INTEGRATIONS_SERVICE_INFO,
    VALID_ARANET2_DATA_SERVICE_INFO,
    VALID_ARANET_RADIATION_DATA_SERVICE_INFO,
    VALID_ARANET_RADON1_DATA_SERVICE_INFO,
    VALID_ARANET_RADON_DATA_SERVICE_INFO,
    VALID_DATA_SERVICE_INFO,
)

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info

RADON_ENTITY_ID = "sensor.aranetrn_12345_radon_concentration"
RADON_UNIQUE_ID = "aa:bb:cc:dd:ee:ff-radon_concentration-aa:bb:cc:dd:ee:ff"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors_aranet_radiation(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setting up creates the sensors for Aranet Radiation device."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="aa:bb:cc:dd:ee:ff",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all("sensor")) == 0
    inject_bluetooth_service_info(hass, VALID_ARANET_RADIATION_DATA_SERVICE_INFO)
    await hass.async_block_till_done()
    assert len(hass.states.async_all("sensor")) == 4

    batt_sensor = hass.states.get("sensor.aranet_12345_battery")
    batt_sensor_attrs = batt_sensor.attributes
    assert batt_sensor.state == "100"
    assert batt_sensor_attrs[ATTR_FRIENDLY_NAME] == "Aranet\u2622 12345 Battery"
    assert batt_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "%"
    assert batt_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    humid_sensor = hass.states.get("sensor.aranet_12345_radiation_total_dose")
    humid_sensor_attrs = humid_sensor.attributes
    assert humid_sensor.state == "0.011616"
    assert (
        humid_sensor_attrs[ATTR_FRIENDLY_NAME]
        == "Aranet\u2622 12345 Radiation Total Dose"
    )
    assert humid_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "mSv"
    assert humid_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    temp_sensor = hass.states.get("sensor.aranet_12345_radiation_dose_rate")
    temp_sensor_attrs = temp_sensor.attributes
    assert temp_sensor.state == "0.11"
    assert (
        temp_sensor_attrs[ATTR_FRIENDLY_NAME]
        == "Aranet\u2622 12345 Radiation Dose Rate"
    )
    assert temp_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "μSv/h"
    assert temp_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    interval_sensor = hass.states.get("sensor.aranet_12345_update_interval")
    interval_sensor_attrs = interval_sensor.attributes
    assert interval_sensor.state == "300"
    assert (
        interval_sensor_attrs[ATTR_FRIENDLY_NAME]
        == "Aranet\u2622 12345 Update Interval"
    )
    assert interval_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "s"
    assert interval_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    # Check device context for the battery sensor
    entity = entity_registry.async_get("sensor.aranet_12345_battery")
    device = device_registry.async_get(entity.device_id)
    assert device.name == "Aranet☢ 12345"
    assert device.model == "Aranet Radiation"
    assert device.sw_version == "v1.4.38"
    assert device.manufacturer == "SAF Tehnika"
    assert device.connections == {(dr.CONNECTION_BLUETOOTH, "aa:bb:cc:dd:ee:ff")}

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors_aranet2(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setting up creates the sensors for Aranet2 device."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="aa:bb:cc:dd:ee:ff",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all("sensor")) == 0
    inject_bluetooth_service_info(hass, VALID_ARANET2_DATA_SERVICE_INFO)
    await hass.async_block_till_done()
    assert len(hass.states.async_all("sensor")) == 4

    batt_sensor = hass.states.get("sensor.aranet2_12345_battery")
    batt_sensor_attrs = batt_sensor.attributes
    assert batt_sensor.state == "79"
    assert batt_sensor_attrs[ATTR_FRIENDLY_NAME] == "Aranet2 12345 Battery"
    assert batt_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "%"
    assert batt_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    humid_sensor = hass.states.get("sensor.aranet2_12345_humidity")
    humid_sensor_attrs = humid_sensor.attributes
    assert humid_sensor.state == "52.4"
    assert humid_sensor_attrs[ATTR_FRIENDLY_NAME] == "Aranet2 12345 Humidity"
    assert humid_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "%"
    assert humid_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    temp_sensor = hass.states.get("sensor.aranet2_12345_temperature")
    temp_sensor_attrs = temp_sensor.attributes
    assert temp_sensor.state == "24.8"
    assert temp_sensor_attrs[ATTR_FRIENDLY_NAME] == "Aranet2 12345 Temperature"
    assert temp_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "°C"
    assert temp_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    interval_sensor = hass.states.get("sensor.aranet2_12345_update_interval")
    interval_sensor_attrs = interval_sensor.attributes
    assert interval_sensor.state == "60"
    assert interval_sensor_attrs[ATTR_FRIENDLY_NAME] == "Aranet2 12345 Update Interval"
    assert interval_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "s"
    assert interval_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    # Check device context for the battery sensor
    entity = entity_registry.async_get("sensor.aranet2_12345_battery")
    device = device_registry.async_get(entity.device_id)
    assert device.name == "Aranet2 12345"
    assert device.model == "Aranet2"
    assert device.sw_version == "v1.4.4"
    assert device.manufacturer == "SAF Tehnika"
    assert device.connections == {(dr.CONNECTION_BLUETOOTH, "aa:bb:cc:dd:ee:ff")}

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors_aranet4(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setting up creates the sensors for Aranet4 device."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="aa:bb:cc:dd:ee:ff",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all("sensor")) == 0
    inject_bluetooth_service_info(hass, VALID_DATA_SERVICE_INFO)
    await hass.async_block_till_done()
    assert len(hass.states.async_all("sensor")) == 7

    batt_sensor = hass.states.get("sensor.aranet4_12345_battery")
    batt_sensor_attrs = batt_sensor.attributes
    assert batt_sensor.state == "89"
    assert batt_sensor_attrs[ATTR_FRIENDLY_NAME] == "Aranet4 12345 Battery"
    assert batt_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "%"
    assert batt_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    co2_sensor = hass.states.get("sensor.aranet4_12345_carbon_dioxide")
    co2_sensor_attrs = co2_sensor.attributes
    assert co2_sensor.state == "650"
    assert co2_sensor_attrs[ATTR_FRIENDLY_NAME] == "Aranet4 12345 Carbon Dioxide"
    assert co2_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "ppm"
    assert co2_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    humid_sensor = hass.states.get("sensor.aranet4_12345_humidity")
    humid_sensor_attrs = humid_sensor.attributes
    assert humid_sensor.state == "34"
    assert humid_sensor_attrs[ATTR_FRIENDLY_NAME] == "Aranet4 12345 Humidity"
    assert humid_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "%"
    assert humid_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    temp_sensor = hass.states.get("sensor.aranet4_12345_temperature")
    temp_sensor_attrs = temp_sensor.attributes
    assert temp_sensor.state == "21.1"
    assert temp_sensor_attrs[ATTR_FRIENDLY_NAME] == "Aranet4 12345 Temperature"
    assert temp_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "°C"
    assert temp_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    press_sensor = hass.states.get("sensor.aranet4_12345_pressure")
    press_sensor_attrs = press_sensor.attributes
    assert press_sensor.state == "990.5"
    assert press_sensor_attrs[ATTR_FRIENDLY_NAME] == "Aranet4 12345 Pressure"
    assert press_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "hPa"
    assert press_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    interval_sensor = hass.states.get("sensor.aranet4_12345_update_interval")
    interval_sensor_attrs = interval_sensor.attributes
    assert interval_sensor.state == "300"
    assert interval_sensor_attrs[ATTR_FRIENDLY_NAME] == "Aranet4 12345 Update Interval"
    assert interval_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "s"
    assert interval_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    status_sensor = hass.states.get("sensor.aranet4_12345_threshold")
    status_sensor_attrs = status_sensor.attributes
    assert status_sensor.state == "green"
    assert status_sensor_attrs[ATTR_FRIENDLY_NAME] == "Aranet4 12345 Threshold"
    assert status_sensor_attrs[ATTR_OPTIONS] == ["error", "green", "yellow", "red"]

    # Check device context for the battery sensor
    entity = entity_registry.async_get("sensor.aranet4_12345_battery")
    device = device_registry.async_get(entity.device_id)
    assert device.name == "Aranet4 12345"
    assert device.model == "Aranet4"
    assert device.sw_version == "v1.2.0"
    assert device.manufacturer == "SAF Tehnika"
    assert device.connections == {(dr.CONNECTION_BLUETOOTH, "aa:bb:cc:dd:ee:ff")}

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors_aranetrn(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setting up creates the sensors for Aranet Radon device."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="aa:bb:cc:dd:ee:ff",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all("sensor")) == 0
    inject_bluetooth_service_info(hass, VALID_ARANET_RADON_DATA_SERVICE_INFO)
    await hass.async_block_till_done()
    assert len(hass.states.async_all("sensor")) == 7

    batt_sensor = hass.states.get("sensor.aranetrn_12345_battery")
    batt_sensor_attrs = batt_sensor.attributes
    assert batt_sensor.state == "100"
    assert batt_sensor_attrs[ATTR_FRIENDLY_NAME] == "AranetRn+ 12345 Battery"
    assert batt_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "%"
    assert batt_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    co2_sensor = hass.states.get(RADON_ENTITY_ID)
    co2_sensor_attrs = co2_sensor.attributes
    assert co2_sensor.state == "7"
    assert co2_sensor_attrs[ATTR_FRIENDLY_NAME] == "AranetRn+ 12345 Radon Concentration"
    assert co2_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "Bq/m³"
    assert co2_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    humid_sensor = hass.states.get("sensor.aranetrn_12345_humidity")
    humid_sensor_attrs = humid_sensor.attributes
    assert humid_sensor.state == "46.2"
    assert humid_sensor_attrs[ATTR_FRIENDLY_NAME] == "AranetRn+ 12345 Humidity"
    assert humid_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "%"
    assert humid_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    temp_sensor = hass.states.get("sensor.aranetrn_12345_temperature")
    temp_sensor_attrs = temp_sensor.attributes
    assert temp_sensor.state == "25.5"
    assert temp_sensor_attrs[ATTR_FRIENDLY_NAME] == "AranetRn+ 12345 Temperature"
    assert temp_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "°C"
    assert temp_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    press_sensor = hass.states.get("sensor.aranetrn_12345_pressure")
    press_sensor_attrs = press_sensor.attributes
    assert press_sensor.state == "1018.5"
    assert press_sensor_attrs[ATTR_FRIENDLY_NAME] == "AranetRn+ 12345 Pressure"
    assert press_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "hPa"
    assert press_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    interval_sensor = hass.states.get("sensor.aranetrn_12345_update_interval")
    interval_sensor_attrs = interval_sensor.attributes
    assert interval_sensor.state == "600"
    assert (
        interval_sensor_attrs[ATTR_FRIENDLY_NAME] == "AranetRn+ 12345 Update Interval"
    )
    assert interval_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "s"
    assert interval_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    status_sensor = hass.states.get("sensor.aranetrn_12345_threshold")
    status_sensor_attrs = status_sensor.attributes
    assert status_sensor.state == "green"
    assert status_sensor_attrs[ATTR_FRIENDLY_NAME] == "AranetRn+ 12345 Threshold"
    assert status_sensor_attrs[ATTR_OPTIONS] == ["error", "green", "yellow", "red"]

    # Check device context for the battery sensor
    entity = entity_registry.async_get("sensor.aranetrn_12345_battery")
    device = device_registry.async_get(entity.device_id)
    assert device.name == "AranetRn+ 12345"
    assert device.model == "Aranet Radon"
    assert device.sw_version == "v1.6.4"
    assert device.manufacturer == "SAF Tehnika"
    assert device.connections == {(dr.CONNECTION_BLUETOOTH, "aa:bb:cc:dd:ee:ff")}

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("service_info", "entity_id"),
    [
        pytest.param(
            VALID_ARANET_RADON_DATA_SERVICE_INFO,
            RADON_ENTITY_ID,
            id="aranetrn_plus",
        ),
        pytest.param(
            VALID_ARANET_RADON1_DATA_SERVICE_INFO,
            "sensor.aranetrn1_12345_radon_concentration",
            id="aranetrn1",
        ),
    ],
)
@pytest.mark.parametrize(
    ("unit_system", "expected_unit", "expected_value"),
    [
        pytest.param(
            METRIC_SYSTEM,
            UnitOfRadiationConcentration.BECQUEREL_PER_CUBIC_METER,
            7,
            id="metric",
        ),
        pytest.param(
            US_CUSTOMARY_SYSTEM,
            UnitOfRadiationConcentration.PICOCURIES_PER_LITER,
            7 / 37,
            id="us_customary",
        ),
    ],
)
async def test_radon_device_class_and_units(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    service_info: BluetoothServiceInfoBleak,
    entity_id: str,
    unit_system: UnitSystem,
    expected_unit: UnitOfRadiationConcentration,
    expected_value: float,
) -> None:
    """Test radon metadata and default units."""
    hass.config.units = unit_system
    entry = MockConfigEntry(domain=DOMAIN, unique_id=service_info.address)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    inject_bluetooth_service_info(hass, service_info)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert float(state.state) == pytest.approx(expected_value)
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.RADON
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == expected_unit
    assert (
        state.attributes[ATTR_FRIENDLY_NAME]
        == f"{service_info.name} Radon Concentration"
    )
    entity = entity_registry.async_get(entity_id)
    assert entity is not None
    assert entity.unique_id == RADON_UNIQUE_ID
    assert entity.original_device_class == SensorDeviceClass.RADON


@pytest.mark.parametrize(
    ("mock_bluetooth_storage", "restored_device_classes"),
    [
        pytest.param({}, {}, id="without_cache"),
        pytest.param(
            {
                STORAGE_KEY: {
                    "version": 1,
                    "minor_version": 1,
                    "key": STORAGE_KEY,
                    "data": {
                        "aranet_radon": {
                            "sensor": {
                                "devices": {
                                    "aa:bb:cc:dd:ee:ff": {
                                        "name": "AranetRn+ 12345",
                                        "connections": [
                                            ["bluetooth", "aa:bb:cc:dd:ee:ff"]
                                        ],
                                    }
                                },
                                "entity_descriptions": {
                                    "radon_concentration___aa:bb:cc:dd:ee:ff": {
                                        "key": "radon_concentration",
                                        "translation_key": "radon_concentration",
                                        "name": "Radon Concentration",
                                        "native_unit_of_measurement": "Bq/m³",
                                        "state_class": "measurement",
                                    }
                                },
                                "entity_names": {
                                    "radon_concentration___aa:bb:cc:dd:ee:ff": (
                                        "Radon Concentration"
                                    )
                                },
                                "entity_data": {
                                    "radon_concentration___aa:bb:cc:dd:ee:ff": 7
                                },
                            }
                        }
                    },
                }
            },
            {RADON_ENTITY_ID: SensorDeviceClass.RADON},
            id="cached_without_device_class",
        ),
    ],
    indirect=["mock_bluetooth_storage"],
)
async def test_existing_radon_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    restored_device_classes: dict[str, SensorDeviceClass],
) -> None:
    """Test existing radon sensors gain the class without changing identity or units."""
    hass.config.units = US_CUSTOMARY_SYSTEM
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="aranet_radon",
        unique_id="aa:bb:cc:dd:ee:ff",
    )
    entry.add_to_hass(hass)
    entity = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        RADON_UNIQUE_ID,
        config_entry=entry,
        suggested_object_id="aranetrn_12345_radon_concentration",
        original_name="Radon Concentration",
        unit_of_measurement=UnitOfRadiationConcentration.BECQUEREL_PER_CUBIC_METER,
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert {
        state.entity_id: state.attributes[ATTR_DEVICE_CLASS]
        for state in hass.states.async_all("sensor")
    } == restored_device_classes

    inject_bluetooth_service_info(hass, VALID_ARANET_RADON_DATA_SERVICE_INFO)
    await hass.async_block_till_done()

    state = hass.states.get(RADON_ENTITY_ID)
    assert state is not None
    assert state.state == "7"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.RADON
    assert (
        state.attributes[ATTR_UNIT_OF_MEASUREMENT]
        == UnitOfRadiationConcentration.BECQUEREL_PER_CUBIC_METER
    )
    assert state.attributes[ATTR_FRIENDLY_NAME] == "AranetRn+ 12345 Radon Concentration"
    updated_entity = entity_registry.async_get(RADON_ENTITY_ID)
    assert updated_entity is not None
    assert updated_entity.id == entity.id
    assert updated_entity.unique_id == RADON_UNIQUE_ID
    assert updated_entity.original_device_class == SensorDeviceClass.RADON


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_smart_home_integration_disabled(hass: HomeAssistant) -> None:
    """Test disabling smart home integration marks entities as unavailable."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="aa:bb:cc:dd:ee:ff",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all("sensor")) == 0
    inject_bluetooth_service_info(hass, DISABLED_INTEGRATIONS_SERVICE_INFO)
    await hass.async_block_till_done()
    assert len(hass.states.async_all("sensor")) == 0

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

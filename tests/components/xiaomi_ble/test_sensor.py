"""Test Xiaomi BLE sensors."""
from datetime import timedelta
import time
from unittest.mock import patch

from homeassistant.components.bluetooth import (
    FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS,
)
from homeassistant.components.sensor import ATTR_STATE_CLASS
from homeassistant.components.xiaomi_ble.const import CONF_SLEEPY_DEVICE, DOMAIN
from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import (
    HHCCJCY10_SERVICE_INFO,
    MISCALE_V1_SERVICE_INFO,
    MISCALE_V2_SERVICE_INFO,
    MMC_T201_1_SERVICE_INFO,
    make_advertisement,
)

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.bluetooth import (
    inject_bluetooth_service_info_bleak,
    patch_all_discovered_devices,
)


async def test_sensors(hass: HomeAssistant) -> None:
    """Test setting up creates the sensors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="00:81:F9:DD:6F:C1",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    inject_bluetooth_service_info_bleak(hass, MMC_T201_1_SERVICE_INFO)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 2

    temp_sensor = hass.states.get("sensor.baby_thermometer_6fc1_temperature")
    temp_sensor_attribtes = temp_sensor.attributes
    assert temp_sensor.state == "36.8719980616822"
    assert (
        temp_sensor_attribtes[ATTR_FRIENDLY_NAME] == "Baby Thermometer 6FC1 Temperature"
    )
    assert temp_sensor_attribtes[ATTR_UNIT_OF_MEASUREMENT] == "°C"
    assert temp_sensor_attribtes[ATTR_STATE_CLASS] == "measurement"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_xiaomi_formaldeyhde(hass: HomeAssistant) -> None:
    """Make sure that formldehyde sensors are correctly mapped."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="C4:7C:8D:6A:3E:7A",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0

    # WARNING: This test data is synthetic, rather than captured from a real device
    # obj type is 0x1010, payload len is 0x2 and payload is 0xf400
    inject_bluetooth_service_info_bleak(
        hass,
        make_advertisement(
            "C4:7C:8D:6A:3E:7A", b"q \x5d\x01iz>j\x8d|\xc4\r\x10\x10\x02\xf4\x00"
        ),
    )

    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 1

    sensor = hass.states.get("sensor.smart_flower_pot_3e7a_formaldehyde")
    sensor_attr = sensor.attributes
    assert sensor.state == "2.44"
    assert sensor_attr[ATTR_FRIENDLY_NAME] == "Smart Flower Pot 3E7A Formaldehyde"
    assert sensor_attr[ATTR_UNIT_OF_MEASUREMENT] == "mg/m³"
    assert sensor_attr[ATTR_STATE_CLASS] == "measurement"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_xiaomi_consumable(hass: HomeAssistant) -> None:
    """Make sure that consumable sensors are correctly mapped."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="C4:7C:8D:6A:3E:7A",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0

    # WARNING: This test data is synthetic, rather than captured from a real device
    # obj type is 0x1310, payload len is 0x2 and payload is 0x6000
    inject_bluetooth_service_info_bleak(
        hass,
        make_advertisement(
            "C4:7C:8D:6A:3E:7A", b"q \x5d\x01iz>j\x8d|\xc4\r\x13\x10\x02\x60\x00"
        ),
    )

    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 1

    sensor = hass.states.get("sensor.smart_flower_pot_3e7a_consumable")
    sensor_attr = sensor.attributes
    assert sensor.state == "96"
    assert sensor_attr[ATTR_FRIENDLY_NAME] == "Smart Flower Pot 3E7A Consumable"
    assert sensor_attr[ATTR_UNIT_OF_MEASUREMENT] == "%"
    assert sensor_attr[ATTR_STATE_CLASS] == "measurement"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_xiaomi_score(hass: HomeAssistant) -> None:
    """Make sure that score sensors are correctly mapped."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="ED:DE:34:3F:48:0C",
        data={"bindkey": "1330b99cded13258acc391627e9771f7"},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    inject_bluetooth_service_info_bleak(
        hass,
        make_advertisement(
            "ED:DE:34:3F:48:0C",
            b"\x48\x58\x06\x08\xc9H\x0e\xf1\x12\x81\x07\x973\xfc\x14\x00\x00VD\xdbA",
        ),
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 2

    sensor = hass.states.get("sensor.smart_toothbrush_480c_score")

    sensor_attr = sensor.attributes
    assert sensor.state == "83"
    assert sensor_attr[ATTR_FRIENDLY_NAME] == "Smart Toothbrush 480C Score"
    assert sensor_attr[ATTR_STATE_CLASS] == "measurement"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_xiaomi_battery_voltage(hass: HomeAssistant) -> None:
    """Make sure that battery voltage sensors are correctly mapped."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="C4:7C:8D:6A:3E:7A",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # WARNING: This test data is synthetic, rather than captured from a real device
    # obj type is 0x0a10, payload len is 0x2 and payload is 0x6400
    inject_bluetooth_service_info_bleak(
        hass,
        make_advertisement(
            "C4:7C:8D:6A:3E:7A", b"q \x5d\x01iz>j\x8d|\xc4\r\x0a\x10\x02\x64\x00"
        ),
    )

    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 2

    volt_sensor = hass.states.get("sensor.smart_flower_pot_3e7a_voltage")
    volt_sensor_attr = volt_sensor.attributes
    assert volt_sensor.state == "3.1"
    assert volt_sensor_attr[ATTR_FRIENDLY_NAME] == "Smart Flower Pot 3E7A Voltage"
    assert volt_sensor_attr[ATTR_UNIT_OF_MEASUREMENT] == "V"
    assert volt_sensor_attr[ATTR_STATE_CLASS] == "measurement"

    bat_sensor = hass.states.get("sensor.smart_flower_pot_3e7a_battery")
    bat_sensor_attr = bat_sensor.attributes
    assert bat_sensor.state == "100"
    assert bat_sensor_attr[ATTR_FRIENDLY_NAME] == "Smart Flower Pot 3E7A Battery"
    assert bat_sensor_attr[ATTR_UNIT_OF_MEASUREMENT] == "%"
    assert bat_sensor_attr[ATTR_STATE_CLASS] == "measurement"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_xiaomi_hhccjcy01(hass: HomeAssistant) -> None:
    """Test HHCCJCY01 multiple advertisements.

    This device has multiple advertisements before all sensors are visible.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="C4:7C:8D:6A:3E:7A",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    inject_bluetooth_service_info_bleak(
        hass,
        make_advertisement(
            "C4:7C:8D:6A:3E:7A", b"q \x98\x00fz>j\x8d|\xc4\r\x07\x10\x03\x00\x00\x00"
        ),
    )
    inject_bluetooth_service_info_bleak(
        hass,
        make_advertisement(
            "C4:7C:8D:6A:3E:7A", b"q \x98\x00hz>j\x8d|\xc4\r\t\x10\x02W\x02"
        ),
    )
    inject_bluetooth_service_info_bleak(
        hass,
        make_advertisement(
            "C4:7C:8D:6A:3E:7A", b"q \x98\x00Gz>j\x8d|\xc4\r\x08\x10\x01@"
        ),
    )
    inject_bluetooth_service_info_bleak(
        hass,
        make_advertisement(
            "C4:7C:8D:6A:3E:7A", b"q \x98\x00iz>j\x8d|\xc4\r\x04\x10\x02\xf4\x00"
        ),
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 5

    illum_sensor = hass.states.get("sensor.plant_sensor_3e7a_illuminance")
    illum_sensor_attr = illum_sensor.attributes
    assert illum_sensor.state == "0"
    assert illum_sensor_attr[ATTR_FRIENDLY_NAME] == "Plant Sensor 3E7A Illuminance"
    assert illum_sensor_attr[ATTR_UNIT_OF_MEASUREMENT] == "lx"
    assert illum_sensor_attr[ATTR_STATE_CLASS] == "measurement"

    cond_sensor = hass.states.get("sensor.plant_sensor_3e7a_conductivity")
    cond_sensor_attribtes = cond_sensor.attributes
    assert cond_sensor.state == "599"
    assert cond_sensor_attribtes[ATTR_FRIENDLY_NAME] == "Plant Sensor 3E7A Conductivity"
    assert cond_sensor_attribtes[ATTR_UNIT_OF_MEASUREMENT] == "µS/cm"
    assert cond_sensor_attribtes[ATTR_STATE_CLASS] == "measurement"

    moist_sensor = hass.states.get("sensor.plant_sensor_3e7a_moisture")
    moist_sensor_attribtes = moist_sensor.attributes
    assert moist_sensor.state == "64"
    assert moist_sensor_attribtes[ATTR_FRIENDLY_NAME] == "Plant Sensor 3E7A Moisture"
    assert moist_sensor_attribtes[ATTR_UNIT_OF_MEASUREMENT] == "%"
    assert moist_sensor_attribtes[ATTR_STATE_CLASS] == "measurement"

    temp_sensor = hass.states.get("sensor.plant_sensor_3e7a_temperature")
    temp_sensor_attribtes = temp_sensor.attributes
    assert temp_sensor.state == "24.4"
    assert temp_sensor_attribtes[ATTR_FRIENDLY_NAME] == "Plant Sensor 3E7A Temperature"
    assert temp_sensor_attribtes[ATTR_UNIT_OF_MEASUREMENT] == "°C"
    assert temp_sensor_attribtes[ATTR_STATE_CLASS] == "measurement"

    batt_sensor = hass.states.get("sensor.plant_sensor_3e7a_battery")
    batt_sensor_attribtes = batt_sensor.attributes
    assert batt_sensor.state == "5"
    assert batt_sensor_attribtes[ATTR_FRIENDLY_NAME] == "Plant Sensor 3E7A Battery"
    assert batt_sensor_attribtes[ATTR_UNIT_OF_MEASUREMENT] == "%"
    assert batt_sensor_attribtes[ATTR_STATE_CLASS] == "measurement"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_xiaomi_hhccjcy01_not_connectable(hass: HomeAssistant) -> None:
    """Test HHCCJCY01 when sensors are not connectable.

    This device has multiple advertisements before all sensors are visible but not connectable.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="C4:7C:8D:6A:3E:7A",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    inject_bluetooth_service_info_bleak(
        hass,
        make_advertisement(
            "C4:7C:8D:6A:3E:7A",
            b"q \x98\x00fz>j\x8d|\xc4\r\x07\x10\x03\x00\x00\x00",
            connectable=False,
        ),
    )
    inject_bluetooth_service_info_bleak(
        hass,
        make_advertisement(
            "C4:7C:8D:6A:3E:7A",
            b"q \x98\x00hz>j\x8d|\xc4\r\t\x10\x02W\x02",
            connectable=False,
        ),
    )
    inject_bluetooth_service_info_bleak(
        hass,
        make_advertisement(
            "C4:7C:8D:6A:3E:7A",
            b"q \x98\x00Gz>j\x8d|\xc4\r\x08\x10\x01@",
            connectable=False,
        ),
    )
    inject_bluetooth_service_info_bleak(
        hass,
        make_advertisement(
            "C4:7C:8D:6A:3E:7A",
            b"q \x98\x00iz>j\x8d|\xc4\r\x04\x10\x02\xf4\x00",
            connectable=False,
        ),
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 4

    illum_sensor = hass.states.get("sensor.plant_sensor_3e7a_illuminance")
    illum_sensor_attr = illum_sensor.attributes
    assert illum_sensor.state == "0"
    assert illum_sensor_attr[ATTR_FRIENDLY_NAME] == "Plant Sensor 3E7A Illuminance"
    assert illum_sensor_attr[ATTR_UNIT_OF_MEASUREMENT] == "lx"
    assert illum_sensor_attr[ATTR_STATE_CLASS] == "measurement"

    cond_sensor = hass.states.get("sensor.plant_sensor_3e7a_conductivity")
    cond_sensor_attribtes = cond_sensor.attributes
    assert cond_sensor.state == "599"
    assert cond_sensor_attribtes[ATTR_FRIENDLY_NAME] == "Plant Sensor 3E7A Conductivity"
    assert cond_sensor_attribtes[ATTR_UNIT_OF_MEASUREMENT] == "µS/cm"
    assert cond_sensor_attribtes[ATTR_STATE_CLASS] == "measurement"

    moist_sensor = hass.states.get("sensor.plant_sensor_3e7a_moisture")
    moist_sensor_attribtes = moist_sensor.attributes
    assert moist_sensor.state == "64"
    assert moist_sensor_attribtes[ATTR_FRIENDLY_NAME] == "Plant Sensor 3E7A Moisture"
    assert moist_sensor_attribtes[ATTR_UNIT_OF_MEASUREMENT] == "%"
    assert moist_sensor_attribtes[ATTR_STATE_CLASS] == "measurement"

    temp_sensor = hass.states.get("sensor.plant_sensor_3e7a_temperature")
    temp_sensor_attribtes = temp_sensor.attributes
    assert temp_sensor.state == "24.4"
    assert temp_sensor_attribtes[ATTR_FRIENDLY_NAME] == "Plant Sensor 3E7A Temperature"
    assert temp_sensor_attribtes[ATTR_UNIT_OF_MEASUREMENT] == "°C"
    assert temp_sensor_attribtes[ATTR_STATE_CLASS] == "measurement"

    # No battery sensor since its not connectable

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_xiaomi_hhccjcy01_only_some_sources_connectable(
    hass: HomeAssistant,
) -> None:
    """Test HHCCJCY01 partial sources.

    This device has multiple advertisements before all sensors are visible
    and some sources are connectable.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="C4:7C:8D:6A:3E:7A",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    inject_bluetooth_service_info_bleak(
        hass,
        make_advertisement(
            "C4:7C:8D:6A:3E:7A",
            b"q \x98\x00fz>j\x8d|\xc4\r\x07\x10\x03\x00\x00\x00",
            connectable=True,
        ),
    )
    inject_bluetooth_service_info_bleak(
        hass,
        make_advertisement(
            "C4:7C:8D:6A:3E:7A",
            b"q \x98\x00hz>j\x8d|\xc4\r\t\x10\x02W\x02",
            connectable=False,
        ),
    )
    inject_bluetooth_service_info_bleak(
        hass,
        make_advertisement(
            "C4:7C:8D:6A:3E:7A",
            b"q \x98\x00Gz>j\x8d|\xc4\r\x08\x10\x01@",
            connectable=False,
        ),
    )
    inject_bluetooth_service_info_bleak(
        hass,
        make_advertisement(
            "C4:7C:8D:6A:3E:7A",
            b"q \x98\x00iz>j\x8d|\xc4\r\x04\x10\x02\xf4\x00",
            connectable=False,
        ),
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 5

    illum_sensor = hass.states.get("sensor.plant_sensor_3e7a_illuminance")
    illum_sensor_attr = illum_sensor.attributes
    assert illum_sensor.state == "0"
    assert illum_sensor_attr[ATTR_FRIENDLY_NAME] == "Plant Sensor 3E7A Illuminance"
    assert illum_sensor_attr[ATTR_UNIT_OF_MEASUREMENT] == "lx"
    assert illum_sensor_attr[ATTR_STATE_CLASS] == "measurement"

    cond_sensor = hass.states.get("sensor.plant_sensor_3e7a_conductivity")
    cond_sensor_attribtes = cond_sensor.attributes
    assert cond_sensor.state == "599"
    assert cond_sensor_attribtes[ATTR_FRIENDLY_NAME] == "Plant Sensor 3E7A Conductivity"
    assert cond_sensor_attribtes[ATTR_UNIT_OF_MEASUREMENT] == "µS/cm"
    assert cond_sensor_attribtes[ATTR_STATE_CLASS] == "measurement"

    moist_sensor = hass.states.get("sensor.plant_sensor_3e7a_moisture")
    moist_sensor_attribtes = moist_sensor.attributes
    assert moist_sensor.state == "64"
    assert moist_sensor_attribtes[ATTR_FRIENDLY_NAME] == "Plant Sensor 3E7A Moisture"
    assert moist_sensor_attribtes[ATTR_UNIT_OF_MEASUREMENT] == "%"
    assert moist_sensor_attribtes[ATTR_STATE_CLASS] == "measurement"

    temp_sensor = hass.states.get("sensor.plant_sensor_3e7a_temperature")
    temp_sensor_attribtes = temp_sensor.attributes
    assert temp_sensor.state == "24.4"
    assert temp_sensor_attribtes[ATTR_FRIENDLY_NAME] == "Plant Sensor 3E7A Temperature"
    assert temp_sensor_attribtes[ATTR_UNIT_OF_MEASUREMENT] == "°C"
    assert temp_sensor_attribtes[ATTR_STATE_CLASS] == "measurement"

    batt_sensor = hass.states.get("sensor.plant_sensor_3e7a_battery")
    batt_sensor_attribtes = batt_sensor.attributes
    assert batt_sensor.state == "5"
    assert batt_sensor_attribtes[ATTR_FRIENDLY_NAME] == "Plant Sensor 3E7A Battery"
    assert batt_sensor_attribtes[ATTR_UNIT_OF_MEASUREMENT] == "%"
    assert batt_sensor_attribtes[ATTR_STATE_CLASS] == "measurement"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_xiaomi_cgdk2_bind_key(hass: HomeAssistant) -> None:
    """Test CGDK2 bind key.

    This device has encryption so we need to retrieve its bind key
    from the config entry.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="58:2D:34:12:20:89",
        data={"bindkey": "a3bfe9853dd85a620debe3620caaa351"},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    inject_bluetooth_service_info_bleak(
        hass,
        make_advertisement(
            "58:2D:34:12:20:89",
            b"XXo\x06\x07\x89 \x124-X_\x17m\xd5O\x02\x00\x00/\xa4S\xfa",
        ),
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 1

    temp_sensor = hass.states.get("sensor.temperature_humidity_sensor_2089_temperature")
    temp_sensor_attribtes = temp_sensor.attributes
    assert temp_sensor.state == "22.6"
    assert (
        temp_sensor_attribtes[ATTR_FRIENDLY_NAME]
        == "Temperature/Humidity Sensor 2089 Temperature"
    )
    assert temp_sensor_attribtes[ATTR_UNIT_OF_MEASUREMENT] == "°C"
    assert temp_sensor_attribtes[ATTR_STATE_CLASS] == "measurement"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_hhccjcy10_uuid(hass: HomeAssistant) -> None:
    """Test HHCCJCY10 UUID.

    This device uses a different UUID compared to the other Xiaomi sensors.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="DC:23:4D:E5:5B:FC",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    inject_bluetooth_service_info_bleak(hass, HHCCJCY10_SERVICE_INFO)

    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 5

    temp_sensor = hass.states.get("sensor.plant_sensor_5bfc_temperature")
    temp_sensor_attr = temp_sensor.attributes
    assert temp_sensor.state == "11.0"
    assert temp_sensor_attr[ATTR_FRIENDLY_NAME] == "Plant Sensor 5BFC Temperature"
    assert temp_sensor_attr[ATTR_UNIT_OF_MEASUREMENT] == "°C"
    assert temp_sensor_attr[ATTR_STATE_CLASS] == "measurement"

    illu_sensor = hass.states.get("sensor.plant_sensor_5bfc_illuminance")
    illu_sensor_attr = illu_sensor.attributes
    assert illu_sensor.state == "79012"
    assert illu_sensor_attr[ATTR_FRIENDLY_NAME] == "Plant Sensor 5BFC Illuminance"
    assert illu_sensor_attr[ATTR_UNIT_OF_MEASUREMENT] == "lx"
    assert illu_sensor_attr[ATTR_STATE_CLASS] == "measurement"

    cond_sensor = hass.states.get("sensor.plant_sensor_5bfc_conductivity")
    cond_sensor_attr = cond_sensor.attributes
    assert cond_sensor.state == "91"
    assert cond_sensor_attr[ATTR_FRIENDLY_NAME] == "Plant Sensor 5BFC Conductivity"
    assert cond_sensor_attr[ATTR_UNIT_OF_MEASUREMENT] == "µS/cm"
    assert cond_sensor_attr[ATTR_STATE_CLASS] == "measurement"

    moist_sensor = hass.states.get("sensor.plant_sensor_5bfc_moisture")
    moist_sensor_attr = moist_sensor.attributes
    assert moist_sensor.state == "14"
    assert moist_sensor_attr[ATTR_FRIENDLY_NAME] == "Plant Sensor 5BFC Moisture"
    assert moist_sensor_attr[ATTR_UNIT_OF_MEASUREMENT] == "%"
    assert moist_sensor_attr[ATTR_STATE_CLASS] == "measurement"

    bat_sensor = hass.states.get("sensor.plant_sensor_5bfc_battery")
    bat_sensor_attr = bat_sensor.attributes
    assert bat_sensor.state == "40"
    assert bat_sensor_attr[ATTR_FRIENDLY_NAME] == "Plant Sensor 5BFC Battery"
    assert bat_sensor_attr[ATTR_UNIT_OF_MEASUREMENT] == "%"
    assert bat_sensor_attr[ATTR_STATE_CLASS] == "measurement"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_miscale_v1_uuid(hass: HomeAssistant) -> None:
    """Test MiScale V1 UUID.

    This device uses a different UUID compared to the other Xiaomi sensors.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="50:FB:19:1B:B5:DC",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    inject_bluetooth_service_info_bleak(hass, MISCALE_V1_SERVICE_INFO)

    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 2

    mass_non_stabilized_sensor = hass.states.get(
        "sensor.mi_smart_scale_b5dc_mass_non_stabilized"
    )
    mass_non_stabilized_sensor_attr = mass_non_stabilized_sensor.attributes
    assert mass_non_stabilized_sensor.state == "86.55"
    assert (
        mass_non_stabilized_sensor_attr[ATTR_FRIENDLY_NAME]
        == "Mi Smart Scale (B5DC) Mass Non Stabilized"
    )
    assert mass_non_stabilized_sensor_attr[ATTR_UNIT_OF_MEASUREMENT] == "kg"
    assert mass_non_stabilized_sensor_attr[ATTR_STATE_CLASS] == "measurement"

    mass_sensor = hass.states.get("sensor.mi_smart_scale_b5dc_mass")
    mass_sensor_attr = mass_sensor.attributes
    assert mass_sensor.state == "86.55"
    assert mass_sensor_attr[ATTR_FRIENDLY_NAME] == "Mi Smart Scale (B5DC) Mass"
    assert mass_sensor_attr[ATTR_UNIT_OF_MEASUREMENT] == "kg"
    assert mass_sensor_attr[ATTR_STATE_CLASS] == "measurement"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_miscale_v2_uuid(hass: HomeAssistant) -> None:
    """Test MiScale V2 UUID.

    This device uses a different UUID compared to the other Xiaomi sensors.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="50:FB:19:1B:B5:DC",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    inject_bluetooth_service_info_bleak(hass, MISCALE_V2_SERVICE_INFO)

    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 3

    mass_non_stabilized_sensor = hass.states.get(
        "sensor.mi_body_composition_scale_b5dc_mass_non_stabilized"
    )
    mass_non_stabilized_sensor_attr = mass_non_stabilized_sensor.attributes
    assert mass_non_stabilized_sensor.state == "85.15"
    assert (
        mass_non_stabilized_sensor_attr[ATTR_FRIENDLY_NAME]
        == "Mi Body Composition Scale (B5DC) Mass Non Stabilized"
    )
    assert mass_non_stabilized_sensor_attr[ATTR_UNIT_OF_MEASUREMENT] == "kg"
    assert mass_non_stabilized_sensor_attr[ATTR_STATE_CLASS] == "measurement"

    mass_sensor = hass.states.get("sensor.mi_body_composition_scale_b5dc_mass")
    mass_sensor_attr = mass_sensor.attributes
    assert mass_sensor.state == "85.15"
    assert (
        mass_sensor_attr[ATTR_FRIENDLY_NAME] == "Mi Body Composition Scale (B5DC) Mass"
    )
    assert mass_sensor_attr[ATTR_UNIT_OF_MEASUREMENT] == "kg"
    assert mass_sensor_attr[ATTR_STATE_CLASS] == "measurement"

    impedance_sensor = hass.states.get(
        "sensor.mi_body_composition_scale_b5dc_impedance"
    )
    impedance_sensor_attr = impedance_sensor.attributes
    assert impedance_sensor.state == "428"
    assert (
        impedance_sensor_attr[ATTR_FRIENDLY_NAME]
        == "Mi Body Composition Scale (B5DC) Impedance"
    )
    assert impedance_sensor_attr[ATTR_UNIT_OF_MEASUREMENT] == "ohm"
    assert impedance_sensor_attr[ATTR_STATE_CLASS] == "measurement"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_unavailable(hass: HomeAssistant) -> None:
    """Test normal device goes to unavailable after 60 minutes."""
    start_monotonic = time.monotonic()

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="58:2D:34:12:20:89",
        data={"bindkey": "a3bfe9853dd85a620debe3620caaa351"},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    inject_bluetooth_service_info_bleak(
        hass,
        make_advertisement(
            "58:2D:34:12:20:89",
            b"XXo\x06\x07\x89 \x124-X_\x17m\xd5O\x02\x00\x00/\xa4S\xfa",
        ),
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 1

    temp_sensor = hass.states.get("sensor.temperature_humidity_sensor_2089_temperature")
    assert temp_sensor.state == "22.6"

    # Fastforward time without BLE advertisements
    monotonic_now = start_monotonic + FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS + 1

    with patch(
        "homeassistant.components.bluetooth.manager.MONOTONIC_TIME",
        return_value=monotonic_now,
    ), patch_all_discovered_devices([]):
        async_fire_time_changed(
            hass,
            dt_util.utcnow()
            + timedelta(seconds=FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS + 1),
        )
        await hass.async_block_till_done()

    temp_sensor = hass.states.get("sensor.temperature_humidity_sensor_2089_temperature")

    # Sleepy devices should keep their state over time
    assert temp_sensor.state == STATE_UNAVAILABLE

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_sleepy_device(hass: HomeAssistant) -> None:
    """Test sleepy devices stay available."""
    start_monotonic = time.monotonic()

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="50:FB:19:1B:B5:DC",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    inject_bluetooth_service_info_bleak(hass, MISCALE_V1_SERVICE_INFO)

    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 2

    mass_non_stabilized_sensor = hass.states.get(
        "sensor.mi_smart_scale_b5dc_mass_non_stabilized"
    )
    assert mass_non_stabilized_sensor.state == "86.55"

    # Fastforward time without BLE advertisements
    monotonic_now = start_monotonic + FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS + 1

    with patch(
        "homeassistant.components.bluetooth.manager.MONOTONIC_TIME",
        return_value=monotonic_now,
    ), patch_all_discovered_devices([]):
        async_fire_time_changed(
            hass,
            dt_util.utcnow()
            + timedelta(seconds=FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS + 1),
        )
        await hass.async_block_till_done()

    mass_non_stabilized_sensor = hass.states.get(
        "sensor.mi_smart_scale_b5dc_mass_non_stabilized"
    )

    # Sleepy devices should keep their state over time
    assert mass_non_stabilized_sensor.state == "86.55"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_sleepy_device_restore_state(hass: HomeAssistant) -> None:
    """Test sleepy devices stay available."""
    start_monotonic = time.monotonic()

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="50:FB:19:1B:B5:DC",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    inject_bluetooth_service_info_bleak(hass, MISCALE_V1_SERVICE_INFO)

    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 2

    mass_non_stabilized_sensor = hass.states.get(
        "sensor.mi_smart_scale_b5dc_mass_non_stabilized"
    )
    assert mass_non_stabilized_sensor.state == "86.55"

    # Fastforward time without BLE advertisements
    monotonic_now = start_monotonic + FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS + 1

    with patch(
        "homeassistant.components.bluetooth.manager.MONOTONIC_TIME",
        return_value=monotonic_now,
    ), patch_all_discovered_devices([]):
        async_fire_time_changed(
            hass,
            dt_util.utcnow()
            + timedelta(seconds=FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS + 1),
        )
        await hass.async_block_till_done()

    mass_non_stabilized_sensor = hass.states.get(
        "sensor.mi_smart_scale_b5dc_mass_non_stabilized"
    )

    # Sleepy devices should keep their state over time
    assert mass_non_stabilized_sensor.state == "86.55"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    mass_non_stabilized_sensor = hass.states.get(
        "sensor.mi_smart_scale_b5dc_mass_non_stabilized"
    )

    # Sleepy devices should keep their state over time and restore it
    assert mass_non_stabilized_sensor.state == "86.55"

    assert entry.data[CONF_SLEEPY_DEVICE] is True

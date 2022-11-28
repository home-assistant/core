"""Test the Xiaomi config flow."""

from unittest.mock import patch

from homeassistant.components.bluetooth import (
    BluetoothChange,
    async_get_advertisement_callback,
)
from homeassistant.components.sensor import ATTR_STATE_CLASS
from homeassistant.components.xiaomi_ble.const import DOMAIN
from homeassistant.const import ATTR_FRIENDLY_NAME, ATTR_UNIT_OF_MEASUREMENT

from . import MMC_T201_1_SERVICE_INFO, make_advertisement

from tests.common import MockConfigEntry


async def test_sensors(hass):
    """Test setting up creates the sensors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="00:81:F9:DD:6F:C1",
    )
    entry.add_to_hass(hass)

    saved_callback = None

    def _async_register_callback(_hass, _callback, _matcher, _mode):
        nonlocal saved_callback
        saved_callback = _callback
        return lambda: None

    with patch(
        "homeassistant.components.bluetooth.update_coordinator.async_register_callback",
        _async_register_callback,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    saved_callback(MMC_T201_1_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 2

    temp_sensor = hass.states.get("sensor.baby_thermometer_dd6fc1_temperature")
    temp_sensor_attribtes = temp_sensor.attributes
    assert temp_sensor.state == "36.8719980616822"
    assert (
        temp_sensor_attribtes[ATTR_FRIENDLY_NAME]
        == "Baby Thermometer DD6FC1 Temperature"
    )
    assert temp_sensor_attribtes[ATTR_UNIT_OF_MEASUREMENT] == "°C"
    assert temp_sensor_attribtes[ATTR_STATE_CLASS] == "measurement"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_xiaomi_formaldeyhde(hass):
    """Make sure that formldehyde sensors are correctly mapped."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="C4:7C:8D:6A:3E:7A",
    )
    entry.add_to_hass(hass)

    saved_callback = None

    def _async_register_callback(_hass, _callback, _matcher, _mode):
        nonlocal saved_callback
        saved_callback = _callback
        return lambda: None

    with patch(
        "homeassistant.components.bluetooth.update_coordinator.async_register_callback",
        _async_register_callback,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0

    # WARNING: This test data is synthetic, rather than captured from a real device
    # obj type is 0x1010, payload len is 0x2 and payload is 0xf400
    saved_callback(
        make_advertisement(
            "C4:7C:8D:6A:3E:7A", b"q \x5d\x01iz>j\x8d|\xc4\r\x10\x10\x02\xf4\x00"
        ),
        BluetoothChange.ADVERTISEMENT,
    )

    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 1

    sensor = hass.states.get("sensor.smart_flower_pot_6a3e7a_formaldehyde")
    sensor_attr = sensor.attributes
    assert sensor.state == "2.44"
    assert sensor_attr[ATTR_FRIENDLY_NAME] == "Smart Flower Pot 6A3E7A Formaldehyde"
    assert sensor_attr[ATTR_UNIT_OF_MEASUREMENT] == "mg/m³"
    assert sensor_attr[ATTR_STATE_CLASS] == "measurement"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_xiaomi_consumable(hass):
    """Make sure that consumable sensors are correctly mapped."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="C4:7C:8D:6A:3E:7A",
    )
    entry.add_to_hass(hass)

    saved_callback = None

    def _async_register_callback(_hass, _callback, _matcher, _mode):
        nonlocal saved_callback
        saved_callback = _callback
        return lambda: None

    with patch(
        "homeassistant.components.bluetooth.update_coordinator.async_register_callback",
        _async_register_callback,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0

    # WARNING: This test data is synthetic, rather than captured from a real device
    # obj type is 0x1310, payload len is 0x2 and payload is 0x6000
    saved_callback(
        make_advertisement(
            "C4:7C:8D:6A:3E:7A", b"q \x5d\x01iz>j\x8d|\xc4\r\x13\x10\x02\x60\x00"
        ),
        BluetoothChange.ADVERTISEMENT,
    )

    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 1

    sensor = hass.states.get("sensor.smart_flower_pot_6a3e7a_consumable")
    sensor_attr = sensor.attributes
    assert sensor.state == "96"
    assert sensor_attr[ATTR_FRIENDLY_NAME] == "Smart Flower Pot 6A3E7A Consumable"
    assert sensor_attr[ATTR_UNIT_OF_MEASUREMENT] == "%"
    assert sensor_attr[ATTR_STATE_CLASS] == "measurement"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_xiaomi_battery_voltage(hass):
    """Make sure that battery voltage sensors are correctly mapped."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="C4:7C:8D:6A:3E:7A",
    )
    entry.add_to_hass(hass)

    saved_callback = None

    def _async_register_callback(_hass, _callback, _matcher, _mode):
        nonlocal saved_callback
        saved_callback = _callback
        return lambda: None

    with patch(
        "homeassistant.components.bluetooth.update_coordinator.async_register_callback",
        _async_register_callback,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0

    # WARNING: This test data is synthetic, rather than captured from a real device
    # obj type is 0x0a10, payload len is 0x2 and payload is 0x6400
    saved_callback(
        make_advertisement(
            "C4:7C:8D:6A:3E:7A", b"q \x5d\x01iz>j\x8d|\xc4\r\x0a\x10\x02\x64\x00"
        ),
        BluetoothChange.ADVERTISEMENT,
    )

    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 2

    volt_sensor = hass.states.get("sensor.smart_flower_pot_6a3e7a_voltage")
    volt_sensor_attr = volt_sensor.attributes
    assert volt_sensor.state == "3.1"
    assert volt_sensor_attr[ATTR_FRIENDLY_NAME] == "Smart Flower Pot 6A3E7A Voltage"
    assert volt_sensor_attr[ATTR_UNIT_OF_MEASUREMENT] == "V"
    assert volt_sensor_attr[ATTR_STATE_CLASS] == "measurement"

    bat_sensor = hass.states.get("sensor.smart_flower_pot_6a3e7a_battery")
    bat_sensor_attr = bat_sensor.attributes
    assert bat_sensor.state == "100"
    assert bat_sensor_attr[ATTR_FRIENDLY_NAME] == "Smart Flower Pot 6A3E7A Battery"
    assert bat_sensor_attr[ATTR_UNIT_OF_MEASUREMENT] == "%"
    assert bat_sensor_attr[ATTR_STATE_CLASS] == "measurement"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_xiaomi_HHCCJCY01(hass):
    """This device has multiple advertisements before all sensors are visible. Test that this works."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="C4:7C:8D:6A:3E:7A",
    )
    entry.add_to_hass(hass)

    saved_callback = None

    def _async_register_callback(_hass, _callback, _matcher, _mode):
        nonlocal saved_callback
        saved_callback = _callback
        return lambda: None

    with patch(
        "homeassistant.components.bluetooth.update_coordinator.async_register_callback",
        _async_register_callback,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    saved_callback(
        make_advertisement(
            "C4:7C:8D:6A:3E:7A", b"q \x98\x00fz>j\x8d|\xc4\r\x07\x10\x03\x00\x00\x00"
        ),
        BluetoothChange.ADVERTISEMENT,
    )
    saved_callback(
        make_advertisement(
            "C4:7C:8D:6A:3E:7A", b"q \x98\x00hz>j\x8d|\xc4\r\t\x10\x02W\x02"
        ),
        BluetoothChange.ADVERTISEMENT,
    )
    saved_callback(
        make_advertisement(
            "C4:7C:8D:6A:3E:7A", b"q \x98\x00Gz>j\x8d|\xc4\r\x08\x10\x01@"
        ),
        BluetoothChange.ADVERTISEMENT,
    )
    saved_callback(
        make_advertisement(
            "C4:7C:8D:6A:3E:7A", b"q \x98\x00iz>j\x8d|\xc4\r\x04\x10\x02\xf4\x00"
        ),
        BluetoothChange.ADVERTISEMENT,
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 5

    illum_sensor = hass.states.get("sensor.plant_sensor_6a3e7a_illuminance")
    illum_sensor_attr = illum_sensor.attributes
    assert illum_sensor.state == "0"
    assert illum_sensor_attr[ATTR_FRIENDLY_NAME] == "Plant Sensor 6A3E7A Illuminance"
    assert illum_sensor_attr[ATTR_UNIT_OF_MEASUREMENT] == "lx"
    assert illum_sensor_attr[ATTR_STATE_CLASS] == "measurement"

    cond_sensor = hass.states.get("sensor.plant_sensor_6a3e7a_conductivity")
    cond_sensor_attribtes = cond_sensor.attributes
    assert cond_sensor.state == "599"
    assert (
        cond_sensor_attribtes[ATTR_FRIENDLY_NAME] == "Plant Sensor 6A3E7A Conductivity"
    )
    assert cond_sensor_attribtes[ATTR_UNIT_OF_MEASUREMENT] == "µS/cm"
    assert cond_sensor_attribtes[ATTR_STATE_CLASS] == "measurement"

    moist_sensor = hass.states.get("sensor.plant_sensor_6a3e7a_moisture")
    moist_sensor_attribtes = moist_sensor.attributes
    assert moist_sensor.state == "64"
    assert moist_sensor_attribtes[ATTR_FRIENDLY_NAME] == "Plant Sensor 6A3E7A Moisture"
    assert moist_sensor_attribtes[ATTR_UNIT_OF_MEASUREMENT] == "%"
    assert moist_sensor_attribtes[ATTR_STATE_CLASS] == "measurement"

    temp_sensor = hass.states.get("sensor.plant_sensor_6a3e7a_temperature")
    temp_sensor_attribtes = temp_sensor.attributes
    assert temp_sensor.state == "24.4"
    assert (
        temp_sensor_attribtes[ATTR_FRIENDLY_NAME] == "Plant Sensor 6A3E7A Temperature"
    )
    assert temp_sensor_attribtes[ATTR_UNIT_OF_MEASUREMENT] == "°C"
    assert temp_sensor_attribtes[ATTR_STATE_CLASS] == "measurement"

    batt_sensor = hass.states.get("sensor.plant_sensor_6a3e7a_battery")
    batt_sensor_attribtes = batt_sensor.attributes
    assert batt_sensor.state == "5"
    assert batt_sensor_attribtes[ATTR_FRIENDLY_NAME] == "Plant Sensor 6A3E7A Battery"
    assert batt_sensor_attribtes[ATTR_UNIT_OF_MEASUREMENT] == "%"
    assert batt_sensor_attribtes[ATTR_STATE_CLASS] == "measurement"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_xiaomi_HHCCJCY01_not_connectable(hass):
    """This device has multiple advertisements before all sensors are visible but not connectable."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="C4:7C:8D:6A:3E:7B",
    )
    entry.add_to_hass(hass)

    saved_callback = None

    def _async_register_callback(_hass, _callback, _matcher, _mode):
        nonlocal saved_callback
        saved_callback = _callback
        return lambda: None

    with patch(
        "homeassistant.components.bluetooth.update_coordinator.async_register_callback",
        _async_register_callback,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    saved_callback(
        make_advertisement(
            "C4:7C:8D:6A:3E:7A",
            b"q \x98\x00fz>j\x8d|\xc4\r\x07\x10\x03\x00\x00\x00",
            connectable=False,
        ),
        BluetoothChange.ADVERTISEMENT,
    )
    saved_callback(
        make_advertisement(
            "C4:7C:8D:6A:3E:7A",
            b"q \x98\x00hz>j\x8d|\xc4\r\t\x10\x02W\x02",
            connectable=False,
        ),
        BluetoothChange.ADVERTISEMENT,
    )
    saved_callback(
        make_advertisement(
            "C4:7C:8D:6A:3E:7A",
            b"q \x98\x00Gz>j\x8d|\xc4\r\x08\x10\x01@",
            connectable=False,
        ),
        BluetoothChange.ADVERTISEMENT,
    )
    saved_callback(
        make_advertisement(
            "C4:7C:8D:6A:3E:7A",
            b"q \x98\x00iz>j\x8d|\xc4\r\x04\x10\x02\xf4\x00",
            connectable=False,
        ),
        BluetoothChange.ADVERTISEMENT,
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 4

    illum_sensor = hass.states.get("sensor.plant_sensor_6a3e7a_illuminance")
    illum_sensor_attr = illum_sensor.attributes
    assert illum_sensor.state == "0"
    assert illum_sensor_attr[ATTR_FRIENDLY_NAME] == "Plant Sensor 6A3E7A Illuminance"
    assert illum_sensor_attr[ATTR_UNIT_OF_MEASUREMENT] == "lx"
    assert illum_sensor_attr[ATTR_STATE_CLASS] == "measurement"

    cond_sensor = hass.states.get("sensor.plant_sensor_6a3e7a_conductivity")
    cond_sensor_attribtes = cond_sensor.attributes
    assert cond_sensor.state == "599"
    assert (
        cond_sensor_attribtes[ATTR_FRIENDLY_NAME] == "Plant Sensor 6A3E7A Conductivity"
    )
    assert cond_sensor_attribtes[ATTR_UNIT_OF_MEASUREMENT] == "µS/cm"
    assert cond_sensor_attribtes[ATTR_STATE_CLASS] == "measurement"

    moist_sensor = hass.states.get("sensor.plant_sensor_6a3e7a_moisture")
    moist_sensor_attribtes = moist_sensor.attributes
    assert moist_sensor.state == "64"
    assert moist_sensor_attribtes[ATTR_FRIENDLY_NAME] == "Plant Sensor 6A3E7A Moisture"
    assert moist_sensor_attribtes[ATTR_UNIT_OF_MEASUREMENT] == "%"
    assert moist_sensor_attribtes[ATTR_STATE_CLASS] == "measurement"

    temp_sensor = hass.states.get("sensor.plant_sensor_6a3e7a_temperature")
    temp_sensor_attribtes = temp_sensor.attributes
    assert temp_sensor.state == "24.4"
    assert (
        temp_sensor_attribtes[ATTR_FRIENDLY_NAME] == "Plant Sensor 6A3E7A Temperature"
    )
    assert temp_sensor_attribtes[ATTR_UNIT_OF_MEASUREMENT] == "°C"
    assert temp_sensor_attribtes[ATTR_STATE_CLASS] == "measurement"

    # No battery sensor since its not connectable

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_xiaomi_HHCCJCY01_only_some_sources_connectable(hass):
    """This device has multiple advertisements before all sensors are visible and some sources are connectable."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="C4:7C:8D:6A:3E:7A",
    )
    entry.add_to_hass(hass)

    saved_callback = async_get_advertisement_callback(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    saved_callback(
        make_advertisement(
            "C4:7C:8D:6A:3E:7A",
            b"q \x98\x00fz>j\x8d|\xc4\r\x07\x10\x03\x00\x00\x00",
            connectable=True,
        ),
    )
    saved_callback(
        make_advertisement(
            "C4:7C:8D:6A:3E:7A",
            b"q \x98\x00hz>j\x8d|\xc4\r\t\x10\x02W\x02",
            connectable=False,
        ),
    )
    saved_callback(
        make_advertisement(
            "C4:7C:8D:6A:3E:7A",
            b"q \x98\x00Gz>j\x8d|\xc4\r\x08\x10\x01@",
            connectable=False,
        ),
    )
    saved_callback(
        make_advertisement(
            "C4:7C:8D:6A:3E:7A",
            b"q \x98\x00iz>j\x8d|\xc4\r\x04\x10\x02\xf4\x00",
            connectable=False,
        ),
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 5

    illum_sensor = hass.states.get("sensor.plant_sensor_6a3e7a_illuminance")
    illum_sensor_attr = illum_sensor.attributes
    assert illum_sensor.state == "0"
    assert illum_sensor_attr[ATTR_FRIENDLY_NAME] == "Plant Sensor 6A3E7A Illuminance"
    assert illum_sensor_attr[ATTR_UNIT_OF_MEASUREMENT] == "lx"
    assert illum_sensor_attr[ATTR_STATE_CLASS] == "measurement"

    cond_sensor = hass.states.get("sensor.plant_sensor_6a3e7a_conductivity")
    cond_sensor_attribtes = cond_sensor.attributes
    assert cond_sensor.state == "599"
    assert (
        cond_sensor_attribtes[ATTR_FRIENDLY_NAME] == "Plant Sensor 6A3E7A Conductivity"
    )
    assert cond_sensor_attribtes[ATTR_UNIT_OF_MEASUREMENT] == "µS/cm"
    assert cond_sensor_attribtes[ATTR_STATE_CLASS] == "measurement"

    moist_sensor = hass.states.get("sensor.plant_sensor_6a3e7a_moisture")
    moist_sensor_attribtes = moist_sensor.attributes
    assert moist_sensor.state == "64"
    assert moist_sensor_attribtes[ATTR_FRIENDLY_NAME] == "Plant Sensor 6A3E7A Moisture"
    assert moist_sensor_attribtes[ATTR_UNIT_OF_MEASUREMENT] == "%"
    assert moist_sensor_attribtes[ATTR_STATE_CLASS] == "measurement"

    temp_sensor = hass.states.get("sensor.plant_sensor_6a3e7a_temperature")
    temp_sensor_attribtes = temp_sensor.attributes
    assert temp_sensor.state == "24.4"
    assert (
        temp_sensor_attribtes[ATTR_FRIENDLY_NAME] == "Plant Sensor 6A3E7A Temperature"
    )
    assert temp_sensor_attribtes[ATTR_UNIT_OF_MEASUREMENT] == "°C"
    assert temp_sensor_attribtes[ATTR_STATE_CLASS] == "measurement"

    batt_sensor = hass.states.get("sensor.plant_sensor_6a3e7a_battery")
    batt_sensor_attribtes = batt_sensor.attributes
    assert batt_sensor.state == "5"
    assert batt_sensor_attribtes[ATTR_FRIENDLY_NAME] == "Plant Sensor 6A3E7A Battery"
    assert batt_sensor_attribtes[ATTR_UNIT_OF_MEASUREMENT] == "%"
    assert batt_sensor_attribtes[ATTR_STATE_CLASS] == "measurement"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_xiaomi_CGDK2(hass):
    """This device has encrypion so we need to retrieve its bindkey from the configentry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="58:2D:34:12:20:89",
        data={"bindkey": "a3bfe9853dd85a620debe3620caaa351"},
    )
    entry.add_to_hass(hass)

    saved_callback = None

    def _async_register_callback(_hass, _callback, _matcher, _mode):
        nonlocal saved_callback
        saved_callback = _callback
        return lambda: None

    with patch(
        "homeassistant.components.bluetooth.update_coordinator.async_register_callback",
        _async_register_callback,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    saved_callback(
        make_advertisement(
            "58:2D:34:12:20:89",
            b"XXo\x06\x07\x89 \x124-X_\x17m\xd5O\x02\x00\x00/\xa4S\xfa",
        ),
        BluetoothChange.ADVERTISEMENT,
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 1

    temp_sensor = hass.states.get(
        "sensor.temperature_humidity_sensor_122089_temperature"
    )
    temp_sensor_attribtes = temp_sensor.attributes
    assert temp_sensor.state == "22.6"
    assert (
        temp_sensor_attribtes[ATTR_FRIENDLY_NAME]
        == "Temperature/Humidity Sensor 122089 Temperature"
    )
    assert temp_sensor_attribtes[ATTR_UNIT_OF_MEASUREMENT] == "°C"
    assert temp_sensor_attribtes[ATTR_STATE_CLASS] == "measurement"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

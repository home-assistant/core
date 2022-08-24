"""Test the BThome sensors."""

from unittest.mock import patch

from homeassistant.components.bluetooth import BluetoothChange
from homeassistant.components.bthome.const import DOMAIN
from homeassistant.components.sensor import ATTR_STATE_CLASS
from homeassistant.const import ATTR_FRIENDLY_NAME, ATTR_UNIT_OF_MEASUREMENT

from . import TEMP_HUMI_SERVICE_INFO, make_advertisement, make_encrypted_advertisement

from tests.common import MockConfigEntry


async def test_sensors(hass):
    """Test setting up creates the sensors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="A4:C1:38:8D:18:B2",
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
    saved_callback(TEMP_HUMI_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 2

    temp_sensor = hass.states.get("sensor.atc_8d18b2_temperature")
    temp_sensor_attribtes = temp_sensor.attributes
    assert temp_sensor.state == "25.06"

    assert temp_sensor_attribtes[ATTR_FRIENDLY_NAME] == "ATC 8D18B2 Temperature"
    assert temp_sensor_attribtes[ATTR_UNIT_OF_MEASUREMENT] == "°C"
    assert temp_sensor_attribtes[ATTR_STATE_CLASS] == "measurement"

    humi_sensor = hass.states.get("sensor.atc_8d18b2_humidity")
    humi_sensor_attribtes = humi_sensor.attributes
    assert humi_sensor.state == "50.55"

    assert humi_sensor_attribtes[ATTR_FRIENDLY_NAME] == "ATC 8D18B2 Humidity"
    assert humi_sensor_attribtes[ATTR_UNIT_OF_MEASUREMENT] == "%"
    assert humi_sensor_attribtes[ATTR_STATE_CLASS] == "measurement"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_bthome_temperature_humidity_battery(hass):
    """Make sure that temperature, humidity and battery sensors are correctly mapped."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="A4:C1:38:8D:18:B2",
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
            "A4:C1:38:8D:18:B2", b"\x02\x00\xa8#\x02]\t\x03\x03\xb7\x18\x02\x01]"
        ),
        BluetoothChange.ADVERTISEMENT,
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 3

    temp_sensor = hass.states.get("sensor.test_device_8d18b2_temperature")
    temp_sensor_attribtes = temp_sensor.attributes
    assert temp_sensor.state == "23.97"

    assert temp_sensor_attribtes[ATTR_FRIENDLY_NAME] == "Test Device 8D18B2 Temperature"
    assert temp_sensor_attribtes[ATTR_UNIT_OF_MEASUREMENT] == "°C"
    assert temp_sensor_attribtes[ATTR_STATE_CLASS] == "measurement"

    humi_sensor = hass.states.get("sensor.test_device_8d18b2_humidity")
    humi_sensor_attribtes = humi_sensor.attributes
    assert humi_sensor.state == "63.27"

    assert humi_sensor_attribtes[ATTR_FRIENDLY_NAME] == "Test Device 8D18B2 Humidity"
    assert humi_sensor_attribtes[ATTR_UNIT_OF_MEASUREMENT] == "%"
    assert humi_sensor_attribtes[ATTR_STATE_CLASS] == "measurement"

    batt_sensor = hass.states.get("sensor.test_device_8d18b2_battery")
    batt_sensor_attr = batt_sensor.attributes
    assert batt_sensor.state == "93"

    assert batt_sensor_attr[ATTR_FRIENDLY_NAME] == "Test Device 8D18B2 Battery"
    assert batt_sensor_attr[ATTR_UNIT_OF_MEASUREMENT] == "%"
    assert batt_sensor_attr[ATTR_STATE_CLASS] == "measurement"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_bthome_pressure(hass):
    """Make sure that pressure sensors are correctly mapped."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="A4:C1:38:8D:18:B2",
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
        make_advertisement("A4:C1:38:8D:18:B2", b"\x02\x00\x0c\x04\x04\x13\x8a\x01"),
        BluetoothChange.ADVERTISEMENT,
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 1

    sensor = hass.states.get("sensor.test_device_8d18b2_pressure")
    sensor_attr = sensor.attributes
    assert sensor.state == "1008.83"

    assert sensor_attr[ATTR_FRIENDLY_NAME] == "Test Device 8D18B2 Pressure"
    assert sensor_attr[ATTR_UNIT_OF_MEASUREMENT] == "mbar"
    assert sensor_attr[ATTR_STATE_CLASS] == "measurement"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_bthome_illuminance(hass):
    """Make sure that illuminance sensors are correctly mapped."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="A4:C1:38:8D:18:B2",
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
        make_advertisement("A4:C1:38:8D:18:B2", b"\x04\x05\x13\x8a\x14"),
        BluetoothChange.ADVERTISEMENT,
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 1

    sensor = hass.states.get("sensor.test_device_8d18b2_illuminance")
    sensor_attr = sensor.attributes
    assert sensor.state == "13460.67"

    assert sensor_attr[ATTR_FRIENDLY_NAME] == "Test Device 8D18B2 Illuminance"
    assert sensor_attr[ATTR_UNIT_OF_MEASUREMENT] == "lx"
    assert sensor_attr[ATTR_STATE_CLASS] == "measurement"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_bthome_energy(hass):
    """Make sure that energy sensors are correctly mapped."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="A4:C1:38:8D:18:B2",
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
        make_advertisement("A4:C1:38:8D:18:B2", b"\x04\n\x13\x8a\x14"),
        BluetoothChange.ADVERTISEMENT,
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 1

    sensor = hass.states.get("sensor.test_device_8d18b2_energy")
    sensor_attr = sensor.attributes
    assert sensor.state == "1346.067"

    assert sensor_attr[ATTR_FRIENDLY_NAME] == "Test Device 8D18B2 Energy"
    assert sensor_attr[ATTR_UNIT_OF_MEASUREMENT] == "kWh"
    assert sensor_attr[ATTR_STATE_CLASS] == "total_increasing"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_bthome_power(hass):
    """Make sure that power sensors are correctly mapped."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="A4:C1:38:8D:18:B2",
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
        make_advertisement("A4:C1:38:8D:18:B2", b"\x04\x0b\x02\x1b\x00"),
        BluetoothChange.ADVERTISEMENT,
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 1

    sensor = hass.states.get("sensor.test_device_8d18b2_power")
    sensor_attr = sensor.attributes
    assert sensor.state == "69.14"

    assert sensor_attr[ATTR_FRIENDLY_NAME] == "Test Device 8D18B2 Power"
    assert sensor_attr[ATTR_UNIT_OF_MEASUREMENT] == "W"
    assert sensor_attr[ATTR_STATE_CLASS] == "measurement"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_bthome_voltage(hass):
    """Make sure that voltage sensors are correctly mapped."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="A4:C1:38:8D:18:B2",
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
        make_advertisement("A4:C1:38:8D:18:B2", b"\x03\x0c\x02\x0c"),
        BluetoothChange.ADVERTISEMENT,
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 1

    sensor = hass.states.get("sensor.test_device_8d18b2_voltage")
    sensor_attr = sensor.attributes
    assert sensor.state == "3.074"

    assert sensor_attr[ATTR_FRIENDLY_NAME] == "Test Device 8D18B2 Voltage"
    assert sensor_attr[ATTR_UNIT_OF_MEASUREMENT] == "V"
    assert sensor_attr[ATTR_STATE_CLASS] == "measurement"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_bthome_pm(hass):
    """Make sure that PM2.5 and PM10 sensors are correctly mapped."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="A4:C1:38:8D:18:B2",
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
        make_advertisement("A4:C1:38:8D:18:B2", b"\x03\r\x12\x0c\x03\x0e\x02\x1c"),
        BluetoothChange.ADVERTISEMENT,
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 2

    sensor = hass.states.get("sensor.test_device_8d18b2_pm10")
    sensor_attr = sensor.attributes
    assert sensor.state == "7170"

    assert sensor_attr[ATTR_FRIENDLY_NAME] == "Test Device 8D18B2 Pm10"
    assert sensor_attr[ATTR_UNIT_OF_MEASUREMENT] == "µg/m³"
    assert sensor_attr[ATTR_STATE_CLASS] == "measurement"

    sensor = hass.states.get("sensor.test_device_8d18b2_pm25")
    sensor_attr = sensor.attributes
    assert sensor.state == "3090"

    assert sensor_attr[ATTR_FRIENDLY_NAME] == "Test Device 8D18B2 Pm25"
    assert sensor_attr[ATTR_UNIT_OF_MEASUREMENT] == "µg/m³"
    assert sensor_attr[ATTR_STATE_CLASS] == "measurement"
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_bthome_c02(hass):
    """Make sure that CO2 sensors are correctly mapped."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="A4:C1:38:8D:18:B2",
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
        make_advertisement("A4:C1:38:8D:18:B2", b"\x03\x12\xe2\x04"),
        BluetoothChange.ADVERTISEMENT,
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 1

    sensor = hass.states.get("sensor.test_device_8d18b2_carbon_dioxide")
    sensor_attr = sensor.attributes
    assert sensor.state == "1250"

    assert sensor_attr[ATTR_FRIENDLY_NAME] == "Test Device 8D18B2 Carbon Dioxide"
    assert sensor_attr[ATTR_UNIT_OF_MEASUREMENT] == "ppm"
    assert sensor_attr[ATTR_STATE_CLASS] == "measurement"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_bthome_voc(hass):
    """Make sure that VOC sensors are correctly mapped."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="A4:C1:38:8D:18:B2",
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
        make_advertisement("A4:C1:38:8D:18:B2", b"\x03\x133\x01"),
        BluetoothChange.ADVERTISEMENT,
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 1

    sensor = hass.states.get("sensor.test_device_8d18b2_volatile_organic_compounds")
    sensor_attr = sensor.attributes
    assert sensor.state == "307"

    assert (
        sensor_attr[ATTR_FRIENDLY_NAME]
        == "Test Device 8D18B2 Volatile Organic Compounds"
    )
    assert sensor_attr[ATTR_UNIT_OF_MEASUREMENT] == "µg/m³"
    assert sensor_attr[ATTR_STATE_CLASS] == "measurement"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_temperature_humidity_encrypted(hass):
    """This device has encrypion so we need to retrieve its bindkey from the configentry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="54:48:E6:8F:80:A5",
        data={"bindkey": "231d39c1d7cc1ab1aee224cd096db932"},
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
        make_encrypted_advertisement(
            "54:48:E6:8F:80:A5",
            b'\xfb\xa45\xe4\xd3\xc3\x12\xfb\x00\x11"3W\xd9\n\x99',
        ),
        BluetoothChange.ADVERTISEMENT,
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 2

    temp_sensor = hass.states.get("sensor.test_device_8f80a5_temperature")
    temp_sensor_attribtes = temp_sensor.attributes
    assert temp_sensor.state == "25.06"
    assert temp_sensor_attribtes[ATTR_FRIENDLY_NAME] == "Test Device 8F80A5 Temperature"
    assert temp_sensor_attribtes[ATTR_UNIT_OF_MEASUREMENT] == "°C"
    assert temp_sensor_attribtes[ATTR_STATE_CLASS] == "measurement"

    humi_sensor = hass.states.get("sensor.test_device_8f80a5_humidity")
    humi_sensor_attribtes = humi_sensor.attributes
    assert humi_sensor.state == "50.55"
    assert humi_sensor_attribtes[ATTR_FRIENDLY_NAME] == "Test Device 8F80A5 Humidity"
    assert humi_sensor_attribtes[ATTR_UNIT_OF_MEASUREMENT] == "%"
    assert humi_sensor_attribtes[ATTR_STATE_CLASS] == "measurement"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

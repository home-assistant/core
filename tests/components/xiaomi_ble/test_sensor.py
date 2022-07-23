"""Test the Xiaomi config flow."""

from unittest.mock import patch

from homeassistant.components.bluetooth import BluetoothChange
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

    def _async_register_callback(_hass, _callback, _matcher):
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

    temp_sensor = hass.states.get("sensor.mmc_t201_1_temperature")
    temp_sensor_attribtes = temp_sensor.attributes
    assert temp_sensor.state == "36.8719980616822"
    assert temp_sensor_attribtes[ATTR_FRIENDLY_NAME] == "MMC_T201_1 Temperature"
    assert temp_sensor_attribtes[ATTR_UNIT_OF_MEASUREMENT] == "°C"
    assert temp_sensor_attribtes[ATTR_STATE_CLASS] == "measurement"

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

    def _async_register_callback(_hass, _callback, _matcher):
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
    assert len(hass.states.async_all()) == 4

    illum_sensor = hass.states.get("sensor.test_device_illuminance")
    illum_sensor_attr = illum_sensor.attributes
    assert illum_sensor.state == "0"
    assert illum_sensor_attr[ATTR_FRIENDLY_NAME] == "Test Device Illuminance"
    assert illum_sensor_attr[ATTR_UNIT_OF_MEASUREMENT] == "lx"
    assert illum_sensor_attr[ATTR_STATE_CLASS] == "measurement"

    cond_sensor = hass.states.get("sensor.test_device_conductivity")
    cond_sensor_attribtes = cond_sensor.attributes
    assert cond_sensor.state == "599"
    assert cond_sensor_attribtes[ATTR_FRIENDLY_NAME] == "Test Device Conductivity"
    assert cond_sensor_attribtes[ATTR_UNIT_OF_MEASUREMENT] == "µS/cm"
    assert cond_sensor_attribtes[ATTR_STATE_CLASS] == "measurement"

    moist_sensor = hass.states.get("sensor.test_device_moisture")
    moist_sensor_attribtes = moist_sensor.attributes
    assert moist_sensor.state == "64"
    assert moist_sensor_attribtes[ATTR_FRIENDLY_NAME] == "Test Device Moisture"
    assert moist_sensor_attribtes[ATTR_UNIT_OF_MEASUREMENT] == "%"
    assert moist_sensor_attribtes[ATTR_STATE_CLASS] == "measurement"

    temp_sensor = hass.states.get("sensor.test_device_temperature")
    temp_sensor_attribtes = temp_sensor.attributes
    assert temp_sensor.state == "24.4"
    assert temp_sensor_attribtes[ATTR_FRIENDLY_NAME] == "Test Device Temperature"
    assert temp_sensor_attribtes[ATTR_UNIT_OF_MEASUREMENT] == "°C"
    assert temp_sensor_attribtes[ATTR_STATE_CLASS] == "measurement"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

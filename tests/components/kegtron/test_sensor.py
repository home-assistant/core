"""Test the Kegtron sensors."""

from unittest.mock import patch

from homeassistant.components.bluetooth import BluetoothChange
from homeassistant.components.kegtron.const import DOMAIN
from homeassistant.components.sensor import ATTR_STATE_CLASS
from homeassistant.const import ATTR_FRIENDLY_NAME, ATTR_UNIT_OF_MEASUREMENT

from . import KEGTRON_KT100_SERVICE_INFO

from tests.common import MockConfigEntry


async def test_sensors(hass):
    """Test setting up creates the sensors for Kegtron KT-100."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="D0:CF:5E:5C:9B:75",
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

    assert len(hass.states.async_all("sensor")) == 0
    saved_callback(KEGTRON_KT100_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
    await hass.async_block_till_done()
    assert len(hass.states.async_all("sensor")) == 7

    keg_size_sensor = hass.states.get("sensor.kegtron_kt_100_9b75_keg_size")
    keg_size_sensor_attrs = keg_size_sensor.attributes
    assert keg_size_sensor.state == "18.927"
    assert keg_size_sensor_attrs[ATTR_FRIENDLY_NAME] == "Kegtron KT-100 9B75 Keg Size"
    assert keg_size_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "L"
    assert keg_size_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    keg_type_sensor = hass.states.get("sensor.kegtron_kt_100_9b75_keg_type")
    keg_type_sensor_attrs = keg_type_sensor.attributes
    assert keg_type_sensor.state == "Corny (5.0 gal)"
    assert keg_type_sensor_attrs[ATTR_FRIENDLY_NAME] == "Kegtron KT-100 9B75 Keg Type"

    volume_start_sensor = hass.states.get("sensor.kegtron_kt_100_9b75_volume_start")
    volume_start_sensor_attrs = volume_start_sensor.attributes
    assert volume_start_sensor.state == "5.0"
    assert (
        volume_start_sensor_attrs[ATTR_FRIENDLY_NAME]
        == "Kegtron KT-100 9B75 Volume Start"
    )
    assert volume_start_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "L"
    assert volume_start_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    port_count_sensor = hass.states.get("sensor.kegtron_kt_100_9b75_port_count")
    port_count_sensor_attrs = port_count_sensor.attributes
    assert port_count_sensor.state == "Single port device"
    assert (
        port_count_sensor_attrs[ATTR_FRIENDLY_NAME] == "Kegtron KT-100 9B75 Port Count"
    )

    port_index_sensor = hass.states.get("sensor.kegtron_kt_100_9b75_port_index")
    port_index_sensor_attrs = port_index_sensor.attributes
    assert port_index_sensor.state == "1"
    assert (
        port_index_sensor_attrs[ATTR_FRIENDLY_NAME] == "Kegtron KT-100 9B75 Port Index"
    )

    port_state_sensor = hass.states.get("sensor.kegtron_kt_100_9b75_port_state")
    port_state_sensor_attrs = port_state_sensor.attributes
    assert port_state_sensor.state == "Configured"
    assert (
        port_state_sensor_attrs[ATTR_FRIENDLY_NAME] == "Kegtron KT-100 9B75 Port State"
    )

    volume_dispensed_port_1_sensor = hass.states.get(
        "sensor.kegtron_kt_100_9b75_volume_dispensed_single_port"
    )
    volume_dispensed_port_1_attrs = volume_dispensed_port_1_sensor.attributes
    assert volume_dispensed_port_1_sensor.state == "0.738"
    assert (
        volume_dispensed_port_1_attrs[ATTR_FRIENDLY_NAME]
        == "Kegtron KT-100 9B75 Volume Dispensed Single Port"
    )
    assert volume_dispensed_port_1_attrs[ATTR_UNIT_OF_MEASUREMENT] == "L"
    assert volume_dispensed_port_1_attrs[ATTR_STATE_CLASS] == "total"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

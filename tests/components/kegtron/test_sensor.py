"""Test the Kegtron sensors."""
from homeassistant.components.kegtron.const import DOMAIN
from homeassistant.components.sensor import ATTR_STATE_CLASS
from homeassistant.const import ATTR_FRIENDLY_NAME, ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant

from . import (
    KEGTRON_KT100_SERVICE_INFO,
    KEGTRON_KT200_PORT_1_SERVICE_INFO,
    KEGTRON_KT200_PORT_2_SERVICE_INFO,
)

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info


async def test_sensors_kt100(hass: HomeAssistant) -> None:
    """Test setting up creates the sensors for Kegtron KT-100."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="D0:CF:5E:5C:9B:75",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all("sensor")) == 0

    inject_bluetooth_service_info(
        hass,
        KEGTRON_KT100_SERVICE_INFO,
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all("sensor")) == 7

    port_count_sensor = hass.states.get("sensor.kegtron_kt_100_9b75_port_count")
    port_count_sensor_attrs = port_count_sensor.attributes
    assert port_count_sensor.state == "Single port device"
    assert (
        port_count_sensor_attrs[ATTR_FRIENDLY_NAME] == "Kegtron KT-100 9B75 Port Count"
    )

    keg_size_sensor = hass.states.get("sensor.kegtron_kt_100_9b75_keg_size")
    keg_size_sensor_attrs = keg_size_sensor.attributes
    assert keg_size_sensor.state == "18.927"
    assert keg_size_sensor_attrs[ATTR_FRIENDLY_NAME] == "Kegtron KT-100 9B75 Keg Size"
    assert keg_size_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "L"

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

    volume_dispensed_sensor = hass.states.get(
        "sensor.kegtron_kt_100_9b75_volume_dispensed"
    )
    volume_dispensed_attrs = volume_dispensed_sensor.attributes
    assert volume_dispensed_sensor.state == "0.738"
    assert (
        volume_dispensed_attrs[ATTR_FRIENDLY_NAME]
        == "Kegtron KT-100 9B75 Volume Dispensed"
    )
    assert volume_dispensed_attrs[ATTR_UNIT_OF_MEASUREMENT] == "L"
    assert volume_dispensed_attrs[ATTR_STATE_CLASS] == "total"

    port_state_sensor = hass.states.get("sensor.kegtron_kt_100_9b75_port_state")
    port_state_sensor_attrs = port_state_sensor.attributes
    assert port_state_sensor.state == "Configured"
    assert (
        port_state_sensor_attrs[ATTR_FRIENDLY_NAME] == "Kegtron KT-100 9B75 Port State"
    )

    port_name_sensor = hass.states.get("sensor.kegtron_kt_100_9b75_port_name")
    port_name_attrs = port_name_sensor.attributes
    assert port_name_sensor.state == "Single Port"
    assert port_name_attrs[ATTR_FRIENDLY_NAME] == "Kegtron KT-100 9B75 Port Name"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_sensors_kt200(hass: HomeAssistant) -> None:
    """Test setting up creates the sensors for Kegtron KT-200."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="D0:CF:5E:5C:9B:75",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all("sensor")) == 0

    # Kegtron KT-200 has two ports that are reported separately, start with port 2
    inject_bluetooth_service_info(
        hass,
        KEGTRON_KT200_PORT_2_SERVICE_INFO,
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all("sensor")) == 7

    port_count_sensor = hass.states.get("sensor.kegtron_kt_200_9b75_port_count")
    port_count_sensor_attrs = port_count_sensor.attributes
    assert port_count_sensor.state == "Dual port device"
    assert (
        port_count_sensor_attrs[ATTR_FRIENDLY_NAME] == "Kegtron KT-200 9B75 Port Count"
    )

    keg_size_sensor = hass.states.get("sensor.kegtron_kt_200_9b75_keg_size_port_2")
    keg_size_sensor_attrs = keg_size_sensor.attributes
    assert keg_size_sensor.state == "58.93"
    assert (
        keg_size_sensor_attrs[ATTR_FRIENDLY_NAME]
        == "Kegtron KT-200 9B75 Keg Size Port 2"
    )
    assert keg_size_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "L"

    keg_type_sensor = hass.states.get("sensor.kegtron_kt_200_9b75_keg_type_port_2")
    keg_type_sensor_attrs = keg_type_sensor.attributes
    assert keg_type_sensor.state == "Other (58.93 L)"
    assert (
        keg_type_sensor_attrs[ATTR_FRIENDLY_NAME]
        == "Kegtron KT-200 9B75 Keg Type Port 2"
    )

    volume_start_sensor = hass.states.get(
        "sensor.kegtron_kt_200_9b75_volume_start_port_2"
    )
    volume_start_sensor_attrs = volume_start_sensor.attributes
    assert volume_start_sensor.state == "15.0"
    assert (
        volume_start_sensor_attrs[ATTR_FRIENDLY_NAME]
        == "Kegtron KT-200 9B75 Volume Start Port 2"
    )
    assert volume_start_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "L"

    volume_dispensed_sensor = hass.states.get(
        "sensor.kegtron_kt_200_9b75_volume_dispensed_port_2"
    )
    volume_dispensed_attrs = volume_dispensed_sensor.attributes
    assert volume_dispensed_sensor.state == "0.738"
    assert (
        volume_dispensed_attrs[ATTR_FRIENDLY_NAME]
        == "Kegtron KT-200 9B75 Volume Dispensed Port 2"
    )
    assert volume_dispensed_attrs[ATTR_UNIT_OF_MEASUREMENT] == "L"
    assert volume_dispensed_attrs[ATTR_STATE_CLASS] == "total"

    port_state_sensor = hass.states.get("sensor.kegtron_kt_200_9b75_port_state_port_2")
    port_state_sensor_attrs = port_state_sensor.attributes
    assert port_state_sensor.state == "Configured"
    assert (
        port_state_sensor_attrs[ATTR_FRIENDLY_NAME]
        == "Kegtron KT-200 9B75 Port State Port 2"
    )

    port_name_sensor = hass.states.get("sensor.kegtron_kt_200_9b75_port_name_port_2")
    port_name_attrs = port_name_sensor.attributes
    assert port_name_sensor.state == "2nd Port"
    assert port_name_attrs[ATTR_FRIENDLY_NAME] == "Kegtron KT-200 9B75 Port Name Port 2"

    # Followed by a BLE advertisement of port 1
    inject_bluetooth_service_info(
        hass,
        KEGTRON_KT200_PORT_1_SERVICE_INFO,
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all("sensor")) == 13

    port_count_sensor = hass.states.get("sensor.kegtron_kt_200_9b75_port_count")
    port_count_sensor_attrs = port_count_sensor.attributes
    assert port_count_sensor.state == "Dual port device"
    assert (
        port_count_sensor_attrs[ATTR_FRIENDLY_NAME] == "Kegtron KT-200 9B75 Port Count"
    )

    keg_size_sensor = hass.states.get("sensor.kegtron_kt_200_9b75_keg_size_port_1")
    keg_size_sensor_attrs = keg_size_sensor.attributes
    assert keg_size_sensor.state == "9.04"
    assert (
        keg_size_sensor_attrs[ATTR_FRIENDLY_NAME]
        == "Kegtron KT-200 9B75 Keg Size Port 1"
    )
    assert keg_size_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "L"

    keg_type_sensor = hass.states.get("sensor.kegtron_kt_200_9b75_keg_type_port_1")
    keg_type_sensor_attrs = keg_type_sensor.attributes
    assert keg_type_sensor.state == "Other (9.04 L)"
    assert (
        keg_type_sensor_attrs[ATTR_FRIENDLY_NAME]
        == "Kegtron KT-200 9B75 Keg Type Port 1"
    )

    volume_start_sensor = hass.states.get(
        "sensor.kegtron_kt_200_9b75_volume_start_port_1"
    )
    volume_start_sensor_attrs = volume_start_sensor.attributes
    assert volume_start_sensor.state == "50.0"
    assert (
        volume_start_sensor_attrs[ATTR_FRIENDLY_NAME]
        == "Kegtron KT-200 9B75 Volume Start Port 1"
    )
    assert volume_start_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "L"

    volume_dispensed_sensor = hass.states.get(
        "sensor.kegtron_kt_200_9b75_volume_dispensed_port_1"
    )
    volume_dispensed_attrs = volume_dispensed_sensor.attributes
    assert volume_dispensed_sensor.state == "13.0"
    assert (
        volume_dispensed_attrs[ATTR_FRIENDLY_NAME]
        == "Kegtron KT-200 9B75 Volume Dispensed Port 1"
    )
    assert volume_dispensed_attrs[ATTR_UNIT_OF_MEASUREMENT] == "L"
    assert volume_dispensed_attrs[ATTR_STATE_CLASS] == "total"

    port_state_sensor = hass.states.get("sensor.kegtron_kt_200_9b75_port_state_port_1")
    port_state_sensor_attrs = port_state_sensor.attributes
    assert port_state_sensor.state == "Configured"
    assert (
        port_state_sensor_attrs[ATTR_FRIENDLY_NAME]
        == "Kegtron KT-200 9B75 Port State Port 1"
    )

    port_name_sensor = hass.states.get("sensor.kegtron_kt_200_9b75_port_name_port_1")
    port_name_attrs = port_name_sensor.attributes
    assert port_name_sensor.state == "Port 1"
    assert port_name_attrs[ATTR_FRIENDLY_NAME] == "Kegtron KT-200 9B75 Port Name Port 1"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

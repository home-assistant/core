"""Test the INKBIRD config flow."""

from unittest.mock import patch

from inkbird_ble import (
    DeviceKey,
    SensorDescription,
    SensorDeviceInfo,
    SensorUpdate,
    SensorValue,
    Units,
)
from sensor_state_data import SensorDeviceClass

from homeassistant.components.inkbird.const import CONF_DEVICE_TYPE, DOMAIN
from homeassistant.components.inkbird.coordinator import FALLBACK_POLL_INTERVAL
from homeassistant.components.sensor import ATTR_STATE_CLASS
from homeassistant.const import ATTR_FRIENDLY_NAME, ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import (
    SPS_PASSIVE_SERVICE_INFO,
    SPS_SERVICE_INFO,
    SPS_WITH_CORRUPT_NAME_SERVICE_INFO,
)

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.bluetooth import inject_bluetooth_service_info


def _make_sensor_update(humidity: float) -> SensorUpdate:
    return SensorUpdate(
        title=None,
        devices={
            None: SensorDeviceInfo(
                name="IBS-TH EEFF",
                model="IBS-TH",
                manufacturer="INKBIRD",
                sw_version=None,
                hw_version=None,
            )
        },
        entity_descriptions={
            DeviceKey(key="humidity", device_id=None): SensorDescription(
                device_key=DeviceKey(key="humidity", device_id=None),
                device_class=SensorDeviceClass.HUMIDITY,
                native_unit_of_measurement=Units.PERCENTAGE,
            ),
        },
        entity_values={
            DeviceKey(key="humidity", device_id=None): SensorValue(
                device_key=DeviceKey(key="humidity", device_id=None),
                name="Humidity",
                native_value=humidity,
            ),
        },
    )


async def test_sensors(hass: HomeAssistant) -> None:
    """Test setting up creates the sensors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="61DE521B-F0BF-9F44-64D4-75BBE1738105",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    inject_bluetooth_service_info(hass, SPS_SERVICE_INFO)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 3

    temp_sensor = hass.states.get("sensor.ibs_th_8105_battery")
    temp_sensor_attribtes = temp_sensor.attributes
    assert temp_sensor.state == "87"
    assert temp_sensor_attribtes[ATTR_FRIENDLY_NAME] == "IBS-TH 8105 Battery"
    assert temp_sensor_attribtes[ATTR_UNIT_OF_MEASUREMENT] == "%"
    assert temp_sensor_attribtes[ATTR_STATE_CLASS] == "measurement"

    # Make sure we remember the device type
    # in case the name is corrupted later
    assert entry.data[CONF_DEVICE_TYPE] == "IBS-TH"
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_device_with_corrupt_name(hass: HomeAssistant) -> None:
    """Test setting up a known device type with a corrupt name."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="AA:BB:CC:DD:EE:FF",
        data={CONF_DEVICE_TYPE: "IBS-TH"},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    inject_bluetooth_service_info(hass, SPS_WITH_CORRUPT_NAME_SERVICE_INFO)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 3

    temp_sensor = hass.states.get("sensor.ibs_th_eeff_battery")
    temp_sensor_attribtes = temp_sensor.attributes
    assert temp_sensor.state == "87"
    assert temp_sensor_attribtes[ATTR_FRIENDLY_NAME] == "IBS-TH EEFF Battery"
    assert temp_sensor_attribtes[ATTR_UNIT_OF_MEASUREMENT] == "%"
    assert temp_sensor_attribtes[ATTR_STATE_CLASS] == "measurement"

    assert entry.data[CONF_DEVICE_TYPE] == "IBS-TH"
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_polling_sensor(hass: HomeAssistant) -> None:
    """Test setting up a device that needs polling."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="AA:BB:CC:DD:EE:FF",
        data={CONF_DEVICE_TYPE: "IBS-TH"},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0

    with patch(
        "homeassistant.components.inkbird.INKBIRDBluetoothDeviceData.async_poll",
        return_value=_make_sensor_update(10.24),
    ):
        inject_bluetooth_service_info(hass, SPS_PASSIVE_SERVICE_INFO)
        await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 1

    temp_sensor = hass.states.get("sensor.ibs_th_eeff_humidity")
    temp_sensor_attribtes = temp_sensor.attributes
    assert temp_sensor.state == "10.24"
    assert temp_sensor_attribtes[ATTR_FRIENDLY_NAME] == "IBS-TH EEFF Humidity"
    assert temp_sensor_attribtes[ATTR_UNIT_OF_MEASUREMENT] == "%"
    assert temp_sensor_attribtes[ATTR_STATE_CLASS] == "measurement"

    assert entry.data[CONF_DEVICE_TYPE] == "IBS-TH"

    with patch(
        "homeassistant.components.inkbird.INKBIRDBluetoothDeviceData.async_poll",
        return_value=_make_sensor_update(20.24),
    ):
        async_fire_time_changed(hass, dt_util.utcnow() + FALLBACK_POLL_INTERVAL)
        inject_bluetooth_service_info(hass, SPS_PASSIVE_SERVICE_INFO)
        await hass.async_block_till_done()

    temp_sensor = hass.states.get("sensor.ibs_th_eeff_humidity")
    temp_sensor_attribtes = temp_sensor.attributes
    assert temp_sensor.state == "20.24"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

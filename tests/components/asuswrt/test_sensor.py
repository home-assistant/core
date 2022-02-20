"""Tests for the AsusWrt sensor."""
from datetime import timedelta
from unittest.mock import AsyncMock, Mock, patch

from aioasuswrt.asuswrt import Device
import pytest

from homeassistant.components import device_tracker, sensor
from homeassistant.components.asuswrt.const import DOMAIN
from homeassistant.components.asuswrt.sensor import DEFAULT_PREFIX
from homeassistant.components.device_tracker.const import CONF_CONSIDER_HOME
from homeassistant.const import (
    CONF_HOST,
    CONF_MODE,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_USERNAME,
    STATE_HOME,
    STATE_NOT_HOME,
)
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import slugify
from homeassistant.util.dt import utcnow

from tests.common import MockConfigEntry, async_fire_time_changed

HOST = "myrouter.asuswrt.com"
IP_ADDRESS = "192.168.1.1"

CONFIG_DATA = {
    CONF_HOST: HOST,
    CONF_PORT: 22,
    CONF_PROTOCOL: "ssh",
    CONF_USERNAME: "user",
    CONF_PASSWORD: "pwd",
    CONF_MODE: "router",
}

MOCK_BYTES_TOTAL = [60000000000, 50000000000]
MOCK_CURRENT_TRANSFER_RATES = [20000000, 10000000]
MOCK_LOAD_AVG = [1.1, 1.2, 1.3]
MOCK_TEMPERATURES = {"2.4GHz": 40, "5.0GHz": 0, "CPU": 71.2}
MOCK_MAC_1 = "a1:b1:c1:d1:e1:f1"
MOCK_MAC_2 = "a2:b2:c2:d2:e2:f2"
MOCK_MAC_3 = "a3:b3:c3:d3:e3:f3"

SENSOR_NAMES = [
    "Devices Connected",
    "Download Speed",
    "Download",
    "Upload Speed",
    "Upload",
    "Load Avg (1m)",
    "Load Avg (5m)",
    "Load Avg (15m)",
    "2.4GHz Temperature",
    "5GHz Temperature",
    "CPU Temperature",
]


@pytest.fixture(name="mock_devices")
def mock_devices_fixture():
    """Mock a list of devices."""
    return {
        MOCK_MAC_1: Device(MOCK_MAC_1, "192.168.1.2", "Test"),
        MOCK_MAC_2: Device(MOCK_MAC_2, "192.168.1.3", "TestTwo"),
    }


@pytest.fixture(name="mock_available_temps")
def mock_available_temps_list():
    """Mock a list of available temperature sensors."""

    # Only length of 3 booleans is valid. First checking the exception handling.
    return [True, False]


@pytest.fixture(name="create_device_registry_devices")
def create_device_registry_devices_fixture(hass):
    """Create device registry devices so the device tracker entities are enabled."""
    dev_reg = dr.async_get(hass)
    config_entry = MockConfigEntry(domain="something_else")

    for idx, device in enumerate(
        (
            MOCK_MAC_1,
            MOCK_MAC_2,
            MOCK_MAC_3,
        )
    ):
        dev_reg.async_get_or_create(
            name=f"Device {idx}",
            config_entry_id=config_entry.entry_id,
            connections={(dr.CONNECTION_NETWORK_MAC, device)},
        )


@pytest.fixture(name="connect")
def mock_controller_connect(mock_devices, mock_available_temps):
    """Mock a successful connection."""
    with patch("homeassistant.components.asuswrt.router.AsusWrt") as service_mock:
        service_mock.return_value.connection.async_connect = AsyncMock()
        service_mock.return_value.is_connected = True
        service_mock.return_value.connection.disconnect = Mock()
        service_mock.return_value.async_get_nvram = AsyncMock(
            return_value={
                "model": "abcd",
                "firmver": "efg",
                "buildno": "123",
            }
        )
        service_mock.return_value.async_get_connected_devices = AsyncMock(
            return_value=mock_devices
        )
        service_mock.return_value.async_get_bytes_total = AsyncMock(
            return_value=MOCK_BYTES_TOTAL
        )
        service_mock.return_value.async_get_current_transfer_rates = AsyncMock(
            return_value=MOCK_CURRENT_TRANSFER_RATES
        )
        service_mock.return_value.async_get_loadavg = AsyncMock(
            return_value=MOCK_LOAD_AVG
        )
        service_mock.return_value.async_get_temperature = AsyncMock(
            return_value=MOCK_TEMPERATURES
        )
        service_mock.return_value.async_find_temperature_commands = AsyncMock(
            return_value=mock_available_temps
        )
        yield service_mock


async def test_sensors(
    hass,
    connect,
    mock_devices,
    mock_available_temps,
    create_device_registry_devices,
):
    """Test creating an AsusWRT sensor."""
    entity_reg = er.async_get(hass)

    # init config entry
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_DATA,
        options={CONF_CONSIDER_HOME: 60},
    )

    # init variable
    unique_id = DOMAIN
    obj_prefix = slugify(DEFAULT_PREFIX)
    sensor_prefix = f"{sensor.DOMAIN}.{obj_prefix}"

    # Pre-enable the status sensor
    for sensor_name in SENSOR_NAMES:
        sensor_id = slugify(sensor_name)
        entity_reg.async_get_or_create(
            sensor.DOMAIN,
            DOMAIN,
            f"{unique_id} {DEFAULT_PREFIX} {sensor_name}",
            suggested_object_id=f"{obj_prefix}_{sensor_id}",
            disabled_by=None,
        )

    config_entry.add_to_hass(hass)

    # initial devices setup
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done()

    assert hass.states.get(f"{device_tracker.DOMAIN}.test").state == STATE_HOME
    assert hass.states.get(f"{device_tracker.DOMAIN}.testtwo").state == STATE_HOME
    assert hass.states.get(f"{sensor_prefix}_download_speed").state == "160.0"
    assert hass.states.get(f"{sensor_prefix}_download").state == "60.0"
    assert hass.states.get(f"{sensor_prefix}_upload_speed").state == "80.0"
    assert hass.states.get(f"{sensor_prefix}_upload").state == "50.0"
    assert hass.states.get(f"{sensor_prefix}_load_avg_1m").state == "1.1"
    assert hass.states.get(f"{sensor_prefix}_load_avg_5m").state == "1.2"
    assert hass.states.get(f"{sensor_prefix}_load_avg_15m").state == "1.3"
    assert hass.states.get(f"{sensor_prefix}_devices_connected").state == "2"

    # assert temperature availability exception is handled correctly
    assert not hass.states.get(f"{sensor_prefix}_2_4ghz_temperature")
    assert not hass.states.get(f"{sensor_prefix}_5ghz_temperature")
    assert not hass.states.get(f"{sensor_prefix}_cpu_temperature")

    # add one device and remove another
    mock_devices.pop(MOCK_MAC_1)
    mock_devices[MOCK_MAC_3] = Device(MOCK_MAC_3, "192.168.1.4", "TestThree")

    async_fire_time_changed(hass, utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done()

    # consider home option set, all devices still home
    assert hass.states.get(f"{device_tracker.DOMAIN}.test").state == STATE_HOME
    assert hass.states.get(f"{device_tracker.DOMAIN}.testtwo").state == STATE_HOME
    assert hass.states.get(f"{device_tracker.DOMAIN}.testthree").state == STATE_HOME
    assert hass.states.get(f"{sensor_prefix}_devices_connected").state == "2"

    hass.config_entries.async_update_entry(
        config_entry, options={CONF_CONSIDER_HOME: 0}
    )
    await hass.async_block_till_done()
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done()

    # consider home option not set, device "test" not home
    assert hass.states.get(f"{device_tracker.DOMAIN}.test").state == STATE_NOT_HOME

    # checking temperature sensors without exceptions
    mock_available_temps.append(True)
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done()

    assert hass.states.get(f"{sensor_prefix}_load_avg_15m").state == "1.3"
    assert hass.states.get(f"{sensor_prefix}_2_4ghz_temperature").state == "40.0"
    assert not hass.states.get(f"{sensor_prefix}_5ghz_temperature")
    assert hass.states.get(f"{sensor_prefix}_cpu_temperature").state == "71.2"

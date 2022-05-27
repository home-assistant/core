"""Tests for the AsusWrt sensor."""
from datetime import timedelta
from unittest.mock import AsyncMock, Mock, patch

from aioasuswrt.asuswrt import Device
import pytest

from homeassistant.components import device_tracker, sensor
from homeassistant.components.asuswrt.const import CONF_INTERFACE, DOMAIN
from homeassistant.components.asuswrt.router import DEFAULT_NAME
from homeassistant.components.device_tracker.const import CONF_CONSIDER_HOME
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_HOST,
    CONF_MODE,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_USERNAME,
    STATE_HOME,
    STATE_NOT_HOME,
    STATE_UNAVAILABLE,
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
    CONF_PROTOCOL: "telnet",
    CONF_USERNAME: "user",
    CONF_PASSWORD: "pwd",
    CONF_MODE: "router",
}

MAC_ADDR = "a1:b2:c3:d4:e5:f6"

MOCK_BYTES_TOTAL = [60000000000, 50000000000]
MOCK_CURRENT_TRANSFER_RATES = [20000000, 10000000]
MOCK_LOAD_AVG = [1.1, 1.2, 1.3]
MOCK_TEMPERATURES = {"2.4GHz": 40, "5.0GHz": 0, "CPU": 71.2}
MOCK_MAC_1 = "A1:B1:C1:D1:E1:F1"
MOCK_MAC_2 = "A2:B2:C2:D2:E2:F2"
MOCK_MAC_3 = "A3:B3:C3:D3:E3:F3"
MOCK_MAC_4 = "A4:B4:C4:D4:E4:F4"

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
    """Create device registry devices so the device tracker entities are enabled when added."""
    dev_reg = dr.async_get(hass)
    config_entry = MockConfigEntry(domain="something_else")

    for idx, device in enumerate(
        (
            MOCK_MAC_3,
            MOCK_MAC_4,
        )
    ):
        dev_reg.async_get_or_create(
            name=f"Device {idx}",
            config_entry_id=config_entry.entry_id,
            connections={(dr.CONNECTION_NETWORK_MAC, dr.format_mac(device))},
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


@pytest.fixture(name="connect_sens_fail")
def mock_controller_connect_sens_fail():
    """Mock a successful connection with sensor fail."""
    with patch("homeassistant.components.asuswrt.router.AsusWrt") as service_mock:
        service_mock.return_value.connection.async_connect = AsyncMock()
        service_mock.return_value.is_connected = True
        service_mock.return_value.connection.disconnect = Mock()
        service_mock.return_value.async_get_nvram = AsyncMock(side_effect=OSError)
        service_mock.return_value.async_get_connected_devices = AsyncMock(
            side_effect=OSError
        )
        service_mock.return_value.async_get_bytes_total = AsyncMock(side_effect=OSError)
        service_mock.return_value.async_get_current_transfer_rates = AsyncMock(
            side_effect=OSError
        )
        service_mock.return_value.async_get_loadavg = AsyncMock(side_effect=OSError)
        service_mock.return_value.async_get_temperature = AsyncMock(side_effect=OSError)
        service_mock.return_value.async_find_temperature_commands = AsyncMock(
            return_value=[True, True, True]
        )
        yield service_mock


def _setup_entry(hass, unique_id=None):
    """Create mock config entry."""
    entity_reg = er.async_get(hass)

    # init config entry
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_DATA,
        options={CONF_CONSIDER_HOME: 60},
        unique_id=unique_id,
    )

    # init variable
    obj_prefix = slugify(HOST if unique_id else DEFAULT_NAME)
    sensor_prefix = f"{sensor.DOMAIN}.{obj_prefix}"

    # Pre-enable the status sensor
    for sensor_name in SENSOR_NAMES:
        sensor_id = slugify(sensor_name)
        entity_reg.async_get_or_create(
            sensor.DOMAIN,
            DOMAIN,
            f"{DOMAIN} {unique_id or DEFAULT_NAME} {sensor_name}",
            suggested_object_id=f"{obj_prefix}_{sensor_id}",
            disabled_by=None,
        )

    # Create the first device tracker to test mac conversion
    for mac, name in {
        MOCK_MAC_1: "test",
        dr.format_mac(MOCK_MAC_2): "testtwo",
        MOCK_MAC_2: "testremove",
    }.items():
        entity_reg.async_get_or_create(
            device_tracker.DOMAIN,
            DOMAIN,
            mac,
            suggested_object_id=name,
            config_entry=config_entry,
            disabled_by=None,
        )

    return config_entry, sensor_prefix


@pytest.mark.parametrize(
    "entry_unique_id",
    [None, MAC_ADDR],
)
async def test_sensors(
    hass,
    connect,
    mock_devices,
    mock_available_temps,
    create_device_registry_devices,
    entry_unique_id,
):
    """Test creating an AsusWRT sensor."""
    config_entry, sensor_prefix = _setup_entry(hass, entry_unique_id)
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

    # remove first track device
    mock_devices.pop(MOCK_MAC_1)

    async_fire_time_changed(hass, utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done()

    # consider home option set, all devices still home but only 1 device connected
    assert hass.states.get(f"{device_tracker.DOMAIN}.test").state == STATE_HOME
    assert hass.states.get(f"{device_tracker.DOMAIN}.testtwo").state == STATE_HOME
    assert hass.states.get(f"{sensor_prefix}_devices_connected").state == "1"

    # add 2 new device, one unnamed that should be ignored but counted
    mock_devices[MOCK_MAC_3] = Device(MOCK_MAC_3, "192.168.1.4", "TestThree")
    mock_devices[MOCK_MAC_4] = Device(MOCK_MAC_4, "192.168.1.5", None)

    # change consider home settings to have status not home of removed track device
    hass.config_entries.async_update_entry(
        config_entry, options={CONF_CONSIDER_HOME: 0}
    )
    await hass.async_block_till_done()
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done()

    # consider home option set to 0, device "test" not home
    assert hass.states.get(f"{device_tracker.DOMAIN}.test").state == STATE_NOT_HOME
    assert hass.states.get(f"{device_tracker.DOMAIN}.testtwo").state == STATE_HOME
    assert hass.states.get(f"{device_tracker.DOMAIN}.testthree").state == STATE_HOME
    assert hass.states.get(f"{sensor_prefix}_devices_connected").state == "3"

    # checking temperature sensors without exceptions
    mock_available_temps.append(True)
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(f"{sensor_prefix}_2_4ghz_temperature").state == "40.0"
    assert not hass.states.get(f"{sensor_prefix}_5ghz_temperature")
    assert hass.states.get(f"{sensor_prefix}_cpu_temperature").state == "71.2"
    assert hass.states.get(f"{sensor_prefix}_devices_connected").state == "3"

    # change an option that require integration reload
    hass.config_entries.async_update_entry(
        config_entry, options={CONF_CONSIDER_HOME: 60, CONF_INTERFACE: "eth1"}
    )
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get(f"{sensor_prefix}_devices_connected").state == "3"


@pytest.mark.parametrize(
    "side_effect",
    [OSError, None],
)
async def test_connect_fail(hass, side_effect):
    """Test AsusWRT connect fail."""

    # init config entry
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_DATA,
    )
    config_entry.add_to_hass(hass)

    with patch("homeassistant.components.asuswrt.router.AsusWrt") as asus_wrt:
        asus_wrt.return_value.connection.async_connect = AsyncMock(
            side_effect=side_effect
        )
        asus_wrt.return_value.is_connected = False

        # initial setup fail
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_sensors_polling_fails(
    hass,
    connect_sens_fail,
):
    """Test AsusWRT sensors are unavailable when polling fails."""
    config_entry, sensor_prefix = _setup_entry(hass)
    config_entry.add_to_hass(hass)

    # initial devices setup
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done()

    assert hass.states.get(f"{sensor_prefix}_download_speed").state == STATE_UNAVAILABLE
    assert hass.states.get(f"{sensor_prefix}_download").state == STATE_UNAVAILABLE
    assert hass.states.get(f"{sensor_prefix}_upload_speed").state == STATE_UNAVAILABLE
    assert hass.states.get(f"{sensor_prefix}_upload").state == STATE_UNAVAILABLE
    assert hass.states.get(f"{sensor_prefix}_load_avg_1m").state == STATE_UNAVAILABLE
    assert hass.states.get(f"{sensor_prefix}_load_avg_5m").state == STATE_UNAVAILABLE
    assert hass.states.get(f"{sensor_prefix}_load_avg_15m").state == STATE_UNAVAILABLE
    assert hass.states.get(f"{sensor_prefix}_devices_connected").state == "0"
    assert (
        hass.states.get(f"{sensor_prefix}_2_4ghz_temperature").state
        == STATE_UNAVAILABLE
    )
    assert (
        hass.states.get(f"{sensor_prefix}_5ghz_temperature").state == STATE_UNAVAILABLE
    )
    assert (
        hass.states.get(f"{sensor_prefix}_cpu_temperature").state == STATE_UNAVAILABLE
    )

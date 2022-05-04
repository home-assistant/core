"""Tests for the AsusWrt sensor."""
from datetime import timedelta
from unittest.mock import AsyncMock, Mock, patch

from aioasuswrt.asuswrt import Device as LegacyDevice
from pyasuswrt.asuswrt import AsusWrtError, Device as HttpDevice
import pytest

from homeassistant.components import device_tracker, sensor
from homeassistant.components.asuswrt.const import (
    CONF_INTERFACE,
    DOMAIN,
    PROTOCOL_HTTP,
    PROTOCOL_HTTPS,
    PROTOCOL_TELNET,
)
from homeassistant.components.asuswrt.router import DEFAULT_NAME
from homeassistant.components.device_tracker import CONF_CONSIDER_HOME
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

ASUSWRT_BASE = "homeassistant.components.asuswrt"
ASUSWRT_HTTP_LIB = f"{ASUSWRT_BASE}.bridge.AsusWrtHttp"
ASUSWRT_LEGACY_LIB = f"{ASUSWRT_BASE}.bridge.AsusWrtLegacy"

HOST = "myrouter.asuswrt.com"
IP_ADDRESS = "192.168.1.1"

CONFIG_DATA_TELNET = {
    CONF_HOST: HOST,
    CONF_PORT: 22,
    CONF_PROTOCOL: PROTOCOL_TELNET,
    CONF_USERNAME: "user",
    CONF_PASSWORD: "pwd",
    CONF_MODE: "router",
}

CONFIG_DATA_HTTP = {
    CONF_HOST: HOST,
    CONF_PORT: 80,
    CONF_PROTOCOL: PROTOCOL_HTTP,
    CONF_USERNAME: "user",
    CONF_PASSWORD: "pwd",
}

MAC_ADDR = "a1:b2:c3:d4:e5:f6"

MOCK_BYTES_TOTAL = [60000000000, 50000000000]
MOCK_BYTES_TOTAL_HTTP = {k: v for k, v in enumerate(MOCK_BYTES_TOTAL)}
MOCK_CURRENT_TRANSFER_RATES = [20000000, 10000000]
MOCK_CURRENT_TRANSFER_RATES_HTTP = {
    k: v for k, v in enumerate(MOCK_CURRENT_TRANSFER_RATES)
}
MOCK_LOAD_AVG = [1.1, 1.2, 1.3]
MOCK_TEMPERATURES = {"2.4GHz": 40, "5.0GHz": 0, "CPU": 71.2}
MOCK_MAC_1 = "A1:B1:C1:D1:E1:F1"
MOCK_MAC_2 = "A2:B2:C2:D2:E2:F2"
MOCK_MAC_3 = "A3:B3:C3:D3:E3:F3"
MOCK_MAC_4 = "A4:B4:C4:D4:E4:F4"

SENSORS_DEFAULT = [
    "Download Speed",
    "Download",
    "Upload Speed",
    "Upload",
]

SENSORS_LOADAVG = [
    "Load Avg (1m)",
    "Load Avg (5m)",
    "Load Avg (15m)",
]

SENSORS_TEMP = [
    "2.4GHz Temperature",
    "5GHz Temperature",
    "CPU Temperature",
]

SENSORS_ALL_LEGACY = [*SENSORS_DEFAULT, *SENSORS_LOADAVG, *SENSORS_TEMP]
SENSORS_ALL_HTTP = [*SENSORS_DEFAULT, *SENSORS_TEMP]

PATCH_SETUP_ENTRY = patch(
    f"{ASUSWRT_BASE}.async_setup_entry",
    return_value=True,
)


def new_device(protocol, mac, ip, name):
    """Return a new device for specific protocol."""
    if protocol in [PROTOCOL_HTTP, PROTOCOL_HTTPS]:
        return HttpDevice(mac, ip, name, MAC_ADDR, None, None)
    return LegacyDevice(mac, ip, name)


@pytest.fixture(name="mock_devices_legacy")
def mock_devices_legacy_fixture():
    """Mock a list of devices."""
    return {
        MOCK_MAC_1: LegacyDevice(MOCK_MAC_1, "192.168.1.2", "Test"),
        MOCK_MAC_2: LegacyDevice(MOCK_MAC_2, "192.168.1.3", "TestTwo"),
    }


@pytest.fixture(name="mock_devices_http")
def mock_devices_http_fixture():
    """Mock a list of devices."""
    return {
        MOCK_MAC_1: HttpDevice(MOCK_MAC_1, "192.168.1.2", "Test", MAC_ADDR, None, None),
        MOCK_MAC_2: HttpDevice(
            MOCK_MAC_2, "192.168.1.3", "TestTwo", MAC_ADDR, None, None
        ),
    }


@pytest.fixture(name="mock_available_temps")
def mock_available_temps_fixture():
    """Mock a list of available temperature sensors."""
    return [True, False, True]


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


@pytest.fixture(name="connect_legacy")
def mock_controller_connect_legacy(mock_devices_legacy, mock_available_temps):
    """Mock a successful connection with legacy library."""
    with patch(ASUSWRT_LEGACY_LIB) as service_mock:
        service_mock.return_value.connection.async_connect = AsyncMock()
        service_mock.return_value.is_connected = True
        service_mock.return_value.connection.disconnect = Mock()
        service_mock.return_value.async_get_nvram = AsyncMock(
            return_value={
                "label_mac": MAC_ADDR,
                "model": "abcd",
                "firmver": "efg",
                "buildno": "123",
            }
        )
        service_mock.return_value.async_get_connected_devices = AsyncMock(
            return_value=mock_devices_legacy
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


@pytest.fixture(name="connect_http")
def mock_controller_connect_http(mock_devices_http):
    """Mock a successful connection with http library."""
    with patch(ASUSWRT_HTTP_LIB) as service_mock:
        service_mock.return_value.async_connect = AsyncMock()
        service_mock.return_value.is_connected = True
        service_mock.return_value.mac = MAC_ADDR
        service_mock.return_value.async_disconnect = AsyncMock()
        service_mock.return_value.async_get_settings = AsyncMock(
            return_value={
                "productid": "abcd",
                "firmver": "efg",
                "buildno": "123",
                "extendno": "2",
            }
        )
        service_mock.return_value.async_get_connected_devices = AsyncMock(
            return_value=mock_devices_http
        )
        service_mock.return_value.async_get_traffic_bytes = AsyncMock(
            return_value=MOCK_BYTES_TOTAL_HTTP
        )
        service_mock.return_value.async_get_traffic_rates = AsyncMock(
            return_value=MOCK_CURRENT_TRANSFER_RATES_HTTP
        )
        service_mock.return_value.async_get_temperatures = AsyncMock(
            return_value={"2.4GHz": 40, "CPU": 71.2}
        )
        yield service_mock


@pytest.fixture(name="connect_legacy_sens_fail")
def mock_controller_connect_legacy_sens_fail():
    """Mock a successful connection using legacy library with sensors fail."""
    with patch(ASUSWRT_LEGACY_LIB) as service_mock:
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


@pytest.fixture(name="connect_http_sens_fail")
def mock_controller_connect_http_sens_fail():
    """Mock a successful connection using http library with sensors fail."""
    with patch(ASUSWRT_HTTP_LIB) as service_mock:
        service_mock.return_value.async_connect = AsyncMock()
        service_mock.return_value.is_connected = True
        service_mock.return_value.mac = None
        service_mock.return_value.async_disconnect = AsyncMock()
        service_mock.return_value.async_get_settings = AsyncMock(
            side_effect=AsusWrtError
        )
        service_mock.return_value.async_get_connected_devices = AsyncMock(
            side_effect=AsusWrtError
        )
        service_mock.return_value.async_get_traffic_bytes = AsyncMock(
            side_effect=AsusWrtError
        )
        service_mock.return_value.async_get_traffic_rates = AsyncMock(
            side_effect=AsusWrtError
        )
        service_mock.return_value.async_get_temperatures = AsyncMock(
            side_effect=AsusWrtError
        )
        yield service_mock


def _setup_entry(hass, config, sensors, unique_id=None):
    """Create mock config entry with enabled sensors."""
    entity_reg = er.async_get(hass)

    # init config entry
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=config,
        options={CONF_CONSIDER_HOME: 60},
        unique_id=unique_id,
    )

    # init variable
    obj_prefix = slugify(HOST if unique_id else DEFAULT_NAME)
    sensor_prefix = f"{sensor.DOMAIN}.{obj_prefix}"

    # Pre-enable the status sensor
    for sensor_name in sensors:
        sensor_id = slugify(sensor_name)
        entity_reg.async_get_or_create(
            sensor.DOMAIN,
            DOMAIN,
            f"{DOMAIN} {unique_id or DEFAULT_NAME} {sensor_name}",
            suggested_object_id=f"{obj_prefix}_{sensor_id}",
            config_entry=config_entry,
            disabled_by=None,
        )

    return config_entry, sensor_prefix


async def _test_sensors(
    hass,
    mock_devices,
    config,
    entry_unique_id,
):
    """Test creating AsusWRT default sensors and tracker."""
    config_entry, sensor_prefix = _setup_entry(
        hass, config, SENSORS_DEFAULT, entry_unique_id
    )

    # Create the first device tracker to test mac conversion
    entity_reg = er.async_get(hass)
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
    assert hass.states.get(f"{sensor_prefix}_devices_connected").state == "2"

    # remove first tracked device
    mock_devices.pop(MOCK_MAC_1)

    async_fire_time_changed(hass, utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done()

    # consider home option set, all devices still home but only 1 device connected
    assert hass.states.get(f"{device_tracker.DOMAIN}.test").state == STATE_HOME
    assert hass.states.get(f"{device_tracker.DOMAIN}.testtwo").state == STATE_HOME
    assert hass.states.get(f"{sensor_prefix}_devices_connected").state == "1"

    # add 2 new devices, one unnamed that should be ignored but counted
    mock_devices[MOCK_MAC_3] = new_device(
        config[CONF_PROTOCOL], MOCK_MAC_3, "192.168.1.4", "TestThree"
    )
    mock_devices[MOCK_MAC_4] = new_device(
        config[CONF_PROTOCOL], MOCK_MAC_4, "192.168.1.5", None
    )

    # change consider home settings to have status not home of removed tracked device
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


@pytest.mark.parametrize(
    "entry_unique_id",
    [None, MAC_ADDR],
)
async def test_sensors_legacy(
    hass,
    connect_legacy,
    mock_devices_legacy,
    create_device_registry_devices,
    entry_unique_id,
):
    """Test creating AsusWRT default sensors and tracker with legacy protocol."""
    await _test_sensors(hass, mock_devices_legacy, CONFIG_DATA_TELNET, entry_unique_id)


@pytest.mark.parametrize(
    "entry_unique_id",
    [None, MAC_ADDR],
)
async def test_sensors_http(
    hass,
    connect_http,
    mock_devices_http,
    create_device_registry_devices,
    entry_unique_id,
):
    """Test creating AsusWRT default sensors and tracker with http protocol."""
    await _test_sensors(hass, mock_devices_http, CONFIG_DATA_HTTP, entry_unique_id)


async def test_loadavg_sensors(
    hass,
    connect_legacy,
):
    """Test creating an AsusWRT load average sensors."""
    config_entry, sensor_prefix = _setup_entry(
        hass, CONFIG_DATA_TELNET, SENSORS_LOADAVG
    )
    config_entry.add_to_hass(hass)

    # initial devices setup
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done()

    # assert temperature sensor available
    assert hass.states.get(f"{sensor_prefix}_load_avg_1m").state == "1.1"
    assert hass.states.get(f"{sensor_prefix}_load_avg_5m").state == "1.2"
    assert hass.states.get(f"{sensor_prefix}_load_avg_15m").state == "1.3"


async def test_temperature_sensors_legacy_fail(
    hass,
    connect_legacy,
    mock_available_temps,
):
    """Test fail creating AsusWRT temperature sensors."""
    config_entry, sensor_prefix = _setup_entry(hass, CONFIG_DATA_TELNET, SENSORS_TEMP)
    config_entry.add_to_hass(hass)

    # Only length of 3 booleans is valid. Checking the exception handling.
    mock_available_temps.pop(2)

    # initial devices setup
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # assert temperature availability exception is handled correctly
    assert not hass.states.get(f"{sensor_prefix}_2_4ghz_temperature")
    assert not hass.states.get(f"{sensor_prefix}_5ghz_temperature")
    assert not hass.states.get(f"{sensor_prefix}_cpu_temperature")


async def test_temperature_sensors_http_fail(
    hass,
    connect_http_sens_fail,
):
    """Test fail creating AsusWRT temperature sensors."""
    config_entry, sensor_prefix = _setup_entry(hass, CONFIG_DATA_HTTP, SENSORS_TEMP)
    config_entry.add_to_hass(hass)

    # initial devices setup
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # assert temperature availability exception is handled correctly
    assert not hass.states.get(f"{sensor_prefix}_2_4ghz_temperature")
    assert not hass.states.get(f"{sensor_prefix}_5ghz_temperature")
    assert not hass.states.get(f"{sensor_prefix}_cpu_temperature")


async def _test_temperature_sensors(hass, config):
    """Test creating a AsusWRT temperature sensors."""
    config_entry, sensor_prefix = _setup_entry(hass, config, SENSORS_TEMP)
    config_entry.add_to_hass(hass)

    # initial devices setup
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done()

    # assert temperature sensor available
    assert hass.states.get(f"{sensor_prefix}_2_4ghz_temperature").state == "40.0"
    assert not hass.states.get(f"{sensor_prefix}_5ghz_temperature")
    assert hass.states.get(f"{sensor_prefix}_cpu_temperature").state == "71.2"


async def test_temperature_sensors_legacy(
    hass,
    connect_legacy,
):
    """Test creating a AsusWRT temperature sensors."""
    await _test_temperature_sensors(hass, CONFIG_DATA_TELNET)


async def test_temperature_sensors_http(
    hass,
    connect_http,
):
    """Test creating a AsusWRT temperature sensors."""
    await _test_temperature_sensors(hass, CONFIG_DATA_HTTP)


@pytest.mark.parametrize(
    "side_effect",
    [OSError, None],
)
async def test_connect_fail_legacy(hass, side_effect):
    """Test AsusWRT connect fail."""

    # init config entry
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_DATA_TELNET,
    )
    config_entry.add_to_hass(hass)

    with patch(ASUSWRT_LEGACY_LIB) as asus_wrt:
        asus_wrt.return_value.connection.async_connect = AsyncMock(
            side_effect=side_effect
        )
        asus_wrt.return_value.async_get_nvram = AsyncMock()
        asus_wrt.return_value.is_connected = False

        # initial setup fail
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    "side_effect",
    [AsusWrtError, None],
)
async def test_connect_fail_http(hass, side_effect):
    """Test AsusWRT connect fail."""

    # init config entry
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_DATA_HTTP,
    )
    config_entry.add_to_hass(hass)

    with patch(ASUSWRT_HTTP_LIB) as asus_wrt:
        asus_wrt.return_value.async_connect = AsyncMock(side_effect=side_effect)
        asus_wrt.return_value.async_get_settings = AsyncMock()
        asus_wrt.return_value.is_connected = False
        asus_wrt.return_value.mac = None

        # initial setup fail
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def _test_sensors_polling_fails(hass, config, sensors):
    """Test AsusWRT sensors are unavailable when polling fails."""
    config_entry, sensor_prefix = _setup_entry(hass, config, sensors)
    config_entry.add_to_hass(hass)

    # initial devices setup
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done()

    for sensor_name in sensors:
        assert (
            hass.states.get(f"{sensor_prefix}_{slugify(sensor_name)}").state
            == STATE_UNAVAILABLE
        )
    assert hass.states.get(f"{sensor_prefix}_devices_connected").state == "0"


async def test_sensors_polling_fails_legacy(
    hass,
    connect_legacy_sens_fail,
):
    """Test AsusWRT sensors are unavailable when polling fails."""
    await _test_sensors_polling_fails(hass, CONFIG_DATA_TELNET, SENSORS_ALL_LEGACY)


async def test_sensors_polling_fails_http(
    hass,
    connect_http_sens_fail,
):
    """Test AsusWRT sensors are unavailable when polling fails."""
    with patch(
        f"{ASUSWRT_BASE}.bridge.AsusWrtHttpBridge._get_available_temperature_sensors",
        return_value=[*MOCK_TEMPERATURES],
    ):
        await _test_sensors_polling_fails(hass, CONFIG_DATA_HTTP, SENSORS_ALL_HTTP)


async def _test_options_reload(hass, config):
    """Test AsusWRT integration is reload changing an options that require this."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=config, unique_id=MAC_ADDR)
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done()

    with PATCH_SETUP_ENTRY as setup_entry_call:
        # change an option that requires integration reload
        hass.config_entries.async_update_entry(
            config_entry, options={CONF_INTERFACE: "eth1"}
        )
        await hass.async_block_till_done()

        assert setup_entry_call.called
        assert config_entry.state is ConfigEntryState.LOADED


async def test_options_reload_legacy(
    hass,
    connect_legacy,
):
    """Test AsusWRT integration is reload changing an options that require this."""
    await _test_options_reload(hass, CONFIG_DATA_TELNET)


async def test_options_reload_http(
    hass,
    connect_http,
):
    """Test AsusWRT integration is reload changing an options that require this."""
    await _test_options_reload(hass, CONFIG_DATA_HTTP)

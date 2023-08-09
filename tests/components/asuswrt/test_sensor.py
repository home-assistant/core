"""Tests for the AsusWrt sensor."""
from datetime import timedelta
from unittest.mock import AsyncMock, Mock, patch

from aioasuswrt.asuswrt import Device
import pytest

from homeassistant.components import device_tracker, sensor
from homeassistant.components.asuswrt.const import (
    CONF_INTERFACE,
    DOMAIN,
    MODE_ROUTER,
    PROTOCOL_TELNET,
    SENSORS_BYTES,
    SENSORS_LOAD_AVG,
    SENSORS_RATES,
    SENSORS_TEMPERATURES,
)
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
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import slugify
from homeassistant.util.dt import utcnow

from tests.common import MockConfigEntry, async_fire_time_changed

ASUSWRT_LIB = "homeassistant.components.asuswrt.bridge.AsusWrtLegacy"

HOST = "myrouter.asuswrt.com"
IP_ADDRESS = "192.168.1.1"

CONFIG_DATA = {
    CONF_HOST: HOST,
    CONF_PORT: 22,
    CONF_PROTOCOL: PROTOCOL_TELNET,
    CONF_USERNAME: "user",
    CONF_PASSWORD: "pwd",
    CONF_MODE: MODE_ROUTER,
}

MAC_ADDR = "a1:b2:c3:d4:e5:f6"

MOCK_BYTES_TOTAL = [60000000000, 50000000000]
MOCK_CURRENT_TRANSFER_RATES = [20000000, 10000000]
MOCK_LOAD_AVG = [1.1, 1.2, 1.3]
MOCK_TEMPERATURES = {"2.4GHz": 40.0, "5.0GHz": 0.0, "CPU": 71.2}
MOCK_MAC_1 = "A1:B1:C1:D1:E1:F1"
MOCK_MAC_2 = "A2:B2:C2:D2:E2:F2"
MOCK_MAC_3 = "A3:B3:C3:D3:E3:F3"
MOCK_MAC_4 = "A4:B4:C4:D4:E4:F4"

SENSORS_DEFAULT = [*SENSORS_BYTES, *SENSORS_RATES]
SENSORS_ALL = [*SENSORS_DEFAULT, *SENSORS_LOAD_AVG, *SENSORS_TEMPERATURES]

PATCH_SETUP_ENTRY = patch(
    "homeassistant.components.asuswrt.async_setup_entry",
    return_value=True,
)


def new_device(mac, ip, name):
    """Return a new device for specific protocol."""
    return Device(mac, ip, name)


@pytest.fixture(name="mock_devices")
def mock_devices_fixture():
    """Mock a list of devices."""
    return {
        MOCK_MAC_1: Device(MOCK_MAC_1, "192.168.1.2", "Test"),
        MOCK_MAC_2: Device(MOCK_MAC_2, "192.168.1.3", "TestTwo"),
    }


@pytest.fixture(name="mock_available_temps")
def mock_available_temps_fixture():
    """Mock a list of available temperature sensors."""
    return [True, False, True]


@pytest.fixture(name="create_device_registry_devices")
def create_device_registry_devices_fixture(hass: HomeAssistant):
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
    """Mock a successful connection with AsusWrt library."""
    with patch(ASUSWRT_LIB) as service_mock:
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
    """Mock a successful connection using AsusWrt library with sensors failing."""
    with patch(ASUSWRT_LIB) as service_mock:
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


def _setup_entry(hass: HomeAssistant, config, sensors, unique_id=None):
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
    obj_prefix = slugify(HOST)
    sensor_prefix = f"{sensor.DOMAIN}.{obj_prefix}"
    unique_id_prefix = slugify(unique_id or config_entry.entry_id)

    # Pre-enable the status sensor
    for sensor_key in sensors:
        sensor_id = slugify(sensor_key)
        entity_reg.async_get_or_create(
            sensor.DOMAIN,
            DOMAIN,
            f"{unique_id_prefix}_{sensor_id}",
            suggested_object_id=f"{obj_prefix}_{sensor_id}",
            config_entry=config_entry,
            disabled_by=None,
        )

    return config_entry, sensor_prefix


@pytest.mark.parametrize(
    "entry_unique_id",
    [None, MAC_ADDR],
)
async def test_sensors(
    hass: HomeAssistant,
    connect,
    mock_devices,
    create_device_registry_devices,
    entry_unique_id,
) -> None:
    """Test creating AsusWRT default sensors and tracker."""
    config_entry, sensor_prefix = _setup_entry(
        hass, CONFIG_DATA, SENSORS_DEFAULT, entry_unique_id
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
    assert hass.states.get(f"{sensor_prefix}_sensor_rx_rates").state == "160.0"
    assert hass.states.get(f"{sensor_prefix}_sensor_rx_bytes").state == "60.0"
    assert hass.states.get(f"{sensor_prefix}_sensor_tx_rates").state == "80.0"
    assert hass.states.get(f"{sensor_prefix}_sensor_tx_bytes").state == "50.0"
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
    mock_devices[MOCK_MAC_3] = new_device(MOCK_MAC_3, "192.168.1.4", "TestThree")
    mock_devices[MOCK_MAC_4] = new_device(MOCK_MAC_4, "192.168.1.5", None)

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


async def test_loadavg_sensors(
    hass: HomeAssistant,
    connect,
) -> None:
    """Test creating an AsusWRT load average sensors."""
    config_entry, sensor_prefix = _setup_entry(hass, CONFIG_DATA, SENSORS_LOAD_AVG)
    config_entry.add_to_hass(hass)

    # initial devices setup
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done()

    # assert temperature sensor available
    assert hass.states.get(f"{sensor_prefix}_sensor_load_avg1").state == "1.1"
    assert hass.states.get(f"{sensor_prefix}_sensor_load_avg5").state == "1.2"
    assert hass.states.get(f"{sensor_prefix}_sensor_load_avg15").state == "1.3"


async def test_temperature_sensors(
    hass: HomeAssistant,
    connect,
) -> None:
    """Test creating a AsusWRT temperature sensors."""
    config_entry, sensor_prefix = _setup_entry(hass, CONFIG_DATA, SENSORS_TEMPERATURES)
    config_entry.add_to_hass(hass)

    # initial devices setup
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done()

    # assert temperature sensor available
    assert hass.states.get(f"{sensor_prefix}_2_4ghz").state == "40.0"
    assert not hass.states.get(f"{sensor_prefix}_5_0ghz")
    assert hass.states.get(f"{sensor_prefix}_cpu").state == "71.2"


@pytest.mark.parametrize(
    "side_effect",
    [OSError, None],
)
async def test_connect_fail(hass: HomeAssistant, side_effect) -> None:
    """Test AsusWRT connect fail."""

    # init config entry
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_DATA,
    )
    config_entry.add_to_hass(hass)

    with patch(ASUSWRT_LIB) as asus_wrt:
        asus_wrt.return_value.connection.async_connect = AsyncMock(
            side_effect=side_effect
        )
        asus_wrt.return_value.async_get_nvram = AsyncMock()
        asus_wrt.return_value.is_connected = False

        # initial setup fail
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_sensors_polling_fails(hass: HomeAssistant, connect_sens_fail) -> None:
    """Test AsusWRT sensors are unavailable when polling fails."""
    config_entry, sensor_prefix = _setup_entry(hass, CONFIG_DATA, SENSORS_ALL)
    config_entry.add_to_hass(hass)

    # initial devices setup
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done()

    for sensor_name in SENSORS_ALL:
        assert (
            hass.states.get(f"{sensor_prefix}_{slugify(sensor_name)}").state
            == STATE_UNAVAILABLE
        )
    assert hass.states.get(f"{sensor_prefix}_devices_connected").state == "0"


async def test_options_reload(hass: HomeAssistant, connect) -> None:
    """Test AsusWRT integration is reload changing an options that require this."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=CONFIG_DATA, unique_id=MAC_ADDR)
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


async def test_unique_id_migration(hass: HomeAssistant, connect) -> None:
    """Test AsusWRT entities unique id format migration."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_DATA,
        unique_id=MAC_ADDR,
    )
    config_entry.add_to_hass(hass)

    entity_reg = er.async_get(hass)
    obj_entity_id = slugify(f"{HOST} Upload")
    entity_reg.async_get_or_create(
        sensor.DOMAIN,
        DOMAIN,
        f"{DOMAIN} {MAC_ADDR} Upload",
        suggested_object_id=obj_entity_id,
        config_entry=config_entry,
        disabled_by=None,
    )

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    migr_entity = entity_reg.async_get(f"{sensor.DOMAIN}.{obj_entity_id}")
    assert migr_entity is not None
    assert migr_entity.unique_id == slugify(f"{MAC_ADDR}_sensor_tx_bytes")

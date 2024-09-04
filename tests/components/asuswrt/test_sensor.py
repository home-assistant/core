"""Tests for the AsusWrt sensor."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from pyasuswrt.exceptions import AsusWrtError, AsusWrtNotAvailableInfoError
import pytest

from homeassistant.components import device_tracker, sensor
from homeassistant.components.asuswrt.const import (
    CONF_INTERFACE,
    DOMAIN,
    SENSORS_BYTES,
    SENSORS_CPU,
    SENSORS_LOAD_AVG,
    SENSORS_MEMORY,
    SENSORS_RATES,
    SENSORS_TEMPERATURES,
    SENSORS_TEMPERATURES_LEGACY,
    SENSORS_UPTIME,
)
from homeassistant.components.device_tracker import CONF_CONSIDER_HOME
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_PROTOCOL,
    STATE_HOME,
    STATE_NOT_HOME,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import slugify

from .common import (
    CONFIG_DATA_HTTP,
    CONFIG_DATA_TELNET,
    HOST,
    MOCK_MACS,
    ROUTER_MAC_ADDR,
    new_device,
)

from tests.common import MockConfigEntry, async_fire_time_changed

SENSORS_DEFAULT = [*SENSORS_BYTES, *SENSORS_RATES]

SENSORS_ALL_LEGACY = [*SENSORS_DEFAULT, *SENSORS_LOAD_AVG, *SENSORS_TEMPERATURES_LEGACY]
SENSORS_ALL_HTTP = [
    *SENSORS_DEFAULT,
    *SENSORS_CPU,
    *SENSORS_LOAD_AVG,
    *SENSORS_MEMORY,
    *SENSORS_TEMPERATURES,
    *SENSORS_UPTIME,
]


@pytest.fixture(name="create_device_registry_devices")
def create_device_registry_devices_fixture(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
):
    """Create device registry devices so the device tracker entities are enabled when added."""
    config_entry = MockConfigEntry(domain="something_else")
    config_entry.add_to_hass(hass)

    for idx, device in enumerate((MOCK_MACS[2], MOCK_MACS[3])):
        device_registry.async_get_or_create(
            name=f"Device {idx}",
            config_entry_id=config_entry.entry_id,
            connections={(dr.CONNECTION_NETWORK_MAC, dr.format_mac(device))},
        )


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


async def _test_sensors(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_devices,
    config,
    entry_unique_id,
) -> None:
    """Test creating AsusWRT default sensors and tracker."""
    config_entry, sensor_prefix = _setup_entry(
        hass, config, SENSORS_DEFAULT, entry_unique_id
    )

    # Create the first device tracker to test mac conversion
    entity_reg = er.async_get(hass)
    for mac, name in {
        MOCK_MACS[0]: "test",
        dr.format_mac(MOCK_MACS[1]): "testtwo",
        MOCK_MACS[1]: "testremove",
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
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(f"{device_tracker.DOMAIN}.test").state == STATE_HOME
    assert hass.states.get(f"{device_tracker.DOMAIN}.testtwo").state == STATE_HOME
    assert hass.states.get(f"{sensor_prefix}_sensor_rx_rates").state == "160.0"
    assert hass.states.get(f"{sensor_prefix}_sensor_rx_bytes").state == "60.0"
    assert hass.states.get(f"{sensor_prefix}_sensor_tx_rates").state == "80.0"
    assert hass.states.get(f"{sensor_prefix}_sensor_tx_bytes").state == "50.0"
    assert hass.states.get(f"{sensor_prefix}_devices_connected").state == "2"

    # remove first tracked device
    mock_devices.pop(MOCK_MACS[0])

    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # consider home option set, all devices still home but only 1 device connected
    assert hass.states.get(f"{device_tracker.DOMAIN}.test").state == STATE_HOME
    assert hass.states.get(f"{device_tracker.DOMAIN}.testtwo").state == STATE_HOME
    assert hass.states.get(f"{sensor_prefix}_devices_connected").state == "1"

    # add 2 new devices, one unnamed that should be ignored but counted
    mock_devices[MOCK_MACS[2]] = new_device(
        config[CONF_PROTOCOL], MOCK_MACS[2], "192.168.1.4", "TestThree"
    )
    mock_devices[MOCK_MACS[3]] = new_device(
        config[CONF_PROTOCOL], MOCK_MACS[3], "192.168.1.5", None
    )

    # change consider home settings to have status not home of removed tracked device
    hass.config_entries.async_update_entry(
        config_entry, options={CONF_CONSIDER_HOME: 0}
    )
    await hass.async_block_till_done()
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # consider home option set to 0, device "test" not home
    assert hass.states.get(f"{device_tracker.DOMAIN}.test").state == STATE_NOT_HOME
    assert hass.states.get(f"{device_tracker.DOMAIN}.testtwo").state == STATE_HOME
    assert hass.states.get(f"{device_tracker.DOMAIN}.testthree").state == STATE_HOME
    assert hass.states.get(f"{sensor_prefix}_devices_connected").state == "3"


@pytest.mark.parametrize(
    "entry_unique_id",
    [None, ROUTER_MAC_ADDR],
)
async def test_sensors_legacy(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_devices_legacy,
    entry_unique_id,
    connect_legacy,
    create_device_registry_devices,
) -> None:
    """Test creating AsusWRT default sensors and tracker with legacy protocol."""
    await _test_sensors(
        hass, freezer, mock_devices_legacy, CONFIG_DATA_TELNET, entry_unique_id
    )


@pytest.mark.parametrize(
    "entry_unique_id",
    [None, ROUTER_MAC_ADDR],
)
async def test_sensors_http(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_devices_http,
    entry_unique_id,
    connect_http,
    create_device_registry_devices,
) -> None:
    """Test creating AsusWRT default sensors and tracker with http protocol."""
    await _test_sensors(
        hass, freezer, mock_devices_http, CONFIG_DATA_HTTP, entry_unique_id
    )


async def _test_loadavg_sensors(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, config
) -> None:
    """Test creating an AsusWRT load average sensors."""
    config_entry, sensor_prefix = _setup_entry(hass, config, SENSORS_LOAD_AVG)
    config_entry.add_to_hass(hass)

    # initial devices setup
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # assert temperature sensor available
    assert hass.states.get(f"{sensor_prefix}_sensor_load_avg1").state == "1.1"
    assert hass.states.get(f"{sensor_prefix}_sensor_load_avg5").state == "1.2"
    assert hass.states.get(f"{sensor_prefix}_sensor_load_avg15").state == "1.3"


async def test_loadavg_sensors_legacy(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, connect_legacy
) -> None:
    """Test creating an AsusWRT load average sensors."""
    await _test_loadavg_sensors(hass, freezer, CONFIG_DATA_TELNET)


async def test_loadavg_sensors_http(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, connect_http
) -> None:
    """Test creating an AsusWRT load average sensors."""
    await _test_loadavg_sensors(hass, freezer, CONFIG_DATA_HTTP)


async def test_loadavg_sensors_unaivalable_http(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, connect_http
) -> None:
    """Test load average sensors no available using http."""
    config_entry, sensor_prefix = _setup_entry(hass, CONFIG_DATA_HTTP, SENSORS_LOAD_AVG)
    config_entry.add_to_hass(hass)

    connect_http.return_value.async_get_loadavg.side_effect = (
        AsusWrtNotAvailableInfoError
    )

    # initial devices setup
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # assert load average sensors not available
    assert not hass.states.get(f"{sensor_prefix}_sensor_load_avg1")
    assert not hass.states.get(f"{sensor_prefix}_sensor_load_avg5")
    assert not hass.states.get(f"{sensor_prefix}_sensor_load_avg15")


async def test_temperature_sensors_http_fail(
    hass: HomeAssistant, connect_http_sens_fail
) -> None:
    """Test fail creating AsusWRT temperature sensors."""
    config_entry, sensor_prefix = _setup_entry(
        hass, CONFIG_DATA_HTTP, SENSORS_TEMPERATURES
    )
    config_entry.add_to_hass(hass)

    # initial devices setup
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # assert temperature availability exception is handled correctly
    assert not hass.states.get(f"{sensor_prefix}_2_4ghz")
    assert not hass.states.get(f"{sensor_prefix}_5_0ghz")
    assert not hass.states.get(f"{sensor_prefix}_cpu")
    assert not hass.states.get(f"{sensor_prefix}_5_0ghz_2")
    assert not hass.states.get(f"{sensor_prefix}_6_0ghz")


async def _test_temperature_sensors(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, config, sensors
) -> str:
    """Test creating a AsusWRT temperature sensors."""
    config_entry, sensor_prefix = _setup_entry(hass, config, sensors)
    config_entry.add_to_hass(hass)

    # initial devices setup
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    return sensor_prefix


async def test_temperature_sensors_legacy(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, connect_legacy
) -> None:
    """Test creating a AsusWRT temperature sensors."""
    sensor_prefix = await _test_temperature_sensors(
        hass, freezer, CONFIG_DATA_TELNET, SENSORS_TEMPERATURES_LEGACY
    )
    # assert temperature sensor available
    assert hass.states.get(f"{sensor_prefix}_2_4ghz").state == "40.2"
    assert hass.states.get(f"{sensor_prefix}_cpu").state == "71.2"
    assert not hass.states.get(f"{sensor_prefix}_5_0ghz")


async def test_temperature_sensors_http(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, connect_http
) -> None:
    """Test creating a AsusWRT temperature sensors."""
    sensor_prefix = await _test_temperature_sensors(
        hass, freezer, CONFIG_DATA_HTTP, SENSORS_TEMPERATURES
    )
    # assert temperature sensor available
    assert hass.states.get(f"{sensor_prefix}_2_4ghz").state == "40.2"
    assert hass.states.get(f"{sensor_prefix}_cpu").state == "71.2"
    assert hass.states.get(f"{sensor_prefix}_5_0ghz_2").state == "40.3"
    assert hass.states.get(f"{sensor_prefix}_6_0ghz").state == "40.4"
    assert not hass.states.get(f"{sensor_prefix}_5_0ghz")


async def test_cpu_sensors_http_fail(
    hass: HomeAssistant, connect_http_sens_fail
) -> None:
    """Test fail creating AsusWRT cpu sensors."""
    config_entry, sensor_prefix = _setup_entry(hass, CONFIG_DATA_HTTP, SENSORS_CPU)
    config_entry.add_to_hass(hass)

    # initial devices setup
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # assert cpu availability exception is handled correctly
    assert not hass.states.get(f"{sensor_prefix}_cpu1_usage")
    assert not hass.states.get(f"{sensor_prefix}_cpu2_usage")
    assert not hass.states.get(f"{sensor_prefix}_cpu3_usage")
    assert not hass.states.get(f"{sensor_prefix}_cpu4_usage")
    assert not hass.states.get(f"{sensor_prefix}_cpu5_usage")
    assert not hass.states.get(f"{sensor_prefix}_cpu6_usage")
    assert not hass.states.get(f"{sensor_prefix}_cpu7_usage")
    assert not hass.states.get(f"{sensor_prefix}_cpu8_usage")
    assert not hass.states.get(f"{sensor_prefix}_cpu_total_usage")


async def test_cpu_sensors_http(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, connect_http
) -> None:
    """Test creating AsusWRT cpu sensors."""
    config_entry, sensor_prefix = _setup_entry(hass, CONFIG_DATA_HTTP, SENSORS_CPU)
    config_entry.add_to_hass(hass)

    # initial devices setup
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # assert cpu sensors available
    assert hass.states.get(f"{sensor_prefix}_cpu1_usage").state == "0.1"
    assert hass.states.get(f"{sensor_prefix}_cpu2_usage").state == "0.2"
    assert hass.states.get(f"{sensor_prefix}_cpu3_usage").state == "0.3"
    assert hass.states.get(f"{sensor_prefix}_cpu4_usage").state == "0.4"
    assert hass.states.get(f"{sensor_prefix}_cpu5_usage").state == "0.5"
    assert hass.states.get(f"{sensor_prefix}_cpu6_usage").state == "0.6"
    assert hass.states.get(f"{sensor_prefix}_cpu7_usage").state == "0.7"
    assert hass.states.get(f"{sensor_prefix}_cpu8_usage").state == "0.8"
    assert hass.states.get(f"{sensor_prefix}_cpu_total_usage").state == "0.9"


async def test_memory_sensors_http(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, connect_http
) -> None:
    """Test creating AsusWRT memory sensors."""
    config_entry, sensor_prefix = _setup_entry(hass, CONFIG_DATA_HTTP, SENSORS_MEMORY)
    config_entry.add_to_hass(hass)

    # initial devices setup
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # assert memory sensors available
    assert hass.states.get(f"{sensor_prefix}_mem_usage_perc").state == "52.4"
    assert hass.states.get(f"{sensor_prefix}_mem_free").state == "384.0"
    assert hass.states.get(f"{sensor_prefix}_mem_used").state == "640.0"


async def test_uptime_sensors_http(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, connect_http
) -> None:
    """Test creating AsusWRT uptime sensors."""
    config_entry, sensor_prefix = _setup_entry(hass, CONFIG_DATA_HTTP, SENSORS_UPTIME)
    config_entry.add_to_hass(hass)

    # initial devices setup
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # assert uptime sensors available
    assert (
        hass.states.get(f"{sensor_prefix}_sensor_last_boot").state
        == "2024-08-02T00:47:00+00:00"
    )
    assert hass.states.get(f"{sensor_prefix}_sensor_uptime").state == "1625927"


@pytest.mark.parametrize(
    "side_effect",
    [OSError, None],
)
async def test_connect_fail_legacy(
    hass: HomeAssistant, connect_legacy, side_effect
) -> None:
    """Test AsusWRT connect fail."""

    # init config entry
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_DATA_TELNET,
    )
    config_entry.add_to_hass(hass)

    connect_legacy.return_value.connection.async_connect.side_effect = side_effect
    connect_legacy.return_value.is_connected = False

    # initial setup fail
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    "side_effect",
    [AsusWrtError, None],
)
async def test_connect_fail_http(
    hass: HomeAssistant, connect_http, side_effect
) -> None:
    """Test AsusWRT connect fail."""

    # init config entry
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_DATA_HTTP,
    )
    config_entry.add_to_hass(hass)

    connect_http.return_value.async_connect.side_effect = side_effect
    connect_http.return_value.is_connected = False

    # initial setup fail
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def _test_sensors_polling_fails(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, config, sensors
) -> None:
    """Test AsusWRT sensors are unavailable when polling fails."""
    config_entry, sensor_prefix = _setup_entry(hass, config, sensors)
    config_entry.add_to_hass(hass)

    # initial devices setup
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    for sensor_name in sensors:
        assert (
            hass.states.get(f"{sensor_prefix}_{slugify(sensor_name)}").state
            == STATE_UNAVAILABLE
        )
    assert hass.states.get(f"{sensor_prefix}_devices_connected").state == "0"


async def test_sensors_polling_fails_legacy(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    connect_legacy_sens_fail,
) -> None:
    """Test AsusWRT sensors are unavailable when polling fails."""
    await _test_sensors_polling_fails(
        hass, freezer, CONFIG_DATA_TELNET, SENSORS_ALL_LEGACY
    )


async def test_sensors_polling_fails_http(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    connect_http_sens_fail,
    connect_http_sens_detect,
) -> None:
    """Test AsusWRT sensors are unavailable when polling fails."""
    await _test_sensors_polling_fails(hass, freezer, CONFIG_DATA_HTTP, SENSORS_ALL_HTTP)


async def test_options_reload(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, connect_legacy
) -> None:
    """Test AsusWRT integration is reload changing an options that require this."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_DATA_TELNET,
        unique_id=ROUTER_MAC_ADDR,
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert connect_legacy.return_value.connection.async_connect.call_count == 1

    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # change an option that requires integration reload
    hass.config_entries.async_update_entry(
        config_entry, options={CONF_INTERFACE: "eth1"}
    )
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert connect_legacy.return_value.connection.async_connect.call_count == 2


async def test_unique_id_migration(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, connect_legacy
) -> None:
    """Test AsusWRT entities unique id format migration."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_DATA_TELNET,
        unique_id=ROUTER_MAC_ADDR,
    )
    config_entry.add_to_hass(hass)

    obj_entity_id = slugify(f"{HOST} Upload")
    entity_registry.async_get_or_create(
        sensor.DOMAIN,
        DOMAIN,
        f"{DOMAIN} {ROUTER_MAC_ADDR} Upload",
        suggested_object_id=obj_entity_id,
        config_entry=config_entry,
        disabled_by=None,
    )

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    migr_entity = entity_registry.async_get(f"{sensor.DOMAIN}.{obj_entity_id}")
    assert migr_entity is not None
    assert migr_entity.unique_id == slugify(f"{ROUTER_MAC_ADDR}_sensor_tx_bytes")


async def test_decorator_errors(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    connect_legacy,
    mock_available_temps,
) -> None:
    """Test AsusWRT sensors are unavailable on decorator type check error."""
    sensors = [*SENSORS_BYTES, *SENSORS_TEMPERATURES_LEGACY]
    config_entry, sensor_prefix = _setup_entry(hass, CONFIG_DATA_TELNET, sensors)
    config_entry.add_to_hass(hass)

    mock_available_temps[1] = True
    connect_legacy.return_value.async_get_bytes_total.return_value = "bad_response"
    connect_legacy.return_value.async_get_temperature.return_value = "bad_response"

    # initial devices setup
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    for sensor_name in sensors:
        assert (
            hass.states.get(f"{sensor_prefix}_{slugify(sensor_name)}").state
            == STATE_UNAVAILABLE
        )

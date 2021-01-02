"""Tests for the AsusWrt sensor."""
from datetime import timedelta

from aioasuswrt.asuswrt import Device
import pytest

from homeassistant.components import device_tracker, sensor
from homeassistant.components.asuswrt.const import DOMAIN
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
from homeassistant.util.dt import utcnow

from tests.async_mock import AsyncMock, patch
from tests.common import MockConfigEntry, async_fire_time_changed

DEFAULT_PREFIX = "Asuswrt"
HOST = "myrouter"
IP_ADDRESS = "192.168.1.1"

CONFIG_DATA = {
    CONF_HOST: HOST,
    CONF_PORT: 22,
    CONF_PROTOCOL: "ssh",
    CONF_USERNAME: "user",
    CONF_PASSWORD: "pwd",
    CONF_MODE: "router",
}

MOCK_DEVICES = {
    "a1:b1:c1:d1:e1:f1": Device("a1:b1:c1:d1:e1:f1", "192.168.1.2", "Test"),
    "a2:b2:c2:d2:e2:f2": Device("a2:b2:c2:d2:e2:f2", "192.168.1.3", "TestTwo"),
}
MOCK_BYTES_TOTAL = [60000000000, 50000000000]
MOCK_CURRENT_TRANSFER_RATES = [20000000, 10000000]
MOCK_TEMPERATURES = {"2.4GHz": 50, "5.0GHz": 60, "CPU": 70}


@pytest.fixture(name="connect")
def mock_controller_connect():
    """Mock a successful connection."""
    with patch("homeassistant.components.asuswrt.router.AsusWrt") as service_mock:
        service_mock.return_value.connection.async_connect = AsyncMock()
        service_mock.return_value.is_connected = True
        service_mock.return_value.connection.disconnect = AsyncMock()
        service_mock.return_value.async_get_nvram = AsyncMock(
            return_value={
                "model": "abcd",
                "firmver": "efg",
                "buildno": "123",
            }
        )
        service_mock.return_value.async_get_connected_devices = AsyncMock(
            return_value=MOCK_DEVICES
        )
        service_mock.return_value.async_get_bytes_total = AsyncMock(
            return_value=MOCK_BYTES_TOTAL
        )
        service_mock.return_value.async_get_current_transfer_rates = AsyncMock(
            return_value=MOCK_CURRENT_TRANSFER_RATES
        )
        service_mock.return_value.async_get_temperature = AsyncMock(
            return_value=MOCK_TEMPERATURES
        )
        yield service_mock


async def test_sensors(hass, connect):
    """Test creating an AsusWRT sensor."""
    entity_reg = await hass.helpers.entity_registry.async_get_registry()

    # init config entry
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_DATA,
        options={CONF_CONSIDER_HOME: 0},
    )

    unique_id = DOMAIN
    name_prefix = DEFAULT_PREFIX
    obj_prefix = name_prefix.lower()
    # Pre-enable the status sensor
    entity_reg.async_get_or_create(
        sensor.DOMAIN,
        DOMAIN,
        f"{unique_id} {name_prefix} Devices Connected",
        suggested_object_id=f"{obj_prefix}_devices_connected",
        disabled_by=None,
    )
    entity_reg.async_get_or_create(
        sensor.DOMAIN,
        DOMAIN,
        f"{unique_id} {name_prefix} Download Speed",
        suggested_object_id=f"{obj_prefix}_download_speed",
        disabled_by=None,
    )
    entity_reg.async_get_or_create(
        sensor.DOMAIN,
        DOMAIN,
        f"{unique_id} {name_prefix} Download",
        suggested_object_id=f"{obj_prefix}_download",
        disabled_by=None,
    )
    entity_reg.async_get_or_create(
        sensor.DOMAIN,
        DOMAIN,
        f"{unique_id} {name_prefix} Upload Speed",
        suggested_object_id=f"{obj_prefix}_upload_speed",
        disabled_by=None,
    )
    entity_reg.async_get_or_create(
        sensor.DOMAIN,
        DOMAIN,
        f"{unique_id} {name_prefix} Upload",
        suggested_object_id=f"{obj_prefix}_upload",
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
    assert (
        hass.states.get(f"{sensor.DOMAIN}.{obj_prefix}_devices_connected").state == "2"
    )
    assert (
        hass.states.get(f"{sensor.DOMAIN}.{obj_prefix}_download_speed").state == "160.0"
    )
    assert hass.states.get(f"{sensor.DOMAIN}.{obj_prefix}_download").state == "60.0"
    assert hass.states.get(f"{sensor.DOMAIN}.{obj_prefix}_upload_speed").state == "80.0"
    assert hass.states.get(f"{sensor.DOMAIN}.{obj_prefix}_upload").state == "50.0"

    # add one device and remove another
    MOCK_DEVICES.pop("a1:b1:c1:d1:e1:f1")
    MOCK_DEVICES["a3:b3:c3:d3:e3:f3"] = Device(
        "a3:b3:c3:d3:e3:f3", "192.168.1.4", "TestThree"
    )
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done()

    assert hass.states.get(f"{device_tracker.DOMAIN}.test").state == STATE_NOT_HOME
    assert hass.states.get(f"{device_tracker.DOMAIN}.testtwo").state == STATE_HOME
    assert hass.states.get(f"{device_tracker.DOMAIN}.testthree").state == STATE_HOME
    assert (
        hass.states.get(f"{sensor.DOMAIN}.{obj_prefix}_devices_connected").state == "2"
    )

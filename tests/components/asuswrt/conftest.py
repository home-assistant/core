"""Fixtures for Asuswrt component."""

from datetime import datetime
from unittest.mock import Mock, patch

from aioasuswrt.asuswrt import AsusWrt as AsusWrtLegacy
from aioasuswrt.connection import TelnetConnection
from asusrouter import AsusRouter, AsusRouterError
from asusrouter.modules.data import AsusData
from asusrouter.modules.identity import AsusDevice
import pytest

from homeassistant.components.asuswrt.bridge import WrtDevice
from homeassistant.components.asuswrt.const import PROTOCOL_HTTP, PROTOCOL_SSH

from .common import ASUSWRT_BASE, HOST, MOCK_MACS, ROUTER_MAC_ADDR, new_device

ASUSWRT_HTTP_LIB = f"{ASUSWRT_BASE}.bridge.AsusRouter"
ASUSWRT_LEGACY_LIB = f"{ASUSWRT_BASE}.bridge.create_connection_aioasuswrt"

MOCK_BYTES_TOTAL = {"rx": 60000000000, "tx": 50000000000}
MOCK_BYTES_TOTAL_HTTP = dict(enumerate(MOCK_BYTES_TOTAL))
MOCK_CPU_USAGE = {
    "cpu1_usage": 0.1,
    "cpu2_usage": 0.2,
    "cpu3_usage": 0.3,
    "cpu4_usage": 0.4,
    "cpu5_usage": 0.5,
    "cpu6_usage": 0.6,
    "cpu7_usage": 0.7,
    "cpu8_usage": 0.8,
    "cpu_total_usage": 0.9,
}
MOCK_CURRENT_TRANSFER_RATES = {"rx": 20000000, "tx": 10000000}
MOCK_CURRENT_TRANSFER_RATES_HTTP = dict(enumerate(MOCK_CURRENT_TRANSFER_RATES))
# Mock for AsusData.NETWORK return of both rates and total bytes
MOCK_CURRENT_NETWORK = {
    "sensor_rx_rates": MOCK_CURRENT_TRANSFER_RATES["rx"] * 8,  # AR works with bits
    "sensor_tx_rates": MOCK_CURRENT_TRANSFER_RATES["tx"] * 8,  # AR works with bits
    "sensor_rx_bytes": MOCK_BYTES_TOTAL["rx"],
    "sensor_tx_bytes": MOCK_BYTES_TOTAL["tx"],
}
MOCK_LOAD_AVG = {
    "sensor_load_avg1": 1.1,
    "sensor_load_avg5": 1.2,
    "sensor_load_avg15": 1.3,
}
MOCK_MEMORY_USAGE = {
    "mem_usage_perc": 52.4,
    "mem_total": 1048576,
    "mem_free": 393216,
    "mem_used": 655360,
}
MOCK_TEMPERATURES = {"2.4GHz": 40.2, "5.0GHz": 62, "CPU": 71.2}
MOCK_TEMPERATURES_HTTP = {**MOCK_TEMPERATURES, "5.0GHz_2": 40.3, "6.0GHz": 40.4}
MOCK_UPTIME = {"last_boot": "2024-08-02T00:47:00+00:00", "uptime": 1625927}
MOCK_BOOTTIME = {
    "sensor_last_boot": datetime.fromisoformat(MOCK_UPTIME["last_boot"]),
    "sensor_uptime": MOCK_UPTIME["uptime"],
}


@pytest.fixture(name="patch_setup_entry")
def mock_controller_patch_setup_entry():
    """Mock setting up a config entry."""
    with patch(
        f"{ASUSWRT_BASE}.async_setup_entry", return_value=True
    ) as setup_entry_mock:
        yield setup_entry_mock


def _mock_devices(protocol: str) -> dict[str, WrtDevice]:
    """Mock devices."""
    return {
        MOCK_MACS[0]: new_device(
            protocol, MOCK_MACS[0], "192.168.1.2", "Test", "node1"
        ),
        MOCK_MACS[1]: new_device(
            protocol, MOCK_MACS[1], "192.168.1.3", "TestTwo", "node2"
        ),
    }


@pytest.fixture(name="mock_devices_http")
def mock_devices_http_fixture() -> dict[str, WrtDevice]:
    """Mock a list of AsusRouter client devices for HTTP backend."""
    return _mock_devices(PROTOCOL_HTTP)


@pytest.fixture(name="mock_devices_legacy")
def mock_devices_legacy_fixture() -> dict[str, WrtDevice]:
    """Mock a list of AsusRouter client devices for SSH backend."""
    return _mock_devices(PROTOCOL_SSH)


@pytest.fixture(name="connect_legacy")
def mock_controller_connect_legacy(mock_devices_legacy):
    """Mock a successful connection with legacy library."""
    with patch(ASUSWRT_LEGACY_LIB, autospec=AsusWrtLegacy) as service_mock:
        service_mock.return_value._connection = Mock(spec=TelnetConnection)
        service_mock.return_value.is_connected = True
        service_mock.return_value.get_nvram.return_value = {
            "label_mac": ROUTER_MAC_ADDR,
            "model": "abcd",
            "firmver": "efg",
            "buildno": "123",
        }
        service_mock.return_value.get_connected_devices.return_value = (
            mock_devices_legacy
        )
        service_mock.return_value.total_transfer.return_value = MOCK_BYTES_TOTAL
        service_mock.return_value.get_current_transfer_rates.return_value = (
            MOCK_CURRENT_TRANSFER_RATES
        )
        service_mock.return_value.get_loadavg.return_value = MOCK_LOAD_AVG
        service_mock.return_value.get_temperature.return_value = MOCK_TEMPERATURES
        yield service_mock


@pytest.fixture(name="connect_http")
def mock_controller_connect_http(mock_devices_http):
    """Mock a successful connection with http library."""
    with patch(ASUSWRT_HTTP_LIB, spec_set=AsusRouter) as service_mock:
        instance = service_mock.return_value

        # Simulate connection status
        instance.connected = True

        # Set the webpanel address
        instance.webpanel = f"http://{HOST}:80"

        # Identity
        instance.async_get_identity.return_value = AsusDevice(
            mac=ROUTER_MAC_ADDR,
            model="FAKE_MODEL",
            firmware="FAKE_FIRMWARE",
        )

        # Data fetches via async_get_data
        instance.async_get_data.side_effect = lambda datatype, *args, **kwargs: {
            AsusData.CLIENTS: mock_devices_http,
            AsusData.NETWORK: MOCK_CURRENT_NETWORK,
            AsusData.SYSINFO: MOCK_LOAD_AVG,
            AsusData.TEMPERATURE: {
                k: v for k, v in MOCK_TEMPERATURES_HTTP.items() if k != "5.0GHz"
            },
            AsusData.CPU: MOCK_CPU_USAGE,
            AsusData.RAM: MOCK_MEMORY_USAGE,
            AsusData.BOOTTIME: MOCK_BOOTTIME,
        }[datatype]

        yield service_mock


def make_async_get_data_side_effect(fail_types=None):
    """Return a side effect for async_get_data that fails for specified AsusData types."""
    fail_types = set(fail_types or [])

    def side_effect(datatype, *args, **kwargs):
        if datatype in fail_types:
            raise AsusRouterError(f"{datatype} unavailable")
        # Return valid mock data for other types
        if datatype == AsusData.CLIENTS:
            return {}
        if datatype == AsusData.NETWORK:
            return {}
        if datatype == AsusData.SYSINFO:
            return {}
        if datatype == AsusData.TEMPERATURE:
            return {}
        if datatype == AsusData.CPU:
            return {}
        if datatype == AsusData.RAM:
            return {}
        if datatype == AsusData.BOOTTIME:
            return {}
        return {}

    return side_effect


@pytest.fixture(name="connect_http_sens_fail")
def mock_controller_connect_http_sens_fail(connect_http):
    """Universal fixture to fail specified AsusData types."""

    def _set_fail_types(fail_types):
        connect_http.return_value.async_get_data.side_effect = (
            make_async_get_data_side_effect(fail_types)
        )
        return connect_http

    return _set_fail_types


@pytest.fixture(name="connect_http_sens_detect")
def mock_controller_connect_http_sens_detect():
    """Mock a successful sensor detection using http library."""

    async def _get_sensors_side_effect(datatype):
        if datatype == AsusData.TEMPERATURE:
            return list(MOCK_TEMPERATURES_HTTP)
        if datatype == AsusData.CPU:
            return list(MOCK_CPU_USAGE)
        if datatype == AsusData.SYSINFO:
            return list(MOCK_LOAD_AVG)
        return []

    with patch(
        f"{ASUSWRT_BASE}.bridge.AsusWrtHttpBridge._get_sensors",
        side_effect=_get_sensors_side_effect,
    ) as mock_sens_detect:
        yield mock_sens_detect

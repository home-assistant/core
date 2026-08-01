"""Test fixtures for the Netis Router integration.

All tests run inside the Home Assistant test framework: the router is
always mocked, no real HTTP traffic is generated.

The raw sample payloads below mirror the response format verified against
a real MW5630 running firmware 4.0.260701.100631.
"""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.netis.api import NetisClient, NetisData
from homeassistant.components.netis.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

# ---------------------------------------------------------------------------
# Sample raw API responses (matching real router firmware output format)
# ---------------------------------------------------------------------------

SAMPLE_SYSTEM_INFO = {
    "model": "MW5630",
    "version": "4.0.260701.100631",
    "hd_version": "1.0",
    "meminfo": "256M",
    "wifispeed": "3000Mbps",
    "uptime": 3600,
    "all_in_byte": 1024000,
    "all_out_byte": 2048000,
    "all_in_byte_speed": 51200,
    "all_out_byte_speed": 102400,
    "all_in_pkt": 10000,
    "all_out_pkt": 20000,
    "link_info": [
        {"name": "PORT0", "link": False, "speed": 0, "duplex": "half"},
        {"name": "PORT1", "link": True, "speed": 1000, "duplex": "full"},
        {"name": "PORT2", "link": False, "speed": 0, "duplex": "half"},
    ],
    "priority1": "wan_lte",
    "priority2": "wan1",
}

SAMPLE_HOSTS = {
    "hosts": [
        {
            "mac": "AA:BB:CC:DD:EE:FF",
            "alias": "test-laptop",
            "ip": "192.168.1.100",
            "ip6": "::",
            "online": True,
            "wire": True,
            "is_wifi": 0,
            "is_5g": 0,
            "is_guest": 0,
            "up_speed": 1024,
            "down_speed": 4096,
            "up_bytes": 500000,
            "down_bytes": 1500000,
            "second": 1800,
        },
        {
            "mac": "11:22:33:44:55:66",
            "alias": "test-phone",
            "ip": "192.168.1.101",
            "online": True,
            "wire": False,
            "is_wifi": 0,
            "is_5g": 1,
            "is_guest": 0,
            "up_speed": 512,
            "down_speed": 2048,
            "up_bytes": 100000,
            "down_bytes": 800000,
            "second": 600,
        },
        {
            "mac": "99:88:77:66:55:44",
            "alias": "offline-device",
            "ip": "",
            "online": False,
            "wire": False,
            "is_wifi": 1,
            "is_5g": 0,
            "is_guest": 0,
            "up_speed": 0,
            "down_speed": 0,
            "up_bytes": 0,
            "down_bytes": 0,
            "second": 0,
        },
    ]
}

SAMPLE_MWAN3 = {
    "interfaces": {
        "wan1": {"status": "offline"},
        "wan1_ipv6": {"status": "offline"},
        "wan_lte": {"status": "online"},
    }
}

SAMPLE_LTE_INFO = {
    "support4G": "1",
    "lte_sim": 1,
    "lte_module": 8,
    "imei": "868245050137472",
    "lte_imsi": "460110503549231",
    "lte_isp": "CHN-CT",
    "lte_mode": "LTE",
    "lte_connect": 1,
    "lte_ip": "10.99.249.101",
    "lte_dns1": "61.139.2.69",
    "lte_dns2": "218.6.200.139",
    "lte_rsrp": "-95.5",
    "lte_rsrq": "-12.3",
    "lte_rssi": "28",
    "lte_band": "103",
    "lte_cellid": "8112",
}

SAMPLE_WIFI_CONFIG = {
    "values": {
        "global": {"Enable": "1"},
        "2G": {
            "Enable": "1",
            "SSID1": "netis-test-2G",
            "TxPower": "100",
            "Channel": "0",
        },
        "5G": {
            "Enable": "1",
            "SSID1": "netis-test-5G",
            "TxPower": "50",
            "Channel": "0",
        },
    }
}

VALID_TOKEN = "aabbccddeeff00112233445566778899"
# 64 hex chars: first 32 = key_index, last 32 = 16-byte AES key.
RAND_KEY = "aabbccddeeff00112233445566778899aabbccddeeff00112233445566778899"


def build_netis_data() -> NetisData:
    """Return a fully-populated parsed NetisData snapshot (LEDs on)."""
    return NetisClient.parse(
        info=SAMPLE_SYSTEM_INFO,
        hosts=SAMPLE_HOSTS,
        mwan=SAMPLE_MWAN3,
        lte=SAMPLE_LTE_INFO,
        wifi=SAMPLE_WIFI_CONFIG,
        ledoff="0",
    )


# ---------------------------------------------------------------------------
# Mock config entry
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock Netis config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Netis 192.168.1.1",
        data={CONF_HOST: "192.168.1.1", CONF_PASSWORD: "password"},
        options={"scan_interval": 30},
        entry_id="1",
        unique_id="192.168.1.1",
    )


# ---------------------------------------------------------------------------
# Mock NetisClient (patched at the coordinator import site)
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_netis_client() -> Generator[MagicMock]:
    """Yield a mocked NetisClient and prevent any real HTTP traffic.

    Patches ``NetisClient`` at both the coordinator and config_flow import
    sites so setup and connection tests share the same mock.
    """
    data = build_netis_data()
    with patch(
        "homeassistant.components.netis.coordinator.NetisClient",
        autospec=True,
    ) as client_class, patch(
        "homeassistant.components.netis.config_flow.NetisClient",
        autospec=True,
    ):
        client = client_class.return_value
        client.login = AsyncMock(return_value=VALID_TOKEN)
        client.gather = AsyncMock(return_value=data)
        client.get_system_info = AsyncMock(return_value=SAMPLE_SYSTEM_INFO)
        client.set_wifi_config = AsyncMock(return_value=None)
        client.set_led = AsyncMock(return_value=None)
        client.reboot = AsyncMock(return_value=None)
        client.send_sms = AsyncMock(return_value=None)
        client.set_speed_limit = AsyncMock(return_value=None)
        yield client


# ---------------------------------------------------------------------------
# Initialise the integration (full setup via the config entry)
# ---------------------------------------------------------------------------

@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_netis_client: MagicMock,
) -> MockConfigEntry:
    """Set up the Netis integration with a mocked router.

    Yields the config entry after a successful first refresh.
    """
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry

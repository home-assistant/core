"""Tests for the Netis API client (homeassistant.components.netis.api).

These tests verify internal logic -- password encryption, data parsing and
type conversion -- without making any real HTTP requests and without the
HA framework (pure unit tests).
"""

from __future__ import annotations

import pytest

from homeassistant.components.netis.api import (
    NetisClient,
    _encrypt_password,
)

from .conftest import (
    RAND_KEY,
    SAMPLE_HOSTS,
    SAMPLE_LTE_INFO,
    SAMPLE_MWAN3,
    SAMPLE_SYSTEM_INFO,
    SAMPLE_WIFI_CONFIG,
)


# ===========================================================================
# Password encryption
# ===========================================================================

class TestEncryptPassword:
    """Tests for _encrypt_password()."""

    def test_encrypt_produces_hex_string(self):
        """Output must be hex with the key_index prefix."""
        result = _encrypt_password("secret", RAND_KEY)
        assert isinstance(result, str)
        # key_index (32 hex) + at least one AES block (32 hex)
        assert len(result) >= 64
        assert result[:32] == RAND_KEY[:32]

    def test_encrypt_empty_password(self):
        """Empty password must still produce valid encrypted output."""
        result = _encrypt_password("", RAND_KEY)
        assert isinstance(result, str)
        assert len(result) >= 64

    def test_encrypt_different_passwords_differ(self):
        """Different passwords must produce different ciphertexts."""
        enc1 = _encrypt_password("password1", RAND_KEY)
        enc2 = _encrypt_password("password2", RAND_KEY)
        assert enc1[:32] == enc2[:32]  # key_index prefix identical
        assert enc1[32:] != enc2[32:]  # ciphertext differs


# ===========================================================================
# Data parsing (NetisClient.parse classmethod)
# ===========================================================================

class TestParse:
    """Tests for NetisClient.parse()."""

    def test_parse_full_data(self):
        """All fields parsed from a complete, valid raw payload."""
        data = NetisClient.parse(
            info=SAMPLE_SYSTEM_INFO,
            hosts=SAMPLE_HOSTS,
            mwan=SAMPLE_MWAN3,
            lte=SAMPLE_LTE_INFO,
            wifi=SAMPLE_WIFI_CONFIG,
            ledoff="0",
        )
        # System
        assert data.model == "MW5630"
        assert data.firmware == "4.0.260701.100631"
        assert data.hardware_version == "1.0"
        assert data.uptime == 3600
        assert data.wan_in_speed == 51200
        assert data.wan_out_speed == 102400
        # WAN
        assert data.wan_online is True
        assert data.wan_interfaces["wan_lte"] == "online"
        assert data.wan_interfaces["wan1"] == "offline"
        # LTE
        assert data.lte_connected is True
        assert data.lte_rsrp == pytest.approx(-95.5)
        assert data.lte_rsrq == pytest.approx(-12.3)
        assert data.lte_rssi == pytest.approx(28.0)
        assert data.lte_mode == "LTE"
        assert data.lte_isp == "CHN-CT"
        assert data.lte_ip == "10.99.249.101"
        assert data.lte_imei == "868245050137472"
        # WiFi
        assert data.wifi_enabled["2G"] is True
        assert data.wifi_enabled["5G"] is True
        assert data.wifi_txpower["2G"] == "100"
        assert data.wifi_txpower["5G"] == "50"
        # LED
        assert data.led_on is True

    def test_parse_devices(self):
        """The device list is parsed with correct connection attributes."""
        data = NetisClient.parse(
            SAMPLE_SYSTEM_INFO, SAMPLE_HOSTS, SAMPLE_MWAN3, SAMPLE_LTE_INFO
        )
        assert len(data.devices) == 3
        wired = data.devices[0]
        assert wired.mac == "AA:BB:CC:DD:EE:FF"
        assert wired.name == "test-laptop"
        assert wired.ip == "192.168.1.100"
        assert wired.online is True
        assert wired.wired is True
        assert wired.wifi_5g is False

        wifi5 = data.devices[1]
        assert wifi5.wifi_5g is True
        assert wifi5.wired is False

        offline = data.devices[2]
        assert offline.online is False

    def test_parse_led_off(self):
        """ledoff='1' means LEDs off."""
        data = NetisClient.parse(
            SAMPLE_SYSTEM_INFO, SAMPLE_HOSTS, SAMPLE_MWAN3,
            SAMPLE_LTE_INFO, ledoff="1",
        )
        assert data.led_on is False

    def test_parse_wifi_disabled(self):
        """WiFi Enable='0' parses as disabled for both bands."""
        wifi_disabled = {
            "values": {
                "2G": {"Enable": "0", "TxPower": "50"},
                "5G": {"Enable": "0", "TxPower": "50"},
            }
        }
        data = NetisClient.parse(
            SAMPLE_SYSTEM_INFO, SAMPLE_HOSTS, SAMPLE_MWAN3,
            SAMPLE_LTE_INFO, wifi=wifi_disabled,
        )
        assert data.wifi_enabled["2G"] is False
        assert data.wifi_enabled["5G"] is False

    def test_parse_wan_offline(self):
        """All WAN interfaces offline means wan_online is False."""
        mwan_offline = {
            "interfaces": {
                "wan1": {"status": "offline"},
                "wan_lte": {"status": "offline"},
            }
        }
        data = NetisClient.parse(
            SAMPLE_SYSTEM_INFO, SAMPLE_HOSTS, mwan_offline, SAMPLE_LTE_INFO
        )
        assert data.wan_online is False

    def test_parse_empty_hosts(self):
        """An empty host list yields an empty device list."""
        data = NetisClient.parse(
            SAMPLE_SYSTEM_INFO, {"hosts": []}, SAMPLE_MWAN3, SAMPLE_LTE_INFO
        )
        assert data.devices == []

    def test_parse_missing_mac_skipped(self):
        """Hosts without a MAC address are skipped."""
        hosts = {
            "hosts": [
                {"ip": "192.168.1.1", "mac": ""},
                {"mac": "AA:BB:CC:DD:EE:FF"},
            ]
        }
        data = NetisClient.parse(
            SAMPLE_SYSTEM_INFO, hosts, SAMPLE_MWAN3, SAMPLE_LTE_INFO
        )
        assert len(data.devices) == 1

    def test_parse_lte_not_connected(self):
        """lte_connect=0 means not connected."""
        lte = {**SAMPLE_LTE_INFO, "lte_connect": 0}
        data = NetisClient.parse(
            SAMPLE_SYSTEM_INFO, SAMPLE_HOSTS, SAMPLE_MWAN3, lte
        )
        assert data.lte_connected is False

    def test_parse_handles_empty_inputs(self):
        """Parse must not crash on empty/None-shaped inputs."""
        data = NetisClient.parse({}, {}, {}, {})
        assert data.model is None
        assert data.devices == []
        assert data.wan_online is False
        assert data.led_on is None


# ===========================================================================
# Type conversion helpers
# ===========================================================================

class TestTypeConversion:
    """Tests for _to_int and _to_float helpers."""

    def test_to_int_valid(self):
        assert NetisClient._to_int("100") == 100
        assert NetisClient._to_int(100) == 100
        assert NetisClient._to_int("100.5") == 100

    def test_to_int_invalid(self):
        assert NetisClient._to_int("abc") is None
        assert NetisClient._to_int(None) is None

    def test_to_float_valid(self):
        assert NetisClient._to_float("-95.5") == pytest.approx(-95.5)
        assert NetisClient._to_float(100) == pytest.approx(100.0)

    def test_to_float_invalid(self):
        assert NetisClient._to_float("abc") is None
        assert NetisClient._to_float(None) is None

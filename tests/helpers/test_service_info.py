"""Test service_info helpers."""

import pytest

from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.service_info.esphome import ESPHomeServiceInfo

# Ensure that incorrectly formatted mac addresses are rejected, even
# on a constant outside of a test
try:
    _ = DhcpServiceInfo(ip="", hostname="", macaddress="AA:BB:CC:DD:EE:FF")
except ValueError:
    pass
else:
    raise RuntimeError(
        "DhcpServiceInfo incorrectly formatted mac address was not rejected. "
        "Please ensure that the DhcpServiceInfo is correctly patched."
    )


def test_invalid_macaddress() -> None:
    """Test that DhcpServiceInfo raises ValueError for unformatted macaddress."""
    with pytest.raises(ValueError):
        DhcpServiceInfo(ip="", hostname="", macaddress="AA:BB:CC:DD:EE:FF")


def test_esphome_socket_path() -> None:
    """Test ESPHomeServiceInfo socket_path property."""
    info = ESPHomeServiceInfo(
        name="Hello World",
        zwave_home_id=123456789,
        ip_address="192.168.1.100",
        port=6053,
    )
    assert info.socket_path == "esphome://192.168.1.100:6053"
    info.noise_psk = "my-noise-psk"
    assert info.socket_path == "esphome://my-noise-psk@192.168.1.100:6053"

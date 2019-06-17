"""Test homeassistant network utility functions."""
from typing import Optional
from unittest.mock import patch

import pytest

import homeassistant.util.network as network_util


@pytest.mark.parametrize("ip_address, stdout, mac_address", [
    # net-tools 2.10-alpha
    ("192.168.1.1",
     b"""\
Address                  HWtype  HWaddress           Flags Mask           Iface
192.168.1.1              ether   de:ad:be:ef:42:42   C                    eth1
""",
     "de:ad:be:ef:42:42"),
    ("192.168.1.1",
     b"192.168.1.1 (192.168.1.1) -- no entry\n",
     None),
    # busybox v1.29.3
    ("192.168.1.1",
     b"? (192.168.1.1) at de:ad:be:ef:42:42 [ether]  on eth0\n",
     "de:ad:be:ef:42:42"),
    ("192.168.1.1",
     b"No match found in 2 entries\n",
     None),
])
def test_get_mac_address(
        ip_address: str, stdout: bytes, mac_address: Optional[str]) -> None:
    """Test MAC address parsing from arp output."""
    with patch("homeassistant.util.network.subprocess") as subprocess:
        subprocess.run.return_value.stdout = stdout
        assert network_util.get_mac_address(ip_address) == mac_address

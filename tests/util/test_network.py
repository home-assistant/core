"""Test Home Assistant volume utility functions."""

from ipaddress import ip_address

import homeassistant.util.network as network_util


def test_is_loopback():
    """Test loopback addresses."""
    assert network_util.is_loopback(ip_address("127.0.0.2"))
    assert network_util.is_loopback(ip_address("127.0.0.1"))
    assert network_util.is_loopback(ip_address("::1"))
    assert network_util.is_loopback(ip_address("::ffff:127.0.0.0"))
    assert network_util.is_loopback(ip_address("0:0:0:0:0:0:0:1"))
    assert network_util.is_loopback(ip_address("0:0:0:0:0:ffff:7f00:1"))
    assert not network_util.is_loopback(ip_address("104.26.5.238"))
    assert not network_util.is_loopback(ip_address("2600:1404:400:1a4::356e"))


def test_is_private():
    """Test private addresses."""
    assert network_util.is_private(ip_address("192.168.0.1"))
    assert network_util.is_private(ip_address("172.16.12.0"))
    assert network_util.is_private(ip_address("10.5.43.3"))
    assert network_util.is_private(ip_address("fd12:3456:789a:1::1"))
    assert not network_util.is_private(ip_address("127.0.0.1"))
    assert not network_util.is_private(ip_address("::1"))


def test_is_link_local():
    """Test link local addresses."""
    assert network_util.is_link_local(ip_address("169.254.12.3"))
    assert not network_util.is_link_local(ip_address("127.0.0.1"))


def test_is_local():
    """Test local addresses."""
    assert network_util.is_local(ip_address("192.168.0.1"))
    assert network_util.is_local(ip_address("127.0.0.1"))
    assert not network_util.is_local(ip_address("208.5.4.2"))

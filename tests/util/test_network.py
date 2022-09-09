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
    assert network_util.is_link_local(ip_address("fe80::1234:5678:abcd"))
    assert not network_util.is_link_local(ip_address("127.0.0.1"))
    assert not network_util.is_link_local(ip_address("::1"))


def test_is_invalid():
    """Test invalid address."""
    assert network_util.is_invalid(ip_address("0.0.0.0"))
    assert not network_util.is_invalid(ip_address("127.0.0.1"))


def test_is_local():
    """Test local addresses."""
    assert network_util.is_local(ip_address("192.168.0.1"))
    assert network_util.is_local(ip_address("127.0.0.1"))
    assert network_util.is_local(ip_address("fd12:3456:789a:1::1"))
    assert network_util.is_local(ip_address("fe80::1234:5678:abcd"))
    assert network_util.is_local(ip_address("::ffff:192.168.0.1"))
    assert not network_util.is_local(ip_address("208.5.4.2"))
    assert not network_util.is_local(ip_address("198.51.100.1"))
    assert not network_util.is_local(ip_address("2001:DB8:FA1::1"))
    assert not network_util.is_local(ip_address("::ffff:208.5.4.2"))


def test_is_ip_address():
    """Test if strings are IP addresses."""
    assert network_util.is_ip_address("192.168.0.1")
    assert network_util.is_ip_address("8.8.8.8")
    assert network_util.is_ip_address("::ffff:127.0.0.0")
    assert not network_util.is_ip_address("192.168.0.999")
    assert not network_util.is_ip_address("192.168.0.0/24")
    assert not network_util.is_ip_address("example.com")


def test_is_ipv4_address():
    """Test if strings are IPv4 addresses."""
    assert network_util.is_ipv4_address("192.168.0.1") is True
    assert network_util.is_ipv4_address("8.8.8.8") is True
    assert network_util.is_ipv4_address("192.168.0.999") is False
    assert network_util.is_ipv4_address("192.168.0.0/24") is False
    assert network_util.is_ipv4_address("example.com") is False


def test_is_ipv6_address():
    """Test if strings are IPv6 addresses."""
    assert network_util.is_ipv6_address("::1") is True
    assert network_util.is_ipv6_address("8.8.8.8") is False
    assert network_util.is_ipv6_address("8.8.8.8") is False


def test_normalize_url():
    """Test the normalizing of URLs."""
    assert network_util.normalize_url("http://example.com") == "http://example.com"
    assert network_util.normalize_url("https://example.com") == "https://example.com"
    assert network_util.normalize_url("https://example.com/") == "https://example.com"
    assert (
        network_util.normalize_url("https://example.com:443") == "https://example.com"
    )
    assert network_util.normalize_url("http://example.com:80") == "http://example.com"
    assert (
        network_util.normalize_url("https://example.com:80") == "https://example.com:80"
    )
    assert (
        network_util.normalize_url("http://example.com:443") == "http://example.com:443"
    )
    assert (
        network_util.normalize_url("https://example.com:443/test/")
        == "https://example.com/test"
    )
    assert network_util.normalize_url("/test/") == "/test"

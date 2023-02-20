"""Test Home Assistant volume utility functions."""

from ipaddress import ip_address

import homeassistant.util.network as network_util


def test_is_loopback() -> None:
    """Test loopback addresses."""
    assert network_util.is_loopback(ip_address("127.0.0.2"))
    assert network_util.is_loopback(ip_address("127.0.0.1"))
    assert network_util.is_loopback(ip_address("::1"))
    assert network_util.is_loopback(ip_address("::ffff:127.0.0.0"))
    assert network_util.is_loopback(ip_address("0:0:0:0:0:0:0:1"))
    assert network_util.is_loopback(ip_address("0:0:0:0:0:ffff:7f00:1"))
    assert not network_util.is_loopback(ip_address("104.26.5.238"))
    assert not network_util.is_loopback(ip_address("2600:1404:400:1a4::356e"))


def test_is_private() -> None:
    """Test private addresses."""
    assert network_util.is_private(ip_address("192.168.0.1"))
    assert network_util.is_private(ip_address("172.16.12.0"))
    assert network_util.is_private(ip_address("10.5.43.3"))
    assert network_util.is_private(ip_address("fd12:3456:789a:1::1"))
    assert not network_util.is_private(ip_address("127.0.0.1"))
    assert not network_util.is_private(ip_address("::1"))


def test_is_link_local() -> None:
    """Test link local addresses."""
    assert network_util.is_link_local(ip_address("169.254.12.3"))
    assert network_util.is_link_local(ip_address("fe80::1234:5678:abcd"))
    assert not network_util.is_link_local(ip_address("127.0.0.1"))
    assert not network_util.is_link_local(ip_address("::1"))


def test_is_invalid() -> None:
    """Test invalid address."""
    assert network_util.is_invalid(ip_address("0.0.0.0"))
    assert not network_util.is_invalid(ip_address("127.0.0.1"))


def test_is_local() -> None:
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


def test_is_ip_address() -> None:
    """Test if strings are IP addresses."""
    assert network_util.is_ip_address("192.168.0.1")
    assert network_util.is_ip_address("8.8.8.8")
    assert network_util.is_ip_address("::ffff:127.0.0.0")
    assert not network_util.is_ip_address("192.168.0.999")
    assert not network_util.is_ip_address("192.168.0.0/24")
    assert not network_util.is_ip_address("example.com")


def test_is_ipv4_address() -> None:
    """Test if strings are IPv4 addresses."""
    assert network_util.is_ipv4_address("192.168.0.1") is True
    assert network_util.is_ipv4_address("8.8.8.8") is True
    assert network_util.is_ipv4_address("192.168.0.999") is False
    assert network_util.is_ipv4_address("192.168.0.0/24") is False
    assert network_util.is_ipv4_address("example.com") is False


def test_is_ipv6_address() -> None:
    """Test if strings are IPv6 addresses."""
    assert network_util.is_ipv6_address("::1") is True
    assert network_util.is_ipv6_address("8.8.8.8") is False
    assert network_util.is_ipv6_address("8.8.8.8") is False


def test_is_valid_host() -> None:
    """Test if strings are IPv6 addresses."""
    assert network_util.is_host_valid("::1")
    assert network_util.is_host_valid("::ffff:127.0.0.0")
    assert network_util.is_host_valid("2001:0db8:85a3:0000:0000:8a2e:0370:7334")
    assert network_util.is_host_valid("8.8.8.8")
    assert network_util.is_host_valid("local")
    assert network_util.is_host_valid("host-host")
    assert network_util.is_host_valid("example.com")
    assert network_util.is_host_valid("example.com.")
    assert network_util.is_host_valid("Example123.com")
    assert not network_util.is_host_valid("")
    assert not network_util.is_host_valid("192.168.0.1:8080")
    assert not network_util.is_host_valid("192.168.0.999")
    assert not network_util.is_host_valid("2001:hb8::1:0:0:1")
    assert not network_util.is_host_valid("-host-host")
    assert not network_util.is_host_valid("host-host-")
    assert not network_util.is_host_valid("host_host")
    assert not network_util.is_host_valid("example.com/path")
    assert not network_util.is_host_valid("example.com:8080")
    assert not network_util.is_host_valid("verylonghostname" * 4)
    assert not network_util.is_host_valid("verydeepdomain." * 18)


def test_normalize_url() -> None:
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

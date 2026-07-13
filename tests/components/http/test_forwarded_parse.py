"""Tests for parsing forwarded-for addresses using urlsplit + ip_address."""

from ipaddress import ip_address
from urllib.parse import urlsplit

import pytest


@pytest.mark.parametrize(
    ("addr", "expected"),
    [
        ("1.2.3.4", "1.2.3.4"),
        ("1.2.3.4:1234", "1.2.3.4"),
        ("127.0.0.1:80", "127.0.0.1"),
        ("[2001:db8::1]:1234", "2001:db8::1"),
        ("[2001:db8::1]", "2001:db8::1"),
        ("2001:db8::1", "2001:db8::1"),
        ("::1", "::1"),
        (" [::1]:8080 ", "::1"),
        (" 1.2.3.4:1234 ", "1.2.3.4"),
    ],
)
def test_urlsplit_hostname_or_raw_accepts_valid_ips(addr: str, expected: str) -> None:
    """The expression extracts the host and validates it with ip_address."""
    host = urlsplit("//" + addr.strip()).hostname or addr.strip()
    assert str(ip_address(host)) == expected


@pytest.mark.parametrize("addr", ["", "not-an-ip", "garbage:123"])
def test_urlsplit_hostname_or_raw_raises_on_invalid(addr: str) -> None:
    """Invalid or empty inputs should raise ValueError from ip_address."""
    host = urlsplit("//" + addr.strip()).hostname or addr.strip()
    with pytest.raises(ValueError):
        ip_address(host)

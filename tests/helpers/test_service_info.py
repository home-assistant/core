"""Test service_info helpers."""

import pytest

from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

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

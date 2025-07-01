"""Test service_info helpers."""

from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

# Ensure that DhcpServiceInfo.__post_init__ is called, even on a constant outside of a test
try:
    _ = DhcpServiceInfo(ip="", hostname="", macaddress="AA:BB:CC:DD:EE:FF")
except ValueError:
    pass
else:
    raise RuntimeError(
        "DhcpServiceInfo.__post_init__ was not called. "
        "Please ensure that the __post_init__ method is correctly defined."
    )

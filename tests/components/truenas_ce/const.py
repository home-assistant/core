"""Test data for the TrueNAS integration."""

from datetime import UTC, datetime

from aiotruenas import InterfaceTraffic, NetworkInterface, SystemInfo, SystemStats

SYSTEM_ID = "a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d"

SYSTEM_INFO = SystemInfo(
    hostname="truenas",
    version="25.10.1",
    manufacturer="iXsystems",
    product="TRUENAS-MINI-3.0-XL+",
    serial="A1-123456",
    physical_memory=34359738368,
    boot_time=datetime(2026, 11, 1, 8, 0, tzinfo=UTC),
    uptime_seconds=432000.0,
    load_1m=0.42,
    load_5m=0.36,
    load_15m=0.31,
    is_virtual=False,
)


def make_interface(interface_id: str, *, link_up: bool | None) -> NetworkInterface:
    """Return a network interface."""
    return NetworkInterface(
        id=interface_id,
        name=interface_id,
        description="",
        mtu=1500,
        link_state="LINK_STATE_UP" if link_up else "LINK_STATE_DOWN",
        link_up=link_up,
        active_media_type="Ethernet",
        active_media_subtype="1000Mb/s Twisted Pair",
        link_address="00:11:22:33:44:55",
    )


NETWORK_INTERFACES = {
    "eno1": make_interface("eno1", link_up=True),
    # A down link gets no traffic sensors until it comes up.
    "eno2": make_interface("eno2", link_up=False),
}

SYSTEM_STATS = SystemStats(
    cpu_usage_percent=7.5,
    cpu_temperature=41.0,
    memory_available=12884901888,
    memory_usage_percent=62.5,
    arc_size=17179869184,
    interfaces={
        "eno1": InterfaceTraffic(rx_kbps=1234.5, tx_kbps=456.7),
        "eno2": InterfaceTraffic(rx_kbps=0.0, tx_kbps=0.0),
    },
)

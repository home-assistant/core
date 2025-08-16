"""Provides reusable functionality for generating consistent device information."""

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN


def device_unique_id(data) -> str:
    """Get unique_id for the device."""
    return data["sysinfo"].macAddr or data["sysinfo"].wirelessMacAddr


def device_info(name, data) -> DeviceInfo:
    """Get DeviceInfo for the device."""
    connections = set()
    if data["sysinfo"].macAddr:
        connections.add((dr.CONNECTION_NETWORK_MAC, data["sysinfo"].macAddr))
    if data["sysinfo"].wirelessMacAddr:
        connections.add((dr.CONNECTION_NETWORK_MAC, data["sysinfo"].wirelessMacAddr))
    return DeviceInfo(
        connections=connections,
        identifiers={(DOMAIN, device_unique_id(data))},
        manufacturer="Sony Corporation",
        model=data["interface_info"].modelName,
        name=name,
        sw_version=data["sysinfo"].version,
    )

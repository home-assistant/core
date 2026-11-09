"""Typings for the xiaomi_miio integration."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from miio import Device as MiioDevice
from miio.gateway.gateway import Gateway

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

if TYPE_CHECKING:
    from .coordinator import GatewayDeviceCoordinator


@dataclass
class XiaomiMiioRuntimeData:
    """Runtime data for Xiaomi Miio config entry.

    Either device/device_coordinator or gateway/gateway_coordinators
    must be set, based on CONF_FLOW_TYPE (CONF_DEVICE or CONF_GATEWAY)
    """

    device: MiioDevice = None  # type: ignore[assignment]
    device_coordinator: DataUpdateCoordinator[Any] = None  # type: ignore[assignment]

    gateway: Gateway = None  # type: ignore[assignment]
    gateway_coordinators: dict[str, GatewayDeviceCoordinator] = None  # type: ignore[assignment]


type XiaomiMiioConfigEntry = ConfigEntry[XiaomiMiioRuntimeData]

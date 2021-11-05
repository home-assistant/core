"""Base class for UniFi Ports."""
from __future__ import annotations

from collections.abc import Iterable, Iterator

from aiounifi.controller import Controller
from aiounifi.devices import Device, Port

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.entity import DeviceInfo

from .unifi_entity_base import UniFiBase


class UniFiPort(UniFiBase):
    """Base class for UniFi ports."""

    def __init__(self, device: Device, port: Port, controller: Controller) -> None:
        """Set up client."""
        self.port = port
        super().__init__(device, controller)

    @property
    def device(self) -> Device:
        """Return the device this port is part of."""
        return self._item

    @property
    def unique_id(self) -> str:
        """Return a unique identifier for this port."""
        return f"{self.TYPE}-{self.device.mac}-{self.port.port_idx}"

    @property
    def key(self) -> str:
        """Return a key for the port."""
        return f"{self.device.mac}-{self.port.port_idx}"

    @property
    def name(self) -> str:
        """Return the name of the port."""
        return f"{self.device.name or self.device.model} {self.port.name}"

    @property
    def available(self) -> bool:
        """Return if controller is available."""
        return (
            self.controller.available and self.device.mac in self.controller.api.devices
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return a port description for device registry."""

        return DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, self.device.mac)},
        )


def find_poe_ports(
    controller: Controller, devices: Iterable[str]
) -> Iterator[tuple[Device, Port]]:
    """Yield a pair of (device, port) for each PoE port found."""
    for mac in devices:
        device = controller.api.devices[mac]
        for port_idx in device.ports:
            port = device.ports[port_idx]
            if not port.port_poe:
                continue

            yield (device, port)

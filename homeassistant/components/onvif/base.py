"""Base classes for ONVIF entities."""
from __future__ import annotations

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import DOMAIN
from .device import ONVIFDevice


class ONVIFBaseEntity(Entity):
    """Base class common to all ONVIF entities."""

    def __init__(self, device: ONVIFDevice) -> None:
        """Initialize the ONVIF entity."""
        self.device: ONVIFDevice = device

    @property
    def available(self):
        """Return True if device is available."""
        return self.device.available

    @property
    def mac_or_serial(self) -> str:
        """Return MAC or serial, for unique_id generation.

        MAC address is not always available, and given the number
        of non-conformant ONVIF devices we have historically supported,
        we can not guarantee serial number either.  Due to this, we have
        adopted an either/or approach in the config entry setup, and can
        guarantee that one or the other will be populated.
        See: https://github.com/home-assistant/core/issues/35883
        """
        return (
            self.device.info.mac
            or self.device.info.serial_number  # type:ignore[return-value]
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return a device description for device registry."""
        connections: set[tuple[str, str]] = set()
        if self.device.info.mac:
            connections = {(CONNECTION_NETWORK_MAC, self.device.info.mac)}
        return DeviceInfo(
            connections=connections,
            identifiers={(DOMAIN, self.mac_or_serial)},
            manufacturer=self.device.info.manufacturer,
            model=self.device.info.model,
            name=self.device.name,
            sw_version=self.device.info.fw_version,
            configuration_url=f"http://{self.device.host}:{self.device.port}",
        )

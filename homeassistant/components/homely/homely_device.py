"""Classes to contain the entity device link provided by Homely."""
import logging

from homelypy.devices import Device

from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class HomelyDevice:
    """A single Homely device."""

    def __init__(self, device_id: str) -> None:
        """Set up data properties."""
        self._device_id = device_id
        self._device: Device

    def update(self, device: Device) -> None:
        """Update device information from Homely."""
        self._device = device

    @property
    def is_online(self) -> bool:
        """Is the device online."""
        return self._device.online

    @property
    def name(self) -> str:
        """Return the device name."""
        return self._device.name

    @property
    def location(self) -> str:
        """Return the device location string."""
        return self._device.location

    @property
    def homely_api_device(self) -> Device:
        """Return the homely API device."""
        return self._device

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=f"{self.location} - {self.name}",
            manufacturer="",
            model=self._device.model_name,
        )

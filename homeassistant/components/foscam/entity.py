"""This component provides basic support for Foscam IP cameras."""
from __future__ import annotations

from libpyfoscam import FoscamCamera

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import FoscamCoordinator
from .const import DOMAIN


class FoscamEntity:
    """An implementation of a Foscam IP camera."""

    def __init__(
        self,
        session: FoscamCamera,
        coordinator: FoscamCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize a Foscam camera."""
        super().__init__()

        self._foscam_session = session
        self._username = config_entry.data[CONF_USERNAME]
        self._password = config_entry.data[CONF_PASSWORD]
        self._name = config_entry.title

        dev_info = (
            coordinator.data["dev_info"] if "dev_info" in coordinator.data else None
        )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, dev_info["mac"] if dev_info else "_camera")},
            manufacturer="Foscam",
            model=dev_info["productName"] if dev_info else None,
            name=config_entry.title,
            sw_version=dev_info["firmwareVer"] if dev_info else None,
            hw_version=dev_info["hardwareVer"] if dev_info else None,
        )


class FoscamCoordinatorEntity(CoordinatorEntity):
    """An implementation of a Foscam IP camera."""

    def __init__(
        self,
        session: FoscamCamera,
        coordinator: FoscamCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize a Foscam camera."""
        super().__init__(coordinator)

        self._foscam_session = session
        self._username = config_entry.data[CONF_USERNAME]
        self._password = config_entry.data[CONF_PASSWORD]
        self._name = config_entry.title

        dev_info = (
            coordinator.data["dev_info"] if "dev_info" in coordinator.data else None
        )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, dev_info["mac"] if dev_info else "_camera")},
            manufacturer="Foscam",
            model=dev_info["productName"] if dev_info else None,
            name=config_entry.title,
            sw_version=dev_info["firmwareVer"] if dev_info else None,
            hw_version=dev_info["hardwareVer"] if dev_info else None,
        )

"""
Base entity for Duosida Local.

This module defines the base class that all Duosida entities inherit from.
It provides common functionality:

1. Connection to the coordinator (for data updates)
2. Device information (shown in HA device registry)
3. Common attributes

By inheriting from this base class, all entities (sensors, switches, etc.)
automatically get proper device grouping in Home Assistant.
"""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME
from .coordinator import DuosidaDataUpdateCoordinator


class DuosidaEntity(CoordinatorEntity[DuosidaDataUpdateCoordinator]):
    """
    Base class for Duosida entities.

    Inherits from CoordinatorEntity which provides:
    - Automatic updates when coordinator refreshes data
    - Availability tracking (unavailable when coordinator fails)
    - Proper cleanup when entity is removed

    The generic type [DuosidaDataUpdateCoordinator] tells the type checker
    what kind of coordinator this entity uses.
    """

    # Tell HA that entity names should be combined with device name
    # e.g., "Duosida 192.168.1.100 Voltage" instead of just "Voltage"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DuosidaDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """
        Initialize the entity.

        Args:
            coordinator: The data update coordinator
            device_id: The charger's device ID (used for unique IDs)
        """
        # Initialize the parent CoordinatorEntity
        # This registers us with the coordinator for updates
        super().__init__(coordinator)

        # Store device ID for use in device_info
        self._device_id = device_id

    @property
    def device_info(self) -> DeviceInfo:
        """
        Return device information.

        This information is used to group all entities from this
        charger under a single device in Home Assistant.

        The device will appear in Settings > Devices & Services
        with all its entities listed together.

        Returns:
            DeviceInfo object with device metadata
        """
        # Get device info from coordinator data
        data = self.coordinator.data or {}

        return DeviceInfo(
            # Unique identifier for this device
            # Uses a set of tuples: {(domain, id)}
            identifiers={(DOMAIN, self._device_id)},
            # Display name for the device
            name=f"{NAME} {self.coordinator.charger.host}",
            # Device metadata from charger response
            manufacturer=data.get("manufacturer") or "Duosida",
            model=data.get("model") or "SmartChargePI",
            # Firmware version from charger data
            sw_version=data.get("firmware"),
        )

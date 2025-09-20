"""Support for Tado Smart device trackers."""

from __future__ import annotations

import logging

from homeassistant.components.device_tracker import TrackerEntity
from homeassistant.const import STATE_HOME, STATE_NOT_HOME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import TadoConfigEntry
from .coordinator import TadoMobileDeviceUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TadoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Tado device scanner entity."""
    tado = entry.runtime_data.mobile_coordinator
    tracked: set = set()

    @callback
    def update_devices() -> None:
        """Update the values of the devices."""
        add_tracked_entities(tado, async_add_entities, tracked)

    update_devices()


@callback
def add_tracked_entities(
    coordinator: TadoMobileDeviceUpdateCoordinator,
    async_add_entities: AddConfigEntryEntitiesCallback,
    tracked: set[str],
) -> None:
    """Add new tracker entities from Tado."""
    _LOGGER.debug("Fetching Tado devices from API for (newly) tracked entities")
    new_tracked = []
    for device_key, device in coordinator.data.items():
        if device_key in tracked:
            continue

        _LOGGER.debug("Adding Tado device %s with deviceID %s", device.name, device_key)
        new_tracked.append(
            TadoDeviceTrackerEntity(device_key, device.name, coordinator)
        )
        tracked.add(device_key)

    async_add_entities(new_tracked)


class TadoDeviceTrackerEntity(CoordinatorEntity[DataUpdateCoordinator], TrackerEntity):
    """A Tado Device Tracker entity."""

    _attr_available = False

    def __init__(
        self,
        device_id: str,
        device_name: str,
        coordinator: TadoMobileDeviceUpdateCoordinator,
    ) -> None:
        """Initialize a Tado Device Tracker entity."""
        super().__init__(coordinator)
        self._attr_unique_id = str(device_id)
        self._device_id = device_id
        self._device_name = device_name
        self._active = False

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.update_state()
        super()._handle_coordinator_update()

    @callback
    def update_state(self) -> None:
        """Update the Tado device."""
        _LOGGER.debug(
            "Updating Tado mobile device: %s (ID: %s)",
            self._device_name,
            self._device_id,
        )
        device = self.coordinator.data[self._device_id]

        self._attr_available = False
        _LOGGER.debug(
            "Tado device %s has geoTracking state %s",
            device["name"],
            device["settings"]["geoTrackingEnabled"],
        )

        if device["settings"]["geoTrackingEnabled"] is False:
            return

        self._attr_available = True
        self._active = False
        if device.get("location") is not None and device["location"]["atHome"]:
            _LOGGER.debug("Tado device %s is at home", device["name"])
            self._active = True
        else:
            _LOGGER.debug("Tado device %s is not at home", device["name"])

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self._device_name

    @property
    def location_name(self) -> str:
        """Return the state of the device."""
        return STATE_HOME if self._active else STATE_NOT_HOME

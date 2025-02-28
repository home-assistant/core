"""Support for Tado Smart device trackers."""

from __future__ import annotations

import logging

from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER_DOMAIN,
    TrackerEntity,
)
from homeassistant.const import STATE_HOME, STATE_NOT_HOME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import TadoConfigEntry
from .const import DOMAIN
from .coordinator import TadoMobileDeviceUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TadoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Tado device scannery entity."""
    _LOGGER.debug("Setting up Tado device scanner entity")
    tado = entry.runtime_data.mobile_coordinator
    tracked: set = set()

    # Fix non-string unique_id for device trackers
    # Can be removed in 2025.1
    entity_registry = er.async_get(hass)
    for device_key in tado.data["mobile_device"]:
        if entity_id := entity_registry.async_get_entity_id(
            DEVICE_TRACKER_DOMAIN, DOMAIN, device_key
        ):
            entity_registry.async_update_entity(
                entity_id, new_unique_id=str(device_key)
            )

    @callback
    def update_devices() -> None:
        """Update the values of the devices."""
        add_tracked_entities(hass, tado, async_add_entities, tracked)

    update_devices()


@callback
def add_tracked_entities(
    hass: HomeAssistant,
    coordinator: TadoMobileDeviceUpdateCoordinator,
    async_add_entities: AddConfigEntryEntitiesCallback,
    tracked: set[str],
) -> None:
    """Add new tracker entities from Tado."""
    _LOGGER.debug("Fetching Tado devices from API for (newly) tracked entities")
    new_tracked = []
    for device_key, device in coordinator.data["mobile_device"].items():
        if device_key in tracked:
            continue

        _LOGGER.debug(
            "Adding Tado device %s with deviceID %s", device["name"], device_key
        )
        new_tracked.append(
            TadoDeviceTrackerEntity(device_key, device["name"], coordinator)
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
        device = self.coordinator.data["mobile_device"][self._device_id]

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

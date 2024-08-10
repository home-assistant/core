"""Airgradient Update platform."""

from datetime import timedelta

from homeassistant.components.update import UpdateDeviceClass, UpdateEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AirGradientConfigEntry, AirGradientMeasurementCoordinator
from .entity import AirGradientEntity

SCAN_INTERVAL = timedelta(hours=1)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AirGradientConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Airgradient update platform."""

    data = config_entry.runtime_data

    async_add_entities([AirGradientUpdate(data.measurement)], True)


class AirGradientUpdate(AirGradientEntity, UpdateEntity):
    """Representation of Airgradient Update."""

    _attr_device_class = UpdateDeviceClass.FIRMWARE

    def __init__(self, coordinator: AirGradientMeasurementCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator.serial_number)
        self._attr_unique_id = f"{coordinator.serial_number}-update"
        self.coordinator = coordinator

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self._set_installed_version)
        )
        self._set_installed_version()

    def _set_installed_version(self) -> None:
        """Set the installed version."""
        self._attr_installed_version = self.coordinator.data.firmware_version

    async def async_update(self) -> None:
        """Update the entity."""
        self._attr_latest_version = (
            await self.coordinator.client.get_latest_firmware_version(
                self.coordinator.serial_number
            )
        )

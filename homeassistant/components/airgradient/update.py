"""Airgradient Update platform."""

from datetime import timedelta

from propcache import cached_property

from homeassistant.components.update import UpdateDeviceClass, UpdateEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AirGradientConfigEntry, AirGradientCoordinator
from .entity import AirGradientEntity

SCAN_INTERVAL = timedelta(hours=1)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AirGradientConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Airgradient update platform."""

    coordinator = config_entry.runtime_data

    async_add_entities([AirGradientUpdate(coordinator)], True)


class AirGradientUpdate(AirGradientEntity, UpdateEntity):
    """Representation of Airgradient Update."""

    _attr_device_class = UpdateDeviceClass.FIRMWARE

    def __init__(self, coordinator: AirGradientCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}-update"

    @cached_property
    def should_poll(self) -> bool:
        """Return True because we need to poll the latest version."""
        return True

    @property
    def installed_version(self) -> str:
        """Return the installed version of the entity."""
        return self.coordinator.data.measures.firmware_version

    async def async_update(self) -> None:
        """Update the entity."""
        self._attr_latest_version = (
            await self.coordinator.client.get_latest_firmware_version(
                self.coordinator.serial_number
            )
        )

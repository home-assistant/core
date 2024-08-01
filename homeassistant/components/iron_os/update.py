"""Update platform for IronOS integration."""

from __future__ import annotations

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityDescription,
    UpdateEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import IronOSConfigEntry, IronOSCoordinators
from .coordinator import IronOSFirmwareUpdateCoordinator
from .entity import IronOSBaseEntity

UPDATE_DESCRIPTION = UpdateEntityDescription(
    key="firmware",
    device_class=UpdateDeviceClass.FIRMWARE,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IronOSConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up IronOS update platform."""

    coordinator = entry.runtime_data

    async_add_entities([IronOSUpdate(coordinator, UPDATE_DESCRIPTION)])


class IronOSUpdate(IronOSBaseEntity, UpdateEntity):
    """Representation of an IronOS update entity."""

    _attr_supported_features = UpdateEntityFeature.RELEASE_NOTES
    firmware: IronOSFirmwareUpdateCoordinator

    def __init__(
        self,
        coordinator: IronOSCoordinators,
        entity_description: UpdateEntityDescription,
    ) -> None:
        """Initialize the sensor."""

        super().__init__(coordinator.live_data, entity_description)

        self.firmware = coordinator.firmware

        self._attr_installed_version = coordinator.live_data.device_info.build
        self._attr_release_url = coordinator.firmware.data.html_url
        self._attr_latest_version = coordinator.firmware.data.tag_name
        self._attr_title = f"IronOS {coordinator.firmware.data.name}"

    async def async_release_notes(self) -> str | None:
        """Return the release notes."""

        return self.firmware.data.body

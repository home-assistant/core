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

from . import IronOSConfigEntry
from .coordinator import IronOSBaseCoordinator
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

    coordinator = entry.runtime_data.firmware

    async_add_entities([IronOSUpdate(coordinator, UPDATE_DESCRIPTION)])


class IronOSUpdate(IronOSBaseEntity, UpdateEntity):
    """Representation of an IronOS update entity."""

    _attr_supported_features = UpdateEntityFeature.RELEASE_NOTES

    def __init__(
        self,
        coordinator: IronOSBaseCoordinator,
        entity_description: UpdateEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entity_description)

    @property
    def installed_version(self) -> str | None:
        """IronOS version on the device."""

        return self.coordinator.device_info.build

    @property
    def title(self) -> str | None:
        """Title of the IronOS release."""

        return f"IronOS {self.coordinator.data.name}"

    @property
    def release_url(self) -> str | None:
        """URL to the full release notes of the latest IronOS version available."""

        return self.coordinator.data.html_url

    @property
    def latest_version(self) -> str | None:
        """Latest IronOS version available for install."""

        return self.coordinator.data.tag_name

    async def async_release_notes(self) -> str | None:
        """Return the release notes."""

        return self.coordinator.data.body

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

    @property
    def installed_version(self) -> str | None:
        """Version installed and in use."""

        return self.coordinator.device_info.build

    async def async_release_notes(self) -> str | None:
        """Return the release notes."""

        return self.coordinator.latest_release.body

    @property
    def release_url(self) -> str | None:
        """URL to the full release notes of the latest version available."""

        return self.coordinator.latest_release.html_url

    @property
    def latest_version(self) -> str | None:
        """Latest version available for install."""

        return self.coordinator.latest_release.tag_name

    @property
    def title(self) -> str | None:
        """Title of the release."""

        return f"IronOS {self.coordinator.latest_release.name}"

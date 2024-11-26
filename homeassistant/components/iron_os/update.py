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

from . import IRON_OS_KEY, IronOSConfigEntry, IronOSLiveDataCoordinator
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

    async_add_entities(
        [IronOSUpdate(coordinator, hass.data[IRON_OS_KEY], UPDATE_DESCRIPTION)]
    )


class IronOSUpdate(IronOSBaseEntity, UpdateEntity):
    """Representation of an IronOS update entity."""

    _attr_supported_features = UpdateEntityFeature.RELEASE_NOTES

    def __init__(
        self,
        coordinator: IronOSLiveDataCoordinator,
        firmware_update: IronOSFirmwareUpdateCoordinator,
        entity_description: UpdateEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        self.firmware_update = firmware_update
        super().__init__(coordinator, entity_description)

    @property
    def installed_version(self) -> str | None:
        """IronOS version on the device."""

        return self.coordinator.device_info.build

    @property
    def title(self) -> str | None:
        """Title of the IronOS release."""

        return f"IronOS {self.firmware_update.data.name}"

    @property
    def release_url(self) -> str | None:
        """URL to the full release notes of the latest IronOS version available."""

        return self.firmware_update.data.html_url

    @property
    def latest_version(self) -> str | None:
        """Latest IronOS version available for install."""

        return self.firmware_update.data.tag_name

    async def async_release_notes(self) -> str | None:
        """Return the release notes."""

        return self.firmware_update.data.body

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass.

        Register extra update listener for the firmware update coordinator.
        """
        await super().async_added_to_hass()
        self.async_on_remove(
            self.firmware_update.async_add_listener(self._handle_coordinator_update)
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.installed_version is not None
            and self.firmware_update.last_update_success
        )

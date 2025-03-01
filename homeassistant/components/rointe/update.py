"""Update entity platform for Rointe devices."""

from __future__ import annotations

from rointesdk.device import RointeDevice

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import RointeDataUpdateCoordinator
from .entity import RointeRadiatorEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the radiator sensors from the config entry."""
    coordinator: RointeDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Register the Entity classes and platform on the coordinator.
    coordinator.add_entities_for_seen_keys(
        async_add_entities,
        [RointeUpdateEntity],
        "update",
    )


class RointeUpdateEntity(RointeRadiatorEntity, UpdateEntity):
    """Update entity."""

    def __init__(
        self,
        radiator: RointeDevice,
        coordinator: RointeDataUpdateCoordinator,
    ) -> None:
        """Init the update entity."""

        self.entity_description = UpdateEntityDescription(
            key="update_available",
            name=f"{radiator.name} Update Available",
            device_class=UpdateDeviceClass.FIRMWARE,
            entity_category=EntityCategory.DIAGNOSTIC,
        )

        # Set the name and ID of this entity to be the radiator name/id and a prefix.
        super().__init__(
            coordinator,
            radiator,
            unique_id=f"{radiator.id}-fw_update_available",
        )

    @property
    def installed_version(self) -> str | None:
        """Version installed and in use."""
        return self._radiator.firmware_version

    @property
    def latest_version(self) -> str | None:
        """Latest version available for install."""
        return self._radiator.latest_firmware_version

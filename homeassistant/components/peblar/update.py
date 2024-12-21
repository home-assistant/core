"""Support for Peblar updates."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import (
    PeblarConfigEntry,
    PeblarVersionDataUpdateCoordinator,
    PeblarVersionInformation,
)


@dataclass(frozen=True, kw_only=True)
class PeblarUpdateEntityDescription(UpdateEntityDescription):
    """Describe an Peblar update entity."""

    installed_fn: Callable[[PeblarVersionInformation], str | None]
    available_fn: Callable[[PeblarVersionInformation], str | None]


DESCRIPTIONS: tuple[PeblarUpdateEntityDescription, ...] = (
    PeblarUpdateEntityDescription(
        key="firmware",
        device_class=UpdateDeviceClass.FIRMWARE,
        installed_fn=lambda x: x.current.firmware,
        available_fn=lambda x: x.available.firmware,
    ),
    PeblarUpdateEntityDescription(
        key="customization",
        translation_key="customization",
        installed_fn=lambda x: x.current.customization,
        available_fn=lambda x: x.available.customization,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PeblarConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Peblar update based on a config entry."""
    async_add_entities(
        PeblarUpdateEntity(entry, description) for description in DESCRIPTIONS
    )


class PeblarUpdateEntity(
    CoordinatorEntity[PeblarVersionDataUpdateCoordinator], UpdateEntity
):
    """Defines a Peblar update entity."""

    entity_description: PeblarUpdateEntityDescription

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: PeblarConfigEntry,
        description: PeblarUpdateEntityDescription,
    ) -> None:
        """Initialize the update entity."""
        super().__init__(entry.runtime_data.version_coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.unique_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, entry.runtime_data.system_information.product_serial_number)
            },
        )

    @property
    def installed_version(self) -> str | None:
        """Version currently installed and in use."""
        return self.entity_description.installed_fn(self.coordinator.data)

    @property
    def latest_version(self) -> str | None:
        """Latest version available for install."""
        return self.entity_description.available_fn(self.coordinator.data)

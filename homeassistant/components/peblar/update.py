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
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import (
    PeblarConfigEntry,
    PeblarVersionDataUpdateCoordinator,
    PeblarVersionInformation,
)
from .entity import PeblarEntity

PARALLEL_UPDATES = 1


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
        PeblarUpdateEntity(
            entry=entry,
            coordinator=entry.runtime_data.version_coordinator,
            description=description,
        )
        for description in DESCRIPTIONS
    )


class PeblarUpdateEntity(
    PeblarEntity[PeblarVersionDataUpdateCoordinator],
    UpdateEntity,
):
    """Defines a Peblar update entity."""

    entity_description: PeblarUpdateEntityDescription

    @property
    def installed_version(self) -> str | None:
        """Version currently installed and in use."""
        return self.entity_description.installed_fn(self.coordinator.data)

    @property
    def latest_version(self) -> str | None:
        """Latest version available for install."""
        return self.entity_description.available_fn(self.coordinator.data)

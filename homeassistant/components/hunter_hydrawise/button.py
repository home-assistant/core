"""Support for Hydrawise cloud buttons."""
from __future__ import annotations

from homeassistant.components.button import (
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DEFAULT_SUSPEND_DAYS,
    DOMAIN,
)
from .coordinator import HydrawiseDataUpdateCoordinator, HydrawiseEntity
from .hydrawiser import Hydrawiser

BUTTON_TYPES: tuple[ButtonEntityDescription, ...] = (
    ButtonEntityDescription(
        key="suspend_all_zones",
        name="Suspend All Zones",
    ),
    ButtonEntityDescription(
        key="resume_all_zones",
        name="Resume All Zones",
    ),
    ButtonEntityDescription(
        key="run_all_zones",
        name="Run All Zones",
    ),
    ButtonEntityDescription(
        key="stop_all_zones",
        name="Stop All Zones",
    ),
)


# This function is called as part of the __init__.async_setup_entry (via the
# hass.config_entries.async_forward_entry_setup call)
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add entities for passed config_entry in HA."""
    coordinator: HydrawiseDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]
    hydrawise: Hydrawiser = coordinator.api

    entities = []

    for controller in hydrawise.controllers:
        for description in BUTTON_TYPES:
            entities.append(
                HydrawiseButton(
                    coordinator=coordinator,
                    controller_id=controller.id,
                    description=description,
                )
            )

    # Add all entities to HA
    async_add_entities(entities)


class HydrawiseButton(HydrawiseEntity, ButtonEntity):
    """A switch implementation for Hydrawise device."""

    def __init__(
        self,
        *,
        coordinator: HydrawiseDataUpdateCoordinator,
        controller_id: int,
        description: EntityDescription,
    ) -> None:
        """Initiatlize."""
        super().__init__(
            coordinator=coordinator,
            controller_id=controller_id,
            zone_id=-1,
            description=description,
        )

    async def async_press(self) -> None:
        """Trigger action."""
        if self.entity_description.key == "suspend_all_zones":
            await self.coordinator.api.async_suspend_all(
                self.controller_id, DEFAULT_SUSPEND_DAYS
            )
        elif self.entity_description.key == "resume_all_zones":
            await self.coordinator.api.async_resume_all(self.controller_id)
        elif self.entity_description.key == "stop_all_zones":
            await self.coordinator.api.async_stop_all(self.controller_id)
        elif self.entity_description.key == "run_all_zones":
            await self.coordinator.api.async_run_all(self.controller_id)

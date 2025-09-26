"""Support for Portainer buttons."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
import logging
from typing import Any

from pyportainer.models.docker import DockerContainer

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PortainerConfigEntry
from .coordinator import PortainerCoordinator, PortainerCoordinatorData
from .entity import PortainerContainerEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class PortainerButtonDescription(ButtonEntityDescription):
    """Class to describe a Portainer button entity."""

    press_action: Callable[
        [PortainerCoordinator, int, str],
        Coroutine[Any, Any, None],
    ]


BUTTONS: tuple[PortainerButtonDescription, ...] = (
    PortainerButtonDescription(
        key="restart",
        name="Restart Container",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        press_action=lambda coordinator,
        endpoint_id,
        container_id: coordinator.async_restart_container(endpoint_id, container_id),
    ),
    PortainerButtonDescription(
        key="stop",
        name="Stop Container",
        icon="mdi:stop-circle-outline",
        entity_category=EntityCategory.CONFIG,
        press_action=lambda coordinator,
        endpoint_id,
        container_id: coordinator.async_stop_container(endpoint_id, container_id),
    ),
    PortainerButtonDescription(
        key="start",
        name="Start Container",
        icon="mdi:play-circle-outline",
        entity_category=EntityCategory.CONFIG,
        press_action=lambda coordinator,
        endpoint_id,
        container_id: coordinator.async_start_container(endpoint_id, container_id),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PortainerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Portainer buttons."""
    coordinator: PortainerCoordinator = entry.runtime_data
    entities: list[ButtonEntity] = []

    for endpoint in coordinator.data.values():
        entities.extend(
            PortainerButton(
                coordinator=coordinator,
                entity_description=entity_description,
                device_info=container,
                via_device=endpoint,
            )
            for container in endpoint.containers.values()
            for entity_description in BUTTONS
        )

    async_add_entities(entities)


class PortainerButton(PortainerContainerEntity, ButtonEntity):
    """Defines a Portainer button."""

    entity_description: PortainerButtonDescription

    def __init__(
        self,
        coordinator: PortainerCoordinator,
        entity_description: PortainerButtonDescription,
        device_info: DockerContainer,
        via_device: PortainerCoordinatorData,
    ) -> None:
        """Initialize the Portainer button entity."""
        self.entity_description = entity_description
        super().__init__(device_info, coordinator, via_device)

        device_identifier = (
            self._device_info.names[0].replace("/", " ").strip()
            if self._device_info.names
            else None
        )
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{device_identifier}_{entity_description.key}"

    async def async_press(self) -> None:
        """Trigger the Portainer button press service."""
        await self.entity_description.press_action(
            self.coordinator, self.endpoint_id, self.device_id
        )

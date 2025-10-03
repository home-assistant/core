"""Switch platform for Portainer containers."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from pyportainer import Portainer
from pyportainer.models.docker import DockerContainer

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PortainerConfigEntry
from .coordinator import PortainerCoordinator
from .entity import PortainerContainerEntity, PortainerCoordinatorData


@dataclass(frozen=True, kw_only=True)
class PortainerSwitchEntityDescription(SwitchEntityDescription):
    """Class to hold Portainer switch description."""

    is_on_fn: Callable[[DockerContainer], bool | None]
    turn_on_fn: Callable[[Portainer, int, str], Coroutine[Any, Any, None]]
    turn_off_fn: Callable[[Portainer, int, str], Coroutine[Any, Any, None]]


async def stop_container(
    portainer: Portainer, endpoint_id: int, container_id: str
) -> None:
    """Stop a container."""
    await portainer.stop_container(endpoint_id, container_id)


async def start_container(
    portainer: Portainer, endpoint_id: int, container_id: str
) -> None:
    """Start a container."""
    await portainer.start_container(endpoint_id, container_id)


SWITCHES: tuple[PortainerSwitchEntityDescription, ...] = (
    PortainerSwitchEntityDescription(
        key="container",
        translation_key="container",
        device_class=SwitchDeviceClass.SWITCH,
        is_on_fn=lambda data: data.state == "running",
        turn_on_fn=start_container,
        turn_off_fn=stop_container,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PortainerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Portainer switch sensors."""

    coordinator: PortainerCoordinator = entry.runtime_data

    async_add_entities(
        PortainerContainerSwitch(
            coordinator=coordinator,
            entity_description=entity_description,
            device_info=container,
            via_device=endpoint,
        )
        for endpoint in coordinator.data.values()
        for container in endpoint.containers.values()
        for entity_description in SWITCHES
    )


class PortainerContainerSwitch(PortainerContainerEntity, SwitchEntity):
    """Representation of a Portainer container switch."""

    entity_description: PortainerSwitchEntityDescription

    def __init__(
        self,
        coordinator: PortainerCoordinator,
        entity_description: PortainerSwitchEntityDescription,
        device_info: DockerContainer,
        via_device: PortainerCoordinatorData,
    ) -> None:
        """Initialize the Portainer container switch."""
        self.entity_description = entity_description
        super().__init__(device_info, coordinator, via_device)

        device_identifier = (
            self._device_info.names[0].replace("/", " ").strip()
            if self._device_info.names
            else None
        )
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{device_identifier}_{entity_description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return the state of the device."""
        return self.entity_description.is_on_fn(
            self.coordinator.data[self.endpoint_id].containers[self.device_id]
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start (turn on) the container."""
        await self.entity_description.turn_on_fn(
            self.coordinator.portainer, self.endpoint_id, self.device_id
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop (turn off) the container."""
        await self.entity_description.turn_off_fn(
            self.coordinator.portainer, self.endpoint_id, self.device_id
        )
        await self.coordinator.async_request_refresh()

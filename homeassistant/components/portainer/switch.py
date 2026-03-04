"""Switch platform for Portainer containers."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from pyportainer import Portainer
from pyportainer.exceptions import (
    PortainerAuthenticationError,
    PortainerConnectionError,
    PortainerTimeoutError,
)

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PortainerConfigEntry
from .const import DOMAIN, STACK_STATUS_ACTIVE
from .coordinator import (
    PortainerContainerData,
    PortainerCoordinator,
    PortainerStackData,
)
from .entity import (
    PortainerContainerEntity,
    PortainerCoordinatorData,
    PortainerStackEntity,
)


@dataclass(frozen=True, kw_only=True)
class PortainerSwitchEntityDescription(SwitchEntityDescription):
    """Class to hold Portainer switch description."""

    is_on_fn: Callable[[PortainerContainerData], bool | None]
    turn_on_fn: Callable[[Portainer], Callable[[int, str], Coroutine[Any, Any, None]]]
    turn_off_fn: Callable[[Portainer], Callable[[int, str], Coroutine[Any, Any, None]]]


@dataclass(frozen=True, kw_only=True)
class PortainerStackSwitchEntityDescription(SwitchEntityDescription):
    """Class to hold Portainer stack switch description."""

    is_on_fn: Callable[[PortainerStackData], bool | None]
    turn_on_fn: Callable[[Portainer], Callable[..., Coroutine[Any, Any, Any]]]
    turn_off_fn: Callable[[Portainer], Callable[..., Coroutine[Any, Any, Any]]]


PARALLEL_UPDATES = 1


async def _perform_action(
    coordinator: PortainerCoordinator,
    coroutine: Coroutine[Any, Any, Any],
) -> None:
    """Perform a Portainer action with error handling and coordinator refresh."""
    try:
        await coroutine
    except PortainerAuthenticationError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="invalid_auth_no_details",
        ) from err
    except PortainerConnectionError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="cannot_connect_no_details",
        ) from err
    except PortainerTimeoutError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="timeout_connect_no_details",
        ) from err
    else:
        await coordinator.async_request_refresh()


CONTAINER_SWITCHES: tuple[PortainerSwitchEntityDescription, ...] = (
    PortainerSwitchEntityDescription(
        key="container",
        translation_key="container",
        device_class=SwitchDeviceClass.SWITCH,
        is_on_fn=lambda data: data.container.state == "running",
        turn_on_fn=lambda portainer: portainer.start_container,
        turn_off_fn=lambda portainer: portainer.stop_container,
    ),
)

STACK_SWITCHES: tuple[PortainerStackSwitchEntityDescription, ...] = (
    PortainerStackSwitchEntityDescription(
        key="stack",
        translation_key="stack",
        device_class=SwitchDeviceClass.SWITCH,
        is_on_fn=lambda data: data.stack.status == STACK_STATUS_ACTIVE,
        turn_on_fn=lambda portainer: portainer.start_stack,
        turn_off_fn=lambda portainer: portainer.stop_stack,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PortainerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Portainer switch sensors."""
    coordinator = entry.runtime_data

    def _async_add_new_containers(
        containers: list[tuple[PortainerCoordinatorData, PortainerContainerData]],
    ) -> None:
        """Add new container switch sensors."""
        async_add_entities(
            PortainerContainerSwitch(
                coordinator,
                entity_description,
                container,
                endpoint,
            )
            for (endpoint, container) in containers
            for entity_description in CONTAINER_SWITCHES
        )

    def _async_add_new_stacks(
        stacks: list[tuple[PortainerCoordinatorData, PortainerStackData]],
    ) -> None:
        """Add new stack switch sensors."""
        async_add_entities(
            PortainerStackSwitch(
                coordinator,
                entity_description,
                stack,
                endpoint,
            )
            for (endpoint, stack) in stacks
            for entity_description in STACK_SWITCHES
        )

    coordinator.new_containers_callbacks.append(_async_add_new_containers)
    coordinator.new_stacks_callbacks.append(_async_add_new_stacks)
    _async_add_new_containers(
        [
            (endpoint, container)
            for endpoint in coordinator.data.values()
            for container in endpoint.containers.values()
        ]
    )
    _async_add_new_stacks(
        [
            (endpoint, stack)
            for endpoint in coordinator.data.values()
            for stack in endpoint.stacks.values()
        ]
    )


class PortainerContainerSwitch(PortainerContainerEntity, SwitchEntity):
    """Representation of a Portainer container switch."""

    entity_description: PortainerSwitchEntityDescription

    @property
    def is_on(self) -> bool | None:
        """Return the state of the device."""
        return self.entity_description.is_on_fn(self.container_data)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start (turn on) the container."""
        await _perform_action(
            self.coordinator,
            self.entity_description.turn_on_fn(self.coordinator.portainer)(
                self.endpoint_id, self.container_data.container.id
            ),
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop (turn off) the container."""
        await _perform_action(
            self.coordinator,
            self.entity_description.turn_off_fn(self.coordinator.portainer)(
                self.endpoint_id, self.container_data.container.id
            ),
        )


class PortainerStackSwitch(PortainerStackEntity, SwitchEntity):
    """Representation of a Portainer stack switch."""

    entity_description: PortainerStackSwitchEntityDescription

    @property
    def is_on(self) -> bool | None:
        """Return the state of the device."""
        return self.entity_description.is_on_fn(self.stack_data)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start (turn on) the stack."""
        await _perform_action(
            self.coordinator,
            self.entity_description.turn_on_fn(self.coordinator.portainer)(
                self.endpoint_id, self.stack_data.stack.id
            ),
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop (turn off) the stack."""
        await _perform_action(
            self.coordinator,
            self.entity_description.turn_off_fn(self.coordinator.portainer)(
                self.endpoint_id, self.stack_data.stack.id
            ),
        )

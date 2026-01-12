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
    """Class to hold Portainer container switch description."""

    is_on_fn: Callable[[PortainerContainerData], bool | None]
    turn_on_fn: Callable[[str, Portainer, int, str], Coroutine[Any, Any, None]]
    turn_off_fn: Callable[[str, Portainer, int, str], Coroutine[Any, Any, None]]


@dataclass(frozen=True, kw_only=True)
class PortainerStackSwitchEntityDescription(SwitchEntityDescription):
    """Class to hold Portainer stack switch description."""

    is_on_fn: Callable[[PortainerStackData], bool | None]
    turn_on_fn: Callable[[Portainer, int, int], Coroutine[Any, Any, None]]
    turn_off_fn: Callable[[Portainer, int, int], Coroutine[Any, Any, None]]


async def perform_container_action(
    action: str, portainer: Portainer, endpoint_id: int, container_id: str
) -> None:
    """Start or stop a container."""
    try:
        if action == "start":
            await portainer.start_container(endpoint_id, container_id)
        elif action == "stop":
            await portainer.stop_container(endpoint_id, container_id)
    except PortainerAuthenticationError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="invalid_auth",
            translation_placeholders={"error": repr(err)},
        ) from err
    except PortainerConnectionError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"error": repr(err)},
        ) from err
    except PortainerTimeoutError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="timeout_connect",
            translation_placeholders={"error": repr(err)},
        ) from err


async def start_stack(portainer: Portainer, stack_id: int, endpoint_id: int) -> None:
    """Start a stack."""
    try:
        await portainer.start_stack(stack_id, endpoint_id)
    except PortainerAuthenticationError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="invalid_auth",
            translation_placeholders={"error": repr(err)},
        ) from err
    except PortainerConnectionError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"error": repr(err)},
        ) from err
    except PortainerTimeoutError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="timeout_connect",
            translation_placeholders={"error": repr(err)},
        ) from err


async def stop_stack(portainer: Portainer, stack_id: int, endpoint_id: int) -> None:
    """Stop a stack."""
    try:
        await portainer.stop_stack(stack_id, endpoint_id)
    except PortainerAuthenticationError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="invalid_auth",
            translation_placeholders={"error": repr(err)},
        ) from err
    except PortainerConnectionError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"error": repr(err)},
        ) from err
    except PortainerTimeoutError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="timeout_connect",
            translation_placeholders={"error": repr(err)},
        ) from err


CONTAINER_SWITCHES: tuple[PortainerSwitchEntityDescription, ...] = (
    PortainerSwitchEntityDescription(
        key="container",
        translation_key="container",
        device_class=SwitchDeviceClass.SWITCH,
        is_on_fn=lambda data: data.container.state == "running",
        turn_on_fn=perform_container_action,
        turn_off_fn=perform_container_action,
    ),
)

STACK_SWITCHES: tuple[PortainerStackSwitchEntityDescription, ...] = (
    PortainerStackSwitchEntityDescription(
        key="stack",
        translation_key="stack",
        device_class=SwitchDeviceClass.SWITCH,
        is_on_fn=lambda data: data.stack.status == STACK_STATUS_ACTIVE,
        turn_on_fn=start_stack,
        turn_off_fn=stop_stack,
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

    def __init__(
        self,
        coordinator: PortainerCoordinator,
        entity_description: PortainerSwitchEntityDescription,
        device_info: PortainerContainerData,
        via_device: PortainerCoordinatorData,
    ) -> None:
        """Initialize the Portainer container switch."""
        self.entity_description = entity_description
        super().__init__(device_info, coordinator, via_device)

        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{self.endpoint_id}_{self.device_name}_{entity_description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return the state of the device."""
        return self.entity_description.is_on_fn(self.container_data)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start (turn on) the container."""
        await self.entity_description.turn_on_fn(
            "start",
            self.coordinator.portainer,
            self.endpoint_id,
            self.container_data.container.id,
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop (turn off) the container."""
        await self.entity_description.turn_off_fn(
            "stop",
            self.coordinator.portainer,
            self.endpoint_id,
            self.container_data.container.id,
        )
        await self.coordinator.async_request_refresh()


class PortainerStackSwitch(PortainerStackEntity, SwitchEntity):
    """Representation of a Portainer stack switch."""

    entity_description: PortainerStackSwitchEntityDescription
    _optimistic_state: bool | None = None

    def __init__(
        self,
        coordinator: PortainerCoordinator,
        entity_description: PortainerStackSwitchEntityDescription,
        device_info: PortainerStackData,
        via_device: PortainerCoordinatorData,
    ) -> None:
        """Initialize the Portainer stack switch."""
        self.entity_description = entity_description
        super().__init__(device_info, coordinator, via_device)

        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{self.endpoint_id}_stack_{self.stack_name}_{entity_description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return the state of the device."""
        if self._optimistic_state is not None:
            return self._optimistic_state
        return self.entity_description.is_on_fn(self.stack_data)

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Clear optimistic state when coordinator updates
        self._optimistic_state = None
        super()._handle_coordinator_update()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start (turn on) the stack."""
        self._optimistic_state = True
        self.async_write_ha_state()
        await self.entity_description.turn_on_fn(
            self.coordinator.portainer,
            self.stack_id,
            self.endpoint_id,
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop (turn off) the stack."""
        self._optimistic_state = False
        self.async_write_ha_state()
        await self.entity_description.turn_off_fn(
            self.coordinator.portainer,
            self.stack_id,
            self.endpoint_id,
        )
        await self.coordinator.async_request_refresh()

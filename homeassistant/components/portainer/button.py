"""Support for Portainer buttons."""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from pyportainer import Portainer
from pyportainer.exceptions import (
    PortainerAuthenticationError,
    PortainerConnectionError,
    PortainerTimeoutError,
)

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PortainerConfigEntry
from .const import DOMAIN
from .coordinator import (
    PortainerContainerData,
    PortainerCoordinator,
    PortainerCoordinatorData,
)
from .entity import PortainerContainerEntity, PortainerEndpointEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class PortainerButtonDescription(ButtonEntityDescription):
    """Class to describe a Portainer button entity."""

    # Note to reviewer: I am keeping the third argument a str, in order to keep mypy happy :)
    press_action: Callable[
        [Portainer, int, str],
        Coroutine[Any, Any, None],
    ]


ENDPOINT_BUTTONS: tuple[PortainerButtonDescription, ...] = (
    PortainerButtonDescription(
        key="images_prune",
        translation_key="images_prune",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        press_action=(
            lambda portainer, endpoint_id, _: portainer.images_prune(
                endpoint_id=endpoint_id, dangling=False, until=timedelta(days=0)
            )
        ),
    ),
)

CONTAINER_BUTTONS: tuple[PortainerButtonDescription, ...] = (
    PortainerButtonDescription(
        key="restart",
        translation_key="restart_container",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        press_action=(
            lambda portainer, endpoint_id, container_id: portainer.restart_container(
                endpoint_id, container_id
            )
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PortainerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Portainer buttons."""
    coordinator = entry.runtime_data

    def _async_add_new_endpoints(endpoints: list[PortainerCoordinatorData]) -> None:
        """Add new endpoint binary sensors."""
        async_add_entities(
            PortainerEndpointButton(
                coordinator,
                entity_description,
                endpoint,
            )
            for entity_description in ENDPOINT_BUTTONS
            for endpoint in endpoints
        )

    def _async_add_new_containers(
        containers: list[tuple[PortainerCoordinatorData, PortainerContainerData]],
    ) -> None:
        """Add new container button sensors."""
        async_add_entities(
            PortainerContainerButton(
                coordinator,
                entity_description,
                container,
                endpoint,
            )
            for (endpoint, container) in containers
            for entity_description in CONTAINER_BUTTONS
        )

    coordinator.new_endpoints_callbacks.append(_async_add_new_endpoints)
    coordinator.new_containers_callbacks.append(_async_add_new_containers)

    _async_add_new_endpoints(
        [
            endpoint
            for endpoint in coordinator.data.values()
            if endpoint.id in coordinator.known_endpoints
        ]
    )
    _async_add_new_containers(
        [
            (endpoint, container)
            for endpoint in coordinator.data.values()
            for container in endpoint.containers.values()
        ]
    )


class PortainerBaseButton(ButtonEntity):
    """Common base for Portainer buttons. Basically to ensure the async_press logic isn't duplicated."""

    entity_description: PortainerButtonDescription
    coordinator: PortainerCoordinator

    @abstractmethod
    async def _async_press_call(self) -> None:
        """Abstract method used per Portainer button class."""

    async def async_press(self) -> None:
        """Trigger the Portainer button press service."""
        try:
            await self._async_press_call()
        except PortainerConnectionError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="cannot_connect_no_details",
            ) from err
        except PortainerAuthenticationError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="invalid_auth_no_details",
            ) from err
        except PortainerTimeoutError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="timeout_connect_no_details",
            ) from err


class PortainerEndpointButton(PortainerEndpointEntity, PortainerBaseButton):
    """Defines a Portainer endpoint button."""

    entity_description: PortainerButtonDescription

    def __init__(
        self,
        coordinator: PortainerCoordinator,
        entity_description: PortainerButtonDescription,
        device_info: PortainerCoordinatorData,
    ) -> None:
        """Initialize the Portainer endpoint button entity."""
        self.entity_description = entity_description
        super().__init__(device_info, coordinator)

        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{device_info.id}_{entity_description.key}"

    async def _async_press_call(self) -> None:
        """Call the endpoint button press action."""
        await self.entity_description.press_action(
            self.coordinator.portainer, self.device_id, ""
        )


class PortainerContainerButton(PortainerContainerEntity, PortainerBaseButton):
    """Defines a Portainer button."""

    entity_description: PortainerButtonDescription

    def __init__(
        self,
        coordinator: PortainerCoordinator,
        entity_description: PortainerButtonDescription,
        device_info: PortainerContainerData,
        via_device: PortainerCoordinatorData,
    ) -> None:
        """Initialize the Portainer button entity."""
        self.entity_description = entity_description
        super().__init__(device_info, coordinator, via_device)

        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{self.device_name}_{entity_description.key}"

    async def _async_press_call(self) -> None:
        """Call the container button press action."""
        await self.entity_description.press_action(
            self.coordinator.portainer,
            self.endpoint_id,
            self.container_data.container.id,
        )

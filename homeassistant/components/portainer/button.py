"""Support for Portainer buttons."""

from abc import abstractmethod
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, override

from pyportainer import Portainer
from pyportainer.exceptions import (
    PortainerAuthenticationError,
    PortainerConnectionError,
    PortainerTimeoutError,
)
from pyportainer.models.docker import DockerContainer

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
class PortainerEndpointButtonDescription(ButtonEntityDescription):
    """Class to describe a Portainer endpoint button entity."""

    press_action: Callable[
        [Portainer, int],
        Coroutine[Any, Any, None | DockerContainer],
    ]


@dataclass(frozen=True, kw_only=True)
class PortainerContainerButtonDescription(ButtonEntityDescription):
    """Class to describe a Portainer container button entity."""

    press_action: Callable[
        [Portainer, int, str],
        Coroutine[Any, Any, None | DockerContainer],
    ]


ENDPOINT_BUTTONS: tuple[PortainerEndpointButtonDescription, ...] = (
    PortainerEndpointButtonDescription(
        key="images_prune",
        translation_key="images_prune",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        press_action=(
            lambda portainer, endpoint_id: portainer.images_prune(
                endpoint_id=endpoint_id, dangling=False, until=timedelta(days=0)
            )
        ),
    ),
    PortainerEndpointButtonDescription(
        key="volumes_prune",
        translation_key="volumes_prune",
        entity_category=EntityCategory.CONFIG,
        press_action=(
            lambda portainer, endpoint_id: portainer.prune_volumes(endpoint_id)
        ),
    ),
)

CONTAINER_BUTTONS: tuple[PortainerContainerButtonDescription, ...] = (
    PortainerContainerButtonDescription(
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
    PortainerContainerButtonDescription(
        key="pause",
        translation_key="pause_container",
        entity_category=EntityCategory.CONFIG,
        press_action=(
            lambda portainer, endpoint_id, container_id: portainer.pause_container(
                endpoint_id, container_id
            )
        ),
    ),
    PortainerContainerButtonDescription(
        key="resume",
        translation_key="resume_container",
        entity_category=EntityCategory.CONFIG,
        press_action=(
            lambda portainer, endpoint_id, container_id: portainer.unpause_container(
                endpoint_id, container_id
            )
        ),
    ),
    PortainerContainerButtonDescription(
        key="recreate",
        translation_key="recreate_container",
        entity_category=EntityCategory.CONFIG,
        press_action=(
            lambda portainer, endpoint_id, container_id: portainer.container_recreate(
                endpoint_id=endpoint_id,
                container_id=container_id,
                timeout=timedelta(minutes=10),
                pull_image=True,
            )
        ),
    ),
    PortainerContainerButtonDescription(
        key="kill",
        translation_key="kill_container",
        entity_category=EntityCategory.CONFIG,
        press_action=(
            lambda portainer, endpoint_id, container_id: portainer.kill_container(
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
    """Common base for Portainer buttons.

    Ensures the async_press logic isn't duplicated.
    """

    coordinator: PortainerCoordinator

    @abstractmethod
    async def _async_press_call(self) -> None:
        """Abstract method used per Portainer button class."""

    @override
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

        await self.coordinator.async_request_refresh()


class PortainerEndpointButton(PortainerEndpointEntity, PortainerBaseButton):
    """Defines a Portainer endpoint button."""

    entity_description: PortainerEndpointButtonDescription

    @override
    async def _async_press_call(self) -> None:
        """Call the endpoint button press action."""
        await self.entity_description.press_action(
            self.coordinator.portainer, self.device_id
        )


class PortainerContainerButton(PortainerContainerEntity, PortainerBaseButton):
    """Defines a Portainer button."""

    entity_description: PortainerContainerButtonDescription

    @override
    async def _async_press_call(self) -> None:
        """Call the container button press action."""
        await self.entity_description.press_action(
            self.coordinator.portainer,
            self.endpoint_id,
            self.container_data.container.id,
        )

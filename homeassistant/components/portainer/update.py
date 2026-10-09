"""Support for Portainer container updates."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import TYPE_CHECKING, Any, override

from pyportainer import (
    ImagePullProgress,
    PortainerAuthenticationError,
    PortainerError,
    PortainerTimeoutError,
)
from pyportainer.models.docker import LocalImageInformation, PortainerImageUpdateStatus
from pyportainer.models.portainer import PortainerSystemVersion

from homeassistant.components.update import (
    UpdateEntity,
    UpdateEntityDescription,
    UpdateEntityFeature,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import (
    PortainerConfigEntry,
    PortainerContainerData,
    PortainerCoordinator,
    PortainerCoordinatorData,
)
from .entity import PortainerContainerEntity, PortainerServerEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class PortainerContainerUpdateEntityDescription(UpdateEntityDescription):
    """Describes Portainer container update entity."""

    installed_version: Callable[[LocalImageInformation], str | None]
    latest_version: Callable[[PortainerImageUpdateStatus | None], str | None]


PARALLEL_UPDATES = 1
DEFAULT_RECREATE_TIMEOUT = timedelta(minutes=10)
# Share of the install progress taken by the image pull, the rest is the recreate
PULL_PERCENTAGE = 90


def _short_digest(digest: str) -> str:
    """Shorten a digest to its algorithm and the leading hex characters."""
    algorithm, separator, hex_digest = digest.partition(":")
    return f"{algorithm}{separator}{hex_digest[:12]}"


CONTAINER_IMAGE: tuple[PortainerContainerUpdateEntityDescription] = (
    PortainerContainerUpdateEntityDescription(
        key="container_image_update",
        translation_key="container_image_update",
        entity_category=EntityCategory.CONFIG,
        installed_version=lambda data: (
            _short_digest(data.repo_digests[0].partition("@")[2])
            if data.repo_digests
            else None
        ),
        latest_version=lambda data: (
            _short_digest(digest)
            if data is not None and (digest := data.registry_digest)
            else None
        ),
    ),
)


@dataclass(frozen=True, kw_only=True)
class PortainerServerUpdateEntityDescription(UpdateEntityDescription):
    """Describes Portainer server update entity."""

    installed_version: Callable[[PortainerSystemVersion], str | None]
    latest_version: Callable[[PortainerSystemVersion], str | None]
    release_url: Callable[[PortainerSystemVersion], str | None]


SERVER_UPDATES: tuple[PortainerServerUpdateEntityDescription, ...] = (
    PortainerServerUpdateEntityDescription(
        key="server_update",
        translation_key="server_update",
        entity_category=EntityCategory.CONFIG,
        installed_version=lambda data: data.server_version,
        # Portainer only reports the latest version when it is newer
        latest_version=lambda data: data.latest_version or data.server_version,
        release_url=lambda data: (
            f"https://github.com/portainer/portainer/releases/tag/{data.latest_version}"
            if data.latest_version
            else None
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PortainerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Portainer update entities based on a config entry."""
    coordinator = entry.runtime_data
    if TYPE_CHECKING:
        assert coordinator.system_version is not None
    async_add_entities(
        PortainerServerUpdateEntity(coordinator.system_version, entity_description)
        for entity_description in SERVER_UPDATES
    )

    def _async_add_new_containers(
        containers: list[tuple[PortainerCoordinatorData, PortainerContainerData]],
    ) -> None:
        """Add new container update entities."""

        async_add_entities(
            PortainerContainerImageUpdateEntity(
                coordinator,
                entity_description,
                container,
                endpoint,
            )
            for (endpoint, container) in containers
            for entity_description in CONTAINER_IMAGE
        )

    coordinator.new_containers_callbacks.append(_async_add_new_containers)
    _async_add_new_containers(
        [
            (endpoint, container)
            for endpoint in coordinator.data.values()
            for container in endpoint.containers.values()
        ]
    )


class PortainerContainerImageUpdateEntity(PortainerContainerEntity, UpdateEntity):
    """Representation of a Portainer container update."""

    _attr_supported_features = (
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS
    )

    entity_description: PortainerContainerUpdateEntityDescription

    def __init__(
        self,
        coordinator: PortainerCoordinator,
        entity_description: PortainerContainerUpdateEntityDescription,
        device_info: PortainerContainerData,
        via_device: PortainerCoordinatorData,
    ) -> None:
        """Initialize the Portainer update entity."""
        self.entity_description = entity_description
        super().__init__(coordinator, entity_description, device_info, via_device)

        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{self.device_name}_{entity_description.key}"

    @override
    @property
    def title(self) -> str | None:
        """Return title."""
        return self.device_name

    @override
    @property
    def installed_version(self) -> str | None:
        """Return installed version."""
        return self.entity_description.installed_version(
            self.container_data.local_image
        )

    @override
    @property
    def latest_version(self) -> str | None:
        """Return latest version."""
        return self.entity_description.latest_version(self.container_data.image_status)

    @override
    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install update."""
        self._attr_in_progress = True
        self.async_write_ha_state()
        try:
            await self.coordinator.async_call_portainer(self._async_pull_and_recreate())
        finally:
            self._attr_update_percentage = None
        await self.coordinator.async_request_refresh()

    async def _async_pull_and_recreate(self) -> None:
        """Pull the image with progress, then recreate the container with it."""
        config = self.container_data.container_inspect.config
        pulled = bool(config and config.image and await self._async_pull(config.image))
        if pulled:
            self._attr_update_percentage = PULL_PERCENTAGE
            self.async_write_ha_state()

        await self.coordinator.portainer.container_recreate(
            endpoint_id=self.endpoint_id,
            container_id=self.container_data.container.id,
            timeout=DEFAULT_RECREATE_TIMEOUT,
            pull_image=not pulled,
        )

    async def _async_pull(self, image: str) -> bool:
        """Pull the image with progress.

        Return False when Portainer has to pull it instead, for example from a
        private registry, whose credentials Portainer only adds to its own pulls.
        """
        progress = ImagePullProgress()
        try:
            async with asyncio.timeout(DEFAULT_RECREATE_TIMEOUT.total_seconds()):
                async for event in self.coordinator.portainer.image_pull(
                    self.endpoint_id, image
                ):
                    percentage = int(progress.update(event) * PULL_PERCENTAGE / 100)
                    if percentage != self._attr_update_percentage:
                        self._attr_update_percentage = percentage
                        self.async_write_ha_state()
        except TimeoutError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="timeout_connect",
            ) from err
        except PortainerAuthenticationError, PortainerTimeoutError:
            raise
        except PortainerError as err:
            _LOGGER.debug("Letting Portainer pull %s instead: %s", image, err)
            self._attr_update_percentage = None
            self.async_write_ha_state()
            return False
        return True


class PortainerServerUpdateEntity(PortainerServerEntity, UpdateEntity):
    """Representation of an update of Portainer itself."""

    _attr_title = "Portainer"

    entity_description: PortainerServerUpdateEntityDescription

    @override
    @property
    def installed_version(self) -> str | None:
        """Return the running Portainer version."""
        return self.entity_description.installed_version(self.coordinator.data)

    @override
    @property
    def latest_version(self) -> str | None:
        """Return the latest Portainer version."""
        return self.entity_description.latest_version(self.coordinator.data)

    @override
    @property
    def release_url(self) -> str | None:
        """Return the release notes of the latest version."""
        return self.entity_description.release_url(self.coordinator.data)

"""Support for Portainer container updates."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, override

from pyportainer import Portainer
from pyportainer.exceptions import (
    PortainerAuthenticationError,
    PortainerConnectionError,
)
from pyportainer.models.docker import (
    DockerContainer,
    LocalImageInformation,
    PortainerImageUpdateStatus,
)

from homeassistant.components.update import (
    UpdateEntity,
    UpdateEntityDescription,
    UpdateEntityFeature,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import (
    PortainerConfigEntry,
    PortainerContainerData,
    PortainerCoordinator,
    PortainerCoordinatorData,
)
from .entity import PortainerContainerEntity


@dataclass(frozen=True, kw_only=True)
class PortainerContainerUpdateEntityDescription(UpdateEntityDescription):
    """Describes Portainer container update entity."""

    installed_version: Callable[[LocalImageInformation], str | None]
    latest_version: Callable[[PortainerImageUpdateStatus | None], str | None]
    update_func: Callable[
        [Portainer, int, str],
        Awaitable[DockerContainer],
    ]


PARALLEL_UPDATES = 1
DEFAULT_RECREATE_TIMEOUT = timedelta(minutes=10)


def _short_digest(digest: str | None) -> str | None:
    """Return the first 12 hex characters of a sha256 digest, Docker-style."""
    if not digest:
        return None
    value = digest.split("@", 1)[-1]
    prefix, sep, short_hash = value.partition(":")
    return f"{prefix}{sep}{short_hash[:12]}" if sep else value[:12]


def _format_version(digest: str | None, repo_tags: list[str] | None) -> str | None:
    """Pair a shortened digest with its repo tag, e.g. `app:latest (2f3d3130beba)`."""
    short = _short_digest(digest)
    if not short:
        return None
    if repo_tags:
        return f"{repo_tags[0]} ({short})"
    return short


def _release_url(image: str | None) -> str | None:
    """Return a best-effort tag-page URL for Docker Hub or ghcr.io images."""
    if not image:
        return None
    repo, _, tag = image.partition(":")
    tag = tag or "latest"
    if repo.startswith("ghcr.io/"):
        owner_repo = repo.removeprefix("ghcr.io/")
        if owner_repo.count("/") != 1:
            return None
        owner, _, name = owner_repo.partition("/")
        return f"https://github.com/{owner}/{name}/pkgs/container/{name}"
    if repo.startswith("docker.io/"):
        path = repo.removeprefix("docker.io/")
        if path.startswith("library/"):
            name = path.removeprefix("library/")
            return f"https://hub.docker.com/_/{name}/tags?name={tag}"
        if path.count("/") == 1:
            return f"https://hub.docker.com/r/{path}/tags?name={tag}"
        return None
    if "." not in repo.split("/", 1)[0]:
        # No registry host prefix — Docker Hub bare name (e.g. ubuntu:latest).
        return f"https://hub.docker.com/r/{repo}/tags?name={tag}"
    return None


CONTAINER_IMAGE: tuple[PortainerContainerUpdateEntityDescription] = (
    PortainerContainerUpdateEntityDescription(
        key="container_image_update",
        translation_key="container_image_update",
        entity_category=EntityCategory.CONFIG,
        installed_version=lambda data: (
            data.repo_digests[0].split("@")[1]
            if data.repo_digests and isinstance(data.repo_digests[0], str)
            else None
        ),
        latest_version=lambda data: data.registry_digest if data is not None else None,
        update_func=(
            lambda portainer, endpoint_id, container_id: portainer.container_recreate(
                endpoint_id=endpoint_id,
                container_id=container_id,
                timeout=DEFAULT_RECREATE_TIMEOUT,
                pull_image=True,
            )
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

    _attr_supported_features = UpdateEntityFeature.INSTALL

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
        digest = self.entity_description.installed_version(
            self.container_data.local_image
        )
        return _format_version(digest, self.container_data.local_image.repo_tags)

    @override
    @property
    def latest_version(self) -> str | None:
        """Return latest version."""
        digest = self.entity_description.latest_version(
            self.container_data.image_status
        )
        return _format_version(digest, self.container_data.local_image.repo_tags)

    @override
    @property
    def release_url(self) -> str | None:
        """Return a link to the image's tag page, when the registry is recognized."""
        return _release_url(self.container_data.container.image)

    @override
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return image size in bytes and build date."""
        local_image = self.container_data.local_image
        attrs: dict[str, Any] = {}
        if local_image.size is not None:
            attrs["image_size"] = local_image.size
        if local_image.created and (
            created := dt_util.parse_datetime(local_image.created)
        ):
            attrs["image_created"] = created
        return attrs

    @override
    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install update."""
        try:
            await self.entity_description.update_func(
                self.coordinator.portainer,
                self.endpoint_id,
                self.container_data.container.id,
            )
        except PortainerAuthenticationError as ex:
            self.coordinator.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
            ) from ex
        except PortainerConnectionError as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            ) from ex
        else:
            await self.coordinator.async_request_refresh()

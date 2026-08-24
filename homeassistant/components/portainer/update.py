"""Support for Portainer container updates."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, override

from aiohttp import ClientError
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
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util, yaml as yaml_util

from .const import CONF_GITHUB_TOKEN, DOMAIN
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
RELEASE_NOTES_CACHE_TTL = timedelta(hours=1)


def _short_digest(digest: str | None) -> str | None:
    """Return the first 12 hex characters of a sha256 digest, Docker-style."""
    if not digest:
        return None
    value = digest.split("@", 1)[-1]
    prefix, sep, short_hash = value.partition(":")
    return f"{prefix}{sep}{short_hash[:12]}" if sep else value[:12]


def _format_version(digest: str | None, image: str | None) -> str | None:
    """Pair a shortened digest with the image reference.

    e.g. `app:latest (2f3d3130beba)`.
    """
    short = _short_digest(digest)
    if not short:
        return None
    if image:
        return f"{image} ({short})"
    return short


def _image_attributes(local_image: LocalImageInformation) -> dict[str, Any]:
    """Return image size in bytes and build date, when known."""
    attrs: dict[str, Any] = {}
    if local_image.size is not None:
        attrs["image_size"] = local_image.size
    if local_image.created and (created := dt_util.parse_datetime(local_image.created)):
        attrs["image_created"] = created
    return attrs


def _split_image_repo_tag(image: str) -> tuple[str, str]:
    """Split a Docker image reference into its repo and tag, ignoring registry ports."""
    path, _, last_segment = image.rpartition("/")
    name, sep, tag = last_segment.partition(":")
    repo = f"{path}/{name}" if path else name
    return repo, tag if sep else "latest"


def _ghcr_owner_repo(repo: str) -> tuple[str, str] | None:
    """Return (owner, name) for a ghcr.io/<owner>/<name> repo, else None."""
    if not repo.startswith("ghcr.io/"):
        return None
    owner_repo = repo.removeprefix("ghcr.io/")
    if owner_repo.count("/") != 1:
        return None
    owner, _, name = owner_repo.partition("/")
    return owner, name


def _linuxserver_app_name(repo: str) -> str | None:
    """Return the app name for an lscr.io/linuxserver/<app> repo, else None."""
    if not repo.startswith("lscr.io/linuxserver/"):
        return None
    name = repo.removeprefix("lscr.io/linuxserver/")
    return None if "/" in name else name


def _release_url(image: str | None) -> str | None:
    """Return a best-effort release-info URL for known registries."""
    if not image:
        return None
    repo, tag = _split_image_repo_tag(image)
    if (name := _linuxserver_app_name(repo)) is not None:
        return f"https://docs.linuxserver.io/images/docker-{name}/#versions"
    if (owner_name := _ghcr_owner_repo(repo)) is not None:
        owner, name = owner_name
        return f"https://github.com/{owner}/{name}/pkgs/container/{name}"
    if repo.startswith("docker.io/"):
        path = repo.removeprefix("docker.io/")
        if path.startswith("library/"):
            name = path.removeprefix("library/")
            return f"https://hub.docker.com/_/{name}/tags?name={tag}"
        if path.count("/") == 1:
            return f"https://hub.docker.com/r/{path}/tags?name={tag}"
        return None
    # A domain, a port, or "localhost" marks a private registry host, not Docker Hub.
    first_segment = repo.split("/", 1)[0]
    if "." in first_segment or ":" in first_segment or first_segment == "localhost":
        return None
    return f"https://hub.docker.com/r/{repo}/tags?name={tag}"


RELEASE_NOTES_TIMEOUT = 10
MAX_LINUXSERVER_CHANGELOG_ENTRIES = 10


def _github_headers(token: str | None, *, accept: str) -> dict[str, str]:
    """Build request headers for a GitHub call, adding auth when a token is set."""
    headers = {"Accept": accept}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


async def _fetch_ghcr_release_notes(
    hass: HomeAssistant, owner: str, name: str, token: str | None
) -> str | None:
    """Fetch the latest GitHub release body for a ghcr.io image."""
    session = aiohttp_client.async_get_clientsession(hass)
    try:
        async with asyncio.timeout(RELEASE_NOTES_TIMEOUT):
            response = await session.get(
                f"https://api.github.com/repos/{owner}/{name}/releases/latest",
                headers=_github_headers(token, accept="application/vnd.github+json"),
            )
            if response.status != 200:
                return None
            release = await response.json()
    except ClientError, TimeoutError:
        return None
    body = release.get("body")
    return body if isinstance(body, str) and body else None


async def _fetch_linuxserver_release_notes(
    hass: HomeAssistant, name: str, token: str | None
) -> str | None:
    """Fetch and format the most recent changelog entries for a linuxserver.io image."""
    session = aiohttp_client.async_get_clientsession(hass)
    url = (
        f"https://raw.githubusercontent.com/linuxserver/docker-{name}"
        "/master/readme-vars.yml"
    )
    try:
        async with asyncio.timeout(RELEASE_NOTES_TIMEOUT):
            response = await session.get(
                url, headers=_github_headers(token, accept="text/plain")
            )
            if response.status != 200:
                return None
            raw_yaml = await response.text()
    except ClientError, TimeoutError:
        return None
    try:
        data = yaml_util.parse_yaml(raw_yaml)
    except HomeAssistantError:
        return None
    if not isinstance(data, dict) or not isinstance(data.get("changelogs"), list):
        return None
    entries = [
        f"**{entry['date']}** {entry['desc']}"
        for entry in data["changelogs"][:MAX_LINUXSERVER_CHANGELOG_ENTRIES]
        if isinstance(entry, dict) and entry.get("date") and entry.get("desc")
    ]
    return "\n\n".join(entries) if entries else None


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

    _attr_supported_features = (
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.RELEASE_NOTES
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
        self._release_notes_cache: tuple[str, str | None, datetime] | None = None

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
        return _format_version(digest, self.container_data.container.image)

    @override
    @property
    def latest_version(self) -> str | None:
        """Return latest version."""
        digest = self.entity_description.latest_version(
            self.container_data.image_status
        )
        return _format_version(digest, self.container_data.container.image)

    @override
    @property
    def release_url(self) -> str | None:
        """Return a link to the image's tag page, when the registry is recognized."""
        return _release_url(self.container_data.container.image)

    @override
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return image size in bytes and build date."""
        return _image_attributes(self.container_data.local_image)

    @override
    async def async_release_notes(self) -> str | None:
        """Return full release notes, when the registry is recognized.

        Cached briefly since the image reference (e.g. an `:latest` tag) often
        stays the same across releases, so it can't be used as a cache key on
        its own without risking stale notes indefinitely.
        """
        image = self.container_data.container.image
        if not image:
            return None
        now = dt_util.utcnow()
        if self._release_notes_cache is not None:
            cached_image, cached_notes, expires = self._release_notes_cache
            if cached_image == image and now < expires:
                return cached_notes
        notes = await self._async_fetch_release_notes(image)
        self._release_notes_cache = (image, notes, now + RELEASE_NOTES_CACHE_TTL)
        return notes

    async def _async_fetch_release_notes(self, image: str) -> str | None:
        """Fetch release notes for an image, when the registry is recognized."""
        repo, _ = _split_image_repo_tag(image)
        token = self.coordinator.config_entry.data.get(CONF_GITHUB_TOKEN)
        if (name := _linuxserver_app_name(repo)) is not None:
            return await _fetch_linuxserver_release_notes(self.hass, name, token)
        if (owner_name := _ghcr_owner_repo(repo)) is not None:
            owner, name = owner_name
            return await _fetch_ghcr_release_notes(self.hass, owner, name, token)
        return None

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

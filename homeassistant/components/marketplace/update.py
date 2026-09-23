"""Update entities for the Marketplace."""

from typing import Any, override

from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .base import StoreConfigEntry
from .const import DOMAIN
from .entity import RepositoryEntity
from .enums import RepositoryCategory, StoreSignal
from .exceptions import StoreError


async def async_setup_entry(
    hass: HomeAssistant,
    entry: StoreConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Setup update platform."""
    store = entry.runtime_data
    async_add_entities(
        RepositoryUpdateEntity(store=store, repository=repository)
        for repository in store.repositories.list_downloaded
    )


class RepositoryUpdateEntity(RepositoryEntity, UpdateEntity):
    """Update entity for a downloaded repository."""

    _attr_supported_features = (
        UpdateEntityFeature.INSTALL
        | UpdateEntityFeature.SPECIFIC_VERSION
        | UpdateEntityFeature.PROGRESS
        | UpdateEntityFeature.RELEASE_NOTES
    )

    @property
    @override
    def name(self) -> str | None:
        """Return the name."""
        return f"{self.repository.display_name} update"

    @property
    @override
    def latest_version(self) -> str:
        """Return latest version of the entity."""
        return self.repository.display_available_version

    @property
    @override
    def release_url(self) -> str:
        """Return the URL of the release page."""
        if self.repository.display_version_or_commit == "commit":
            return f"https://github.com/{self.repository.data.full_name}"
        return f"https://github.com/{self.repository.data.full_name}/releases/{self.latest_version}"

    @property
    @override
    def installed_version(self) -> str:
        """Return downloaded version of the entity."""
        return self.repository.display_installed_version

    @property
    @override
    def release_summary(self) -> str | None:
        """Return the release summary."""
        if self.repository.pending_restart:
            return "<ha-alert alert-type='error'>Restart of Home Assistant required</ha-alert>"
        return None

    @property
    @override
    def entity_picture(self) -> str | None:
        """Return the entity picture to use in the frontend."""
        if (
            self.repository.data.category != RepositoryCategory.INTEGRATION
            or self.repository.data.domain is None
        ):
            return None

        return (
            f"https://brands.home-assistant.io/_/{self.repository.data.domain}/icon.png"
        )

    @override
    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""
        to_download = version or self.latest_version
        if to_download == self.installed_version:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="version_already_downloaded",
                translation_placeholders={
                    "repository": self.repository.data.full_name,
                    "version": self.installed_version,
                },
            )

        try:
            await self.repository.async_download_repository(ref=to_download)
        except StoreError as exception:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="download_failed",
                translation_placeholders={
                    "error": str(exception),
                    "repository": self.repository.data.full_name,
                },
            ) from exception

    @override
    async def async_release_notes(self) -> str | None:
        """Return the release notes."""
        if self.repository.pending_restart:
            return None

        if self.latest_version not in self.repository.data.published_tags:
            releases = await self.repository.get_releases(
                prerelease=self.repository.data.show_beta,
                returnlimit=self.store.configuration.release_limit,
            )
            if releases:
                self.repository.data.releases = True
                self.repository.releases.objects = releases
                self.repository.data.published_tags = [x.tag_name for x in releases]
                self.repository.data.last_version = next(
                    iter(self.repository.data.published_tags)
                )

        release_notes = ""
        # Compile release notes from installed version up to the latest
        if self.installed_version in self.repository.data.published_tags:
            for release in self.repository.releases.objects:
                if release.tag_name == self.installed_version:
                    break
                release_notes += f"# {release.tag_name}"
                if release.tag_name != release.name:
                    release_notes += f"  - {release.name}"
                release_notes += f"\n\n{release.body}"
                release_notes += "\n\n---\n\n"
        elif any(self.repository.releases.objects):
            release_notes += self.repository.releases.objects[0].body

        if self.repository.pending_update:
            if self.repository.data.category == RepositoryCategory.INTEGRATION:
                release_notes += (
                    "\n\n<ha-alert alert-type='warning'>You need to restart"
                    " Home Assistant manually after updating.</ha-alert>\n\n"
                )
            if self.repository.data.category == RepositoryCategory.PLUGIN:
                release_notes += (
                    "\n\n<ha-alert alert-type='warning'>You need to manually"
                    " clear the frontend cache after updating.</ha-alert>\n\n"
                )

        return release_notes.replace("\n#", "\n\n#")

    @override
    async def async_added_to_hass(self) -> None:
        """Register for status events."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                StoreSignal.REPOSITORY_DOWNLOAD_PROGRESS,
                self._update_download_progress,
            )
        )

    @callback
    def _update_download_progress(self, data: dict[str, Any]) -> None:
        """Update the download progress."""
        if data["repository"] != self.repository.data.full_name:
            return
        self._update_in_progress(progress=data["progress"])

    @callback
    def _update_in_progress(self, progress: int | bool) -> None:
        """Update the download progress."""
        self._attr_in_progress = progress is not False
        self._attr_update_percentage = progress if progress is not False else None
        self.async_write_ha_state()

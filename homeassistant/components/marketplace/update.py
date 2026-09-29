"""Update entities for the Marketplace."""

from typing import Any, override

import probatio

from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .base import MarketplaceConfigEntry
from .const import DOMAIN, RELEASE_LIMIT
from .entity import RepositoryEntity
from .enums import MarketplaceSignal, RepositoryCategory
from .exceptions import GitHubAnonymousRateLimitError, MarketplaceError
from .utils.logger import LOGGER
from .utils.validate import valid_ref


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MarketplaceConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Setup update platform."""
    marketplace = entry.runtime_data
    async_add_entities(
        RepositoryUpdateEntity(marketplace=marketplace, repository=repository)
        for repository in marketplace.repositories.list_installed
    )


class RepositoryUpdateEntity(RepositoryEntity, UpdateEntity):
    """Update entity for an installed repository."""

    # Updating is what the device of a repository is for, it carries the name
    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = (
        UpdateEntityFeature.INSTALL
        | UpdateEntityFeature.SPECIFIC_VERSION
        | UpdateEntityFeature.PROGRESS
        | UpdateEntityFeature.RELEASE_NOTES
    )

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
        """Return installed version of the entity."""
        return self.repository.display_installed_version

    @property
    @override
    def entity_picture(self) -> str | None:
        """Return the entity picture to use in the frontend."""
        if (
            self.repository.data.category != RepositoryCategory.INTEGRATION
            or self.repository.data.domain is None
        ):
            return None

        # Served by Home Assistant, which prefers the icon an integration ships
        return f"/api/brands/integration/{self.repository.data.domain}/icon.png"

    @override
    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""
        if version is not None:
            try:
                valid_ref(version)
            except probatio.Invalid as exception:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="invalid_version",
                    translation_placeholders={"version": version},
                ) from exception

        user_id = self._context.user_id if self._context else None

        # Automations and scripts run without a user, someone has to have read it
        if user_id is None:
            warning_accepted = bool(self.marketplace.warning_acceptances)
        else:
            warning_accepted = self.marketplace.warning_accepted(user_id)

        if not warning_accepted:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="warning_not_accepted",
            )

        to_install = version or self.latest_version
        if to_install == self.installed_version:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="version_already_installed",
                translation_placeholders={
                    "repository": self.repository.data.full_name,
                    "version": self.installed_version,
                },
            )

        try:
            await self.repository.async_install_repository(ref=to_install)
        except GitHubAnonymousRateLimitError as exception:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="github_rate_limited",
            ) from exception
        except MarketplaceError as exception:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="install_failed",
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
            # The notes are best effort, the releases known already still help
            try:
                releases = await self.repository.get_releases(
                    prerelease=self.repository.data.show_beta,
                    returnlimit=RELEASE_LIMIT,
                )
            except MarketplaceError as exception:
                LOGGER.debug(
                    "Could not get the releases of %s: %s",
                    self.repository.data.full_name,
                    exception,
                )
                releases = []
            if releases:
                self.repository.data.releases = True
                self.repository.releases.objects = releases
                self.repository.data.published_tags = [x.tag_name for x in releases]
                # Fetched with pre-releases when those are shown, they are not stable
                self.repository.data.last_version = next(
                    (
                        release.tag_name
                        for release in releases
                        if not release.prerelease
                    ),
                    self.repository.data.last_version,
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

        return release_notes.replace("\n#", "\n\n#")

    @override
    async def async_added_to_hass(self) -> None:
        """Register for status events."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                MarketplaceSignal.REPOSITORY_INSTALL_PROGRESS,
                self._update_install_progress,
            )
        )

    @callback
    def _update_install_progress(self, data: dict[str, Any]) -> None:
        """Update the install progress."""
        if data["repository"] != self.repository.data.full_name:
            return
        self._update_in_progress(progress=data["progress"])

    @callback
    def _update_in_progress(self, progress: int | bool) -> None:
        """Update the install progress."""
        self._attr_in_progress = progress is not False
        self._attr_update_percentage = progress if progress is not False else None
        self.async_write_ha_state()

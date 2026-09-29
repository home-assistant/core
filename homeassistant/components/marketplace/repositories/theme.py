"""Class for theme repositories."""

import os
from pathlib import Path
from typing import TYPE_CHECKING, override

from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.yaml import load_yaml

from ..enums import MarketplaceSignal, RepositoryCategory
from ..exceptions import MarketplaceError
from ..utils.decorator import concurrent
from ..utils.tree import tree_entry_filename
from ..utils.url import ref_version
from .base import Repository

if TYPE_CHECKING:
    from ..base import MarketplaceManager


class ThemeRepository(Repository):
    """Theme repository."""

    remote_path = "themes"

    def __init__(self, marketplace: MarketplaceManager, full_name: str) -> None:
        """Initialize."""
        super().__init__(marketplace=marketplace)
        self.data.full_name = full_name
        self.data.category = RepositoryCategory.THEME
        self.content.path.local = self.localpath

    @property
    @override
    def localpath(self) -> str:
        """Return localpath."""
        return f"{self.marketplace.core.config_path}/themes/{self.data.file_name.replace('.yaml', '')}"

    @override
    async def async_pre_install(self) -> None:
        """Run pre install steps."""
        # The folder is named after the theme file, other themes can use that name
        for repository in self.marketplace.repositories.list_downloaded:
            if (
                repository is not self
                and repository.data.category == RepositoryCategory.THEME
                and repository.localpath == self.localpath
            ):
                raise MarketplaceError(
                    f"The '{Path(self.localpath).name}' theme folder is owned by"
                    f" {repository.data.full_name}"
                )

    @override
    async def async_post_installation(self) -> None:
        """Run post installation steps."""
        await self._reload_frontend_themes()

    @override
    async def async_check_written_content(self) -> None:
        """Refuse a theme that is not valid YAML.

        Themes are included in configuration.yaml, a broken one stops
        Home Assistant from loading its configuration at the next start.
        """

        def _check() -> None:
            for theme in Path(self.content.path.local).rglob("*.yaml"):
                try:
                    load_yaml(theme)
                except HomeAssistantError as exception:
                    raise MarketplaceError(
                        f"{theme.name} is not valid YAML: {exception}"
                    ) from exception

        await self.marketplace.hass.async_add_executor_job(_check)

    @override
    async def validate_repository(self) -> bool:
        """Validate."""
        # Run common validation steps.
        await self.common_validate()

        # Custom step 1: Validate content.
        self.resolve_content()

        # Handle potential errors
        if self.validate.errors:
            for error in self.validate.errors:
                if not self.marketplace.status.startup:
                    self.logger.error("%s %s", self.string, error)
        return self.validate.success

    @override
    def resolve_content(self) -> None:
        """Point the content at the theme in the tree."""
        directory = "" if self.repository_manifest.content_in_root else "themes"
        if not any(
            os.path.dirname(treefile) == directory and treefile.endswith(".yaml")
            for treefile in self.treefiles
        ):
            raise MarketplaceError(
                f"{self.string} Repository structure for {ref_version(self.ref)} is not compliant"
            )

        if self.repository_manifest.content_in_root:
            self.content.path.remote = ""

    @override
    def resolve_archive_content(self) -> None:
        """Point the content at the theme in the archive."""
        self.resolve_content()
        self.update_filenames()
        self.content.path.local = self.localpath

    @override
    async def async_post_registration(self) -> None:
        """Registration."""
        # Set name
        self.update_filenames()
        self.content.path.local = self.localpath

    async def _reload_frontend_themes(self) -> None:
        """Reload frontend themes."""
        self.logger.debug("%s Reloading frontend themes", self.string)
        try:
            await self.marketplace.hass.services.async_call(
                "frontend", "reload_themes", {}
            )
        except HomeAssistantError:
            self.logger.exception("%s Reloading frontend themes failed", self.string)

    @override
    async def async_post_uninstall(self) -> None:
        """Run post uninstall steps."""
        await self._reload_frontend_themes()

    @override
    @concurrent(concurrenttasks=10)
    async def update_repository(
        self, ignore_issues: bool = False, force: bool = False
    ) -> None:
        """Update."""
        if not await self.common_update(ignore_issues, force) and not force:
            return

        # Get theme objects.
        if self.repository_manifest.content_in_root:
            self.content.path.remote = ""

        # Update name
        self.update_filenames()
        self.content.path.local = self.localpath

        # Signal frontend to refresh
        if self.data.installed:
            self.marketplace.async_dispatch(
                MarketplaceSignal.REPOSITORY,
                {
                    "id": 1337,
                    "action": "update",
                    "repository": self.data.full_name,
                    "repository_id": self.data.id,
                },
            )

    @override
    def update_filenames(self) -> None:
        """Get the filename to target."""
        for entry in self.tree:
            if entry.path.startswith(self.content.path.remote) and entry.path.endswith(
                ".yaml"
            ):
                self.data.file_name = tree_entry_filename(entry)

"""Class for theme repositories."""

import os
from pathlib import Path
from typing import TYPE_CHECKING, override

import probatio
import yaml

from homeassistant.components.frontend import (
    CONF_THEMES,
    CONFIG_SCHEMA as FRONTEND_CONFIG_SCHEMA,
    DOMAIN as FRONTEND_DOMAIN,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.yaml import load_yaml

from ..enums import RepositoryCategory
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
        return f"{self.marketplace.core.config_path}/themes/{self.directory}"

    @property
    def directory(self) -> str:
        """Return the folder of the theme, the one it was installed to."""
        return self.data.directory or self.data.file_name.replace(".yaml", "")

    @override
    async def async_pre_install(self) -> None:
        """Run pre install steps."""
        # The folder is named after the theme file, other themes can use that name
        for repository in self.marketplace.repositories.list_installed:
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
        self.data.directory = self.directory
        await self._reload_frontend_themes()

    @override
    async def async_check_written_content(self) -> None:
        """Refuse a theme the frontend can not load.

        Themes are included in configuration.yaml, a broken one stops
        Home Assistant from loading its configuration at the next start. No
        tags either: a theme is served to every user, an include would hand
        them whatever file it points at.
        """

        def _check() -> None:
            for theme in Path(self.content.path.local).rglob("*.yaml"):
                # The plain loader refuses the tags, the loader of Home Assistant
                # reads it the way the include in configuration.yaml does
                try:
                    yaml.safe_load(theme.read_text(encoding="utf-8"))
                    themes = load_yaml(theme)
                except (
                    HomeAssistantError,
                    UnicodeDecodeError,
                    yaml.YAMLError,
                ) as exception:
                    raise MarketplaceError(
                        f"{theme.name} is not valid YAML: {exception}"
                    ) from exception

                # The include only merges a mapping, anything else is left out
                if not isinstance(themes, dict):
                    continue

                try:
                    FRONTEND_CONFIG_SCHEMA({FRONTEND_DOMAIN: {CONF_THEMES: themes}})
                except probatio.Invalid as exception:
                    raise MarketplaceError(
                        f"{theme.name} is not a valid theme: {exception}"
                    ) from exception

        await self.marketplace.hass.async_add_executor_job(_check)

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
        """Point the content at the file to install."""
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
        # Installed again, the theme goes to the folder of its current file
        self.data.directory = None
        await self._reload_frontend_themes()

    @override
    @concurrent(concurrenttasks=10)
    async def update_repository(
        self, ignore_issues: bool = False, force: bool = False
    ) -> None:
        """Refresh the repository from GitHub."""
        if not await self.common_update(ignore_issues, force) and not force:
            return

        if self.repository_manifest.content_in_root:
            self.content.path.remote = ""

        self.update_filenames()
        self.content.path.local = self.localpath

        if self.data.installed:
            self.async_dispatch_changed("update")

    @override
    def update_filenames(self) -> None:
        """Get the filename to target."""
        # Only the folder validation checked, an example below it is not the theme
        directory = (self.content.path.remote or "").strip("/")
        for entry in self.tree:
            if os.path.dirname(entry.path) == directory and entry.path.endswith(
                ".yaml"
            ):
                self.data.file_name = tree_entry_filename(entry)

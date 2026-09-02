"""Class for themes in HACS."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.exceptions import HomeAssistantError

from ..enums import HacsCategory, HacsDispatchEvent
from ..exceptions import HacsException
from ..utils.decorator import concurrent
from .base import HacsRepository

if TYPE_CHECKING:
    from ..base import HacsBase


class HacsThemeRepository(HacsRepository):
    """Themes in HACS."""

    def __init__(self, hacs: HacsBase, full_name: str):
        """Initialize."""
        super().__init__(hacs=hacs)
        self.data.full_name = full_name
        self.data.full_name_lower = full_name.lower()
        self.data.category = HacsCategory.THEME
        self.content.path.remote = "themes"
        self.content.path.local = self.localpath
        self.content.single = False

    @property
    def localpath(self):
        """Return localpath."""
        return f"{self.hacs.core.config_path}/themes/{self.data.file_name.replace('.yaml', '')}"

    async def async_post_installation(self):
        """Run post installation steps."""
        await self._reload_frontend_themes()

    async def validate_repository(self):
        """Validate."""
        # Run common validation steps.
        await self.common_validate()

        # Custom step 1: Validate content.
        compliant = False
        for treefile in self.treefiles:
            if treefile.startswith("themes/") and treefile.endswith(".yaml"):
                compliant = True
                break
        if not compliant:
            raise HacsException(
                f"{self.string} Repository structure for {self.ref.replace('tags/', '')} is not compliant"
            )

        if self.repository_manifest.content_in_root:
            self.content.path.remote = ""

        # Handle potential errors
        if self.validate.errors:
            for error in self.validate.errors:
                if not self.hacs.status.startup:
                    self.logger.error("%s %s", self.string, error)
        return self.validate.success

    async def async_post_registration(self):
        """Registration."""
        # Set name
        self.update_filenames()
        self.content.path.local = self.localpath

        if self.hacs.system.action:
            await self.hacs.validation.async_run_repository_checks(self)

    async def _reload_frontend_themes(self) -> None:
        """Reload frontend themes."""
        self.logger.debug("%s Reloading frontend themes", self.string)
        try:
            await self.hacs.hass.services.async_call("frontend", "reload_themes", {})
        except HomeAssistantError as exception:
            self.logger.exception("%s %s", self.string, exception)

    async def async_post_uninstall(self) -> None:
        """Run post uninstall steps."""
        await self._reload_frontend_themes()

    @concurrent(concurrenttasks=10, backoff_time=5)
    async def update_repository(self, ignore_issues=False, force=False):
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
            self.hacs.async_dispatch(
                HacsDispatchEvent.REPOSITORY,
                {
                    "id": 1337,
                    "action": "update",
                    "repository": self.data.full_name,
                    "repository_id": self.data.id,
                },
            )

    def update_filenames(self) -> None:
        """Get the filename to target."""
        for treefile in self.tree:
            if treefile.full_path.startswith(
                self.content.path.remote
            ) and treefile.full_path.endswith(".yaml"):
                self.data.file_name = treefile.filename

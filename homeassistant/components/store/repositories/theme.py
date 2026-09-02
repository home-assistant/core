"""Class for themes in HACS."""

from typing import TYPE_CHECKING, override

from homeassistant.exceptions import HomeAssistantError

from ..enums import HacsCategory, HacsDispatchEvent
from ..exceptions import HacsException
from ..utils.decorator import concurrent
from .base import HacsRepository

if TYPE_CHECKING:
    from ..base import HacsBase


class HacsThemeRepository(HacsRepository):
    """Themes in HACS."""

    def __init__(self, hacs: HacsBase, full_name: str) -> None:
        """Initialize."""
        super().__init__(hacs=hacs)
        self.data.full_name = full_name
        self.data.full_name_lower = full_name.lower()
        self.data.category = HacsCategory.THEME
        self.content.path.remote = "themes"
        self.content.path.local = self.localpath
        self.content.single = False

    @property
    @override
    def localpath(self) -> str:
        """Return localpath."""
        return f"{self.hacs.core.config_path}/themes/{self.data.file_name.replace('.yaml', '')}"

    @override
    async def async_post_installation(self) -> None:
        """Run post installation steps."""
        await self._reload_frontend_themes()

    @override
    async def validate_repository(self) -> bool:
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
                f"{self.string} Repository structure for {f'{self.ref}'.replace('tags/', '')} is not compliant"
            )

        if self.repository_manifest.content_in_root:
            self.content.path.remote = ""

        # Handle potential errors
        if self.validate.errors:
            for error in self.validate.errors:
                if not self.hacs.status.startup:
                    self.logger.error("%s %s", self.string, error)
        return self.validate.success

    @override
    async def async_post_registration(self) -> None:
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
        except HomeAssistantError:
            self.logger.exception("%s Reloading frontend themes failed", self.string)

    @override
    async def async_post_uninstall(self) -> None:
        """Run post uninstall steps."""
        await self._reload_frontend_themes()

    @override
    @concurrent(concurrenttasks=10, backoff_time=5)
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
            self.hacs.async_dispatch(
                HacsDispatchEvent.REPOSITORY,
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
        for treefile in self.tree:
            if treefile.full_path.startswith(
                self.content.path.remote
            ) and treefile.full_path.endswith(".yaml"):
                self.data.file_name = treefile.filename

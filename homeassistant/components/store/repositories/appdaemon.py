"""Class for appdaemon apps in HACS."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..enums import HacsCategory, HacsDispatchEvent
from ..exceptions import HacsException
from ..utils.decorator import concurrent
from ..utils.filters import get_first_directory_in_directory
from .base import HacsRepository

if TYPE_CHECKING:
    from ..base import HacsBase


class HacsAppdaemonRepository(HacsRepository):
    """Appdaemon apps in HACS."""

    def __init__(self, hacs: HacsBase, full_name: str):
        """Initialize."""
        super().__init__(hacs=hacs)
        self.data.full_name = full_name
        self.data.full_name_lower = full_name.lower()
        self.data.category = HacsCategory.APPDAEMON
        self.content.path.local = self.localpath
        self.content.path.remote = "apps"

    @property
    def localpath(self):
        """Return localpath."""
        return f"{self.hacs.core.config_path}/appdaemon/apps/{self.data.name}"

    async def validate_repository(self) -> bool:
        """Validate."""
        await self.common_validate()

        # Custom step 1: Validate content.
        # Find the first directory under apps/
        self.content.path.remote = f"apps/{self._get_apps_directory_from_tree()}"

        # Handle potential errors
        if self.validate.errors:
            for error in self.validate.errors:
                if not self.hacs.status.startup:
                    self.logger.error("%s %s", self.string, error)
        return self.validate.success

    @concurrent(concurrenttasks=10, backoff_time=5)
    async def update_repository(self, ignore_issues: bool = False, force: bool = False) -> None:
        """Update."""
        if not await self.common_update(ignore_issues, force) and not force:
            return

        # Get appdaemon objects.
        if self.repository_manifest:
            if self.repository_manifest.content_in_root:
                self.content.path.remote = ""

        if self.content.path.remote == "apps":
            self.content.path.remote = f"apps/{self._get_apps_directory_from_tree()}"

        # Set local path
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

    def _get_apps_directory_from_tree(self) -> str:
        """Get the first apps directory from the repository tree."""
        if not (app_dir := get_first_directory_in_directory(self.tree, "apps")):
            raise HacsException(
                f"{self.string} Repository structure for {self.ref.replace('tags/', '')} is not compliant. "
                "Expected to find at least one directory under '<root>/apps/'"
            )
        return app_dir

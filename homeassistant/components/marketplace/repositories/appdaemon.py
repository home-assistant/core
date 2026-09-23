"""Class for AppDaemon app repositories."""

from typing import TYPE_CHECKING, override

from ..enums import MarketplaceSignal, RepositoryCategory
from ..exceptions import MarketplaceError
from ..utils.decorator import concurrent
from ..utils.filters import get_first_directory_in_directory
from .base import Repository

if TYPE_CHECKING:
    from ..base import MarketplaceManager


class AppdaemonRepository(Repository):
    """AppDaemon app repository."""

    def __init__(self, marketplace: MarketplaceManager, full_name: str) -> None:
        """Initialize."""
        super().__init__(marketplace=marketplace)
        self.data.full_name = full_name
        self.data.full_name_lower = full_name.lower()
        self.data.category = RepositoryCategory.APPDAEMON
        self.content.path.local = self.localpath
        self.content.path.remote = "apps"

    @property
    @override
    def localpath(self) -> str:
        """Return localpath."""
        return f"{self.marketplace.core.config_path}/appdaemon/apps/{self.data.name}"

    @override
    async def validate_repository(self) -> bool:
        """Validate."""
        await self.common_validate()

        # Custom step 1: Validate content.
        # Find the first directory under apps/
        self.content.path.remote = f"apps/{self._get_apps_directory_from_tree()}"

        # Handle potential errors
        if self.validate.errors:
            for error in self.validate.errors:
                if not self.marketplace.status.startup:
                    self.logger.error("%s %s", self.string, error)
        return self.validate.success

    @override
    @concurrent(concurrenttasks=10, backoff_time=5)
    async def update_repository(
        self, ignore_issues: bool = False, force: bool = False
    ) -> None:
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
            self.marketplace.async_dispatch(
                MarketplaceSignal.REPOSITORY,
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
            raise MarketplaceError(
                f"{self.string} Repository structure for {f'{self.ref}'.replace('tags/', '')} is not compliant. "
                "Expected to find at least one directory under '<root>/apps/'"
            )
        return app_dir

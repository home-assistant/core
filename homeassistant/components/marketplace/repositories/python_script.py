"""Class for python_script repositories."""

from typing import TYPE_CHECKING, override

from ..enums import MarketplaceSignal, RepositoryCategory
from ..exceptions import MarketplaceError
from ..utils.decorator import concurrent
from ..utils.tree import tree_entry_filename
from .base import Repository

if TYPE_CHECKING:
    from ..base import MarketplaceManager


class PythonScriptRepository(Repository):
    """Python script repository."""

    category = "python_script"

    def __init__(self, marketplace: MarketplaceManager, full_name: str) -> None:
        """Initialize."""
        super().__init__(marketplace=marketplace)
        self.data.full_name = full_name
        self.data.full_name_lower = full_name.lower()
        self.data.category = RepositoryCategory.PYTHON_SCRIPT
        self.content.path.remote = "python_scripts"
        self.content.path.local = self.localpath
        self.content.single = True

    @property
    @override
    def localpath(self) -> str:
        """Return localpath."""
        return f"{self.marketplace.core.config_path}/python_scripts"

    @override
    async def validate_repository(self) -> bool:
        """Validate."""
        # Run common validation steps.
        await self.common_validate()

        # Custom step 1: Validate content.
        if self.repository_manifest.content_in_root:
            self.content.path.remote = ""

        compliant = False
        for treefile in self.treefiles:
            if treefile.startswith(f"{self.content.path.remote}") and treefile.endswith(
                ".py"
            ):
                compliant = True
                break
        if not compliant:
            raise MarketplaceError(
                f"{self.string} Repository structure for {f'{self.ref}'.replace('tags/', '')} is not compliant"
            )

        # Handle potential errors
        if self.validate.errors:
            for error in self.validate.errors:
                if not self.marketplace.status.startup:
                    self.logger.error("%s %s", self.string, error)
        return self.validate.success

    @override
    async def async_post_registration(self) -> None:
        """Registration."""
        # Set name
        self.update_filenames()

    @override
    @concurrent(concurrenttasks=10, backoff_time=5)
    async def update_repository(
        self, ignore_issues: bool = False, force: bool = False
    ) -> None:
        """Update."""
        if not await self.common_update(ignore_issues, force) and not force:
            return

        # Get python_script objects.
        if self.repository_manifest.content_in_root:
            self.content.path.remote = ""

        compliant = False
        for treefile in self.treefiles:
            if treefile.startswith(f"{self.content.path.remote}") and treefile.endswith(
                ".py"
            ):
                compliant = True
                break
        if not compliant:
            raise MarketplaceError(
                f"{self.string} Repository structure for {f'{self.ref}'.replace('tags/', '')} is not compliant"
            )

        # Update name
        self.update_filenames()

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
                ".py"
            ):
                self.data.file_name = tree_entry_filename(entry)

"""Class for python_scripts in HACS."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..enums import HacsCategory, HacsDispatchEvent
from ..exceptions import HacsException
from ..utils.decorator import concurrent
from .base import HacsRepository

if TYPE_CHECKING:
    from ..base import HacsBase


class HacsPythonScriptRepository(HacsRepository):
    """python_scripts in HACS."""

    category = "python_script"

    def __init__(self, hacs: HacsBase, full_name: str):
        """Initialize."""
        super().__init__(hacs=hacs)
        self.data.full_name = full_name
        self.data.full_name_lower = full_name.lower()
        self.data.category = HacsCategory.PYTHON_SCRIPT
        self.content.path.remote = "python_scripts"
        self.content.path.local = self.localpath
        self.content.single = True

    @property
    def localpath(self):
        """Return localpath."""
        return f"{self.hacs.core.config_path}/python_scripts"

    async def validate_repository(self):
        """Validate."""
        # Run common validation steps.
        await self.common_validate()

        # Custom step 1: Validate content.
        if self.repository_manifest.content_in_root:
            self.content.path.remote = ""

        compliant = False
        for treefile in self.treefiles:
            if treefile.startswith(f"{self.content.path.remote}") and treefile.endswith(".py"):
                compliant = True
                break
        if not compliant:
            raise HacsException(
                f"{self.string} Repository structure for {self.ref.replace('tags/', '')} is not compliant"
            )

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

        if self.hacs.system.action:
            await self.hacs.validation.async_run_repository_checks(self)

    @concurrent(concurrenttasks=10, backoff_time=5)
    async def update_repository(self, ignore_issues=False, force=False):
        """Update."""
        if not await self.common_update(ignore_issues, force) and not force:
            return

        # Get python_script objects.
        if self.repository_manifest.content_in_root:
            self.content.path.remote = ""

        compliant = False
        for treefile in self.treefiles:
            if treefile.startswith(f"{self.content.path.remote}") and treefile.endswith(".py"):
                compliant = True
                break
        if not compliant:
            raise HacsException(
                f"{self.string} Repository structure for {self.ref.replace('tags/', '')} is not compliant"
            )

        # Update name
        self.update_filenames()

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
            ) and treefile.full_path.endswith(".py"):
                self.data.file_name = treefile.filename

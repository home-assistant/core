"""Class for template repositories."""

from typing import TYPE_CHECKING, override

from homeassistant.exceptions import HomeAssistantError

from ..enums import RepositoryCategory, StoreSignal
from ..exceptions import StoreError
from ..utils.decorator import concurrent
from .base import Repository

if TYPE_CHECKING:
    from ..base import StoreManager


class TemplateRepository(Repository):
    """Template repository."""

    def __init__(self, store: StoreManager, full_name: str) -> None:
        """Initialize."""
        super().__init__(store=store)
        self.data.full_name = full_name
        self.data.full_name_lower = full_name.lower()
        self.data.category = RepositoryCategory.TEMPLATE
        self.content.path.remote = ""
        self.content.path.local = self.localpath
        self.content.single = True

    @property
    @override
    def localpath(self) -> str:
        """Return localpath."""
        return f"{self.store.core.config_path}/custom_templates"

    @override
    async def async_post_installation(self) -> None:
        """Run post installation steps."""
        await self._reload_custom_templates()

    @override
    async def validate_repository(self) -> bool:
        """Validate."""
        # Run common validation steps.
        await self.common_validate()

        # Custom step 1: Validate content.
        self.data.file_name = self.repository_manifest.filename or ""

        if (
            not self.data.file_name
            or "/" in self.data.file_name
            or not self.data.file_name.endswith(".jinja")
            or self.data.file_name not in self.treefiles
        ):
            raise StoreError(
                f"{self.string} Repository structure for {f'{self.ref}'.replace('tags/', '')} is not compliant"
            )

        # Handle potential errors
        if self.validate.errors:
            for error in self.validate.errors:
                if not self.store.status.startup:
                    self.logger.error("%s %s", self.string, error)
        return self.validate.success

    @override
    async def async_post_registration(self) -> None:
        """Registration."""
        # Set filenames
        self.data.file_name = self.repository_manifest.filename or ""
        self.content.path.local = self.localpath

    @override
    async def async_post_uninstall(self) -> None:
        """Run post uninstall steps."""
        await self._reload_custom_templates()

    async def _reload_custom_templates(self) -> None:
        """Reload custom templates."""
        self.logger.debug("%s Reloading custom templates", self.string)
        try:
            await self.store.hass.services.async_call(
                "homeassistant", "reload_custom_templates", {}
            )
        except HomeAssistantError:
            self.logger.exception("%s Reloading custom templates failed", self.string)

    @override
    @concurrent(concurrenttasks=10, backoff_time=5)
    async def update_repository(
        self, ignore_issues: bool = False, force: bool = False
    ) -> None:
        """Update."""
        if not await self.common_update(ignore_issues, force) and not force:
            return

        # Update filenames
        self.data.file_name = self.repository_manifest.filename or ""
        self.content.path.local = self.localpath

        # Signal frontend to refresh
        if self.data.installed:
            self.store.async_dispatch(
                StoreSignal.REPOSITORY,
                {
                    "id": 1337,
                    "action": "update",
                    "repository": self.data.full_name,
                    "repository_id": self.data.id,
                },
            )

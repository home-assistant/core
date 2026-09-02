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


class HacsTemplateRepository(HacsRepository):
    """Custom templates in HACS."""

    def __init__(self, hacs: HacsBase, full_name: str):
        """Initialize."""
        super().__init__(hacs=hacs)
        self.data.full_name = full_name
        self.data.full_name_lower = full_name.lower()
        self.data.category = HacsCategory.TEMPLATE
        self.content.path.remote = ""
        self.content.path.local = self.localpath
        self.content.single = True

    @property
    def localpath(self):
        """Return localpath."""
        return f"{self.hacs.core.config_path}/custom_templates"

    async def async_post_installation(self):
        """Run post installation steps."""
        await self._reload_custom_templates()

    async def validate_repository(self):
        """Validate."""
        # Run common validation steps.
        await self.common_validate()

        # Custom step 1: Validate content.
        self.data.file_name = self.repository_manifest.filename

        if (
            not self.data.file_name
            or "/" in self.data.file_name
            or not self.data.file_name.endswith(".jinja")
            or self.data.file_name not in self.treefiles
        ):
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
        # Set filenames
        self.data.file_name = self.repository_manifest.filename
        self.content.path.local = self.localpath

        if self.hacs.system.action:
            await self.hacs.validation.async_run_repository_checks(self)

    async def async_post_uninstall(self) -> None:
        """Run post uninstall steps."""
        await self._reload_custom_templates()

    async def _reload_custom_templates(self) -> None:
        """Reload custom templates."""
        self.logger.debug("%s Reloading custom templates", self.string)
        try:
            await self.hacs.hass.services.async_call("homeassistant", "reload_custom_templates", {})
        except HomeAssistantError as exception:
            self.logger.exception("%s %s", self.string, exception)

    @concurrent(concurrenttasks=10, backoff_time=5)
    async def update_repository(self, ignore_issues=False, force=False):
        """Update."""
        if not await self.common_update(ignore_issues, force) and not force:
            return

        # Update filenames
        self.data.file_name = self.repository_manifest.filename
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

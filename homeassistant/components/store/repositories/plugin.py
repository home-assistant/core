"""Class for plugins in HACS."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from ..enums import HacsCategory, HacsDispatchEvent
from ..exceptions import HacsException
from ..utils.decorator import concurrent
from .base import HacsRepository

HACSTAG_REPLACER = re.compile(r"\D+")

if TYPE_CHECKING:
    from homeassistant.components.lovelace.resources import ResourceStorageCollection

    from ..base import HacsBase


class HacsPluginRepository(HacsRepository):
    """Plugins in HACS."""

    def __init__(self, hacs: HacsBase, full_name: str):
        """Initialize."""
        super().__init__(hacs=hacs)
        self.data.full_name = full_name
        self.data.full_name_lower = full_name.lower()
        self.data.file_name = None
        self.data.category = HacsCategory.PLUGIN
        self.content.path.local = self.localpath

    @property
    def localpath(self):
        """Return localpath."""
        return f"{self.hacs.core.config_path}/www/community/{self.data.full_name.split('/')[-1]}"

    async def validate_repository(self):
        """Validate."""
        # Run common validation steps.
        await self.common_validate()

        # Custom step 1: Validate content.
        self.update_filenames()

        if self.content.path.remote is None:
            raise HacsException(
                f"{self.string} Repository structure for {self.ref.replace('tags/', '')} is not compliant"
            )

        if self.content.path.remote == "release":
            self.content.single = True

        # Handle potential errors
        if self.validate.errors:
            for error in self.validate.errors:
                if not self.hacs.status.startup:
                    self.logger.error("%s %s", self.string, error)
        return self.validate.success

    async def async_post_installation(self):
        """Run post installation steps."""
        await self.hacs.async_setup_frontend_endpoint_plugin()
        await self.update_dashboard_resources()

    async def async_post_uninstall(self):
        """Run post uninstall steps."""
        await self.remove_dashboard_resources()

    @concurrent(concurrenttasks=10, backoff_time=5)
    async def update_repository(self, ignore_issues=False, force=False):
        """Update."""
        if not await self.common_update(ignore_issues, force) and not force:
            return

        # Get plugin objects.
        self.update_filenames()

        if self.content.path.remote is None:
            self.validate.errors.append(
                f"{self.string} Repository structure for {self.ref.replace('tags/', '')} is not compliant"
            )

        if self.content.path.remote == "release":
            self.content.single = True

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
        content_in_root = self.repository_manifest.content_in_root
        if specific_filename := self.repository_manifest.filename:
            valid_filenames = (specific_filename,)
        else:
            valid_filenames = (
                f"{self.data.name.replace('lovelace-', '')}.js",
                f"{self.data.name}.js",
                f"{self.data.name}.umd.js",
                f"{self.data.name}-bundle.js",
            )

        if not content_in_root:
            if self.releases.objects:
                release = self.releases.objects[0]
                if release.assets:
                    if assetnames := [
                        filename
                        for filename in valid_filenames
                        for asset in release.assets
                        if filename == asset.name
                    ]:
                        self.data.file_name = assetnames[0]
                        self.content.path.remote = "release"
                        return

        all_paths = {x.full_path for x in self.tree}
        for filename in valid_filenames:
            if filename in all_paths:
                self.data.file_name = filename
                self.content.path.remote = ""
                return
            if not content_in_root and f"dist/{filename}" in all_paths:
                self.data.file_name = filename.split("/")[-1]
                self.content.path.remote = "dist"
                return

    def generate_dashboard_resource_hacstag(self) -> str:
        """Get the HACS tag used by dashboard resources."""
        version = (
            self.display_installed_version
            or self.data.selected_tag
            or self.display_available_version
        )
        return f"{self.data.id}{HACSTAG_REPLACER.sub('', version)}"

    def generate_dashboard_resource_namespace(self) -> str:
        """Get the dashboard resource namespace."""
        return f"/hacsfiles/{self.data.full_name.split('/')[1]}"

    def generate_dashboard_resource_url(self) -> str:
        """Get the dashboard resource namespace."""
        filename = self.data.file_name
        if "/" in filename:
            self.logger.warning("%s have defined an invalid file name %s", self.string, filename)
            filename = filename.split("/")[-1]
        return (
            f"{self.generate_dashboard_resource_namespace()}/{filename}"
            f"?hacstag={self.generate_dashboard_resource_hacstag()}"
        )

    def _get_resource_handler(self) -> ResourceStorageCollection | None:
        """Get the resource handler."""
        resources: ResourceStorageCollection | None
        if not (hass_data := self.hacs.hass.data):
            self.logger.error("%s Can not access the hass data", self.string)
            return

        if (lovelace_data := hass_data.get("lovelace")) is None:
            self.logger.warning("%s Can not access the lovelace integration data", self.string)
            return

        if self.hacs.core.ha_version > "2025.1.99":
            # Changed to 2025.2.0
            # Changed in https://github.com/home-assistant/core/pull/136313
            resources = lovelace_data.resources
        else:
            resources = lovelace_data.get("resources")

        if resources is None:
            self.logger.warning("%s Can not access the dashboard resources", self.string)
            return

        if not hasattr(resources, "store") or resources.store is None:
            self.logger.info("%s YAML mode detected, can not update resources", self.string)
            return

        if resources.store.key != "lovelace_resources" or resources.store.version != 1:
            self.logger.warning("%s Can not use the dashboard resources", self.string)
            return

        return resources

    async def update_dashboard_resources(self) -> None:
        """Update dashboard resources."""
        if not (resources := self._get_resource_handler()):
            return

        if not resources.loaded:
            await resources.async_load()

        # The trailing slash matters, without it the namespace of
        # for example 'button' would also match 'button-card'.
        namespace = f"{self.generate_dashboard_resource_namespace()}/"
        url = self.generate_dashboard_resource_url()

        for entry in resources.async_items():
            if (entry_url := entry["url"]).startswith(namespace):
                if entry_url != url:
                    self.logger.info(
                        "%s Updating existing dashboard resource from %s to %s",
                        self.string,
                        entry_url,
                        url,
                    )
                    await resources.async_update_item(entry["id"], {"url": url})
                return

        # Nothing was updated, add the resource
        self.logger.info("%s Adding dashboard resource %s", self.string, url)
        await resources.async_create_item({"res_type": "module", "url": url})

    async def remove_dashboard_resources(self) -> None:
        """Remove dashboard resources."""
        if not (resources := self._get_resource_handler()):
            return

        if not resources.loaded:
            await resources.async_load()

        # The trailing slash matters, without it the namespace of
        # for example 'button' would also match 'button-card'.
        namespace = f"{self.generate_dashboard_resource_namespace()}/"

        for entry in resources.async_items():
            if entry["url"].startswith(namespace):
                self.logger.info("%s Removing dashboard resource %s", self.string, entry["url"])
                await resources.async_delete_item(entry["id"])
                return

"""Class for dashboard resource repositories."""

from collections.abc import Awaitable, Callable
from functools import partial
import io
from pathlib import Path
from typing import TYPE_CHECKING, override
from urllib.parse import quote
import zipfile
import zlib

from homeassistant.components import lovelace
from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from ..const import (
    DASHBOARD_RESOURCE_BASE,
    DOMAIN,
    LEGACY_DASHBOARD_RESOURCE_BASE,
    MAX_DOWNLOAD_SIZE,
    RESTART_ISSUE_PREFIX,
)
from ..enums import RepositoryCategory
from ..exceptions import CatalogContentUnresolvedError, MarketplaceError
from ..utils.decorator import concurrent
from ..utils.file_system import async_run_to_completion
from ..utils.path import resolve_in_directory
from ..utils.tree import (
    tree_entry_directory,
    tree_entry_filename,
    tree_entry_is_directory,
)
from ..utils.url import github_release_asset, ref_version
from .base import FileInformation, Repository, _check_archive_size

if TYPE_CHECKING:
    from aiogithubapi.models.release import GitHubReleaseAssetModel

    from ..base import MarketplaceManager


def _archive_name(filename: str) -> str | None:
    """Return the name of the ZIP release asset a dashboard resource can ship as."""
    if not filename.endswith(".js"):
        return None
    return f"{filename.removesuffix('.js')}.zip"


class PluginRepository(Repository):
    """Dashboard resource repository."""

    ships_release_assets = True

    def __init__(self, marketplace: MarketplaceManager, full_name: str) -> None:
        """Initialize."""
        super().__init__(marketplace=marketplace)
        self.data.full_name = full_name
        self.data.file_name = ""
        self.data.category = RepositoryCategory.PLUGIN
        self.content.path.local = self.localpath

    @property
    @override
    def localpath(self) -> str:
        """Return localpath."""
        return f"{self.marketplace.core.config_path}/www/community/{self.directory}"

    @property
    def directory(self) -> str:
        """Return the folder of the card, the one it was installed to."""
        return self.data.directory or self.data.full_name.rsplit("/", maxsplit=1)[-1]

    @override
    def _category_directory(self) -> str | None:
        """Return the folder dashboard resources are installed to."""
        configuration = self.marketplace.configuration
        return f"{self.marketplace.core.config_path}/{configuration.plugin_path}"

    @override
    def _release_asset_names(self) -> tuple[str, ...]:
        """Return the names a release asset of the dashboard resource can have."""
        return (
            f"{self.data.name}.js",
            f"{self.data.name}-bundle.js",
            f"{self.data.name}.umd.js",
        )

    @override
    def _find_target_asset(
        self, assets: list[GitHubReleaseAssetModel] | None
    ) -> GitHubReleaseAssetModel | None:
        """Find the asset that is downloaded, the ZIP of the resource if there is one."""
        # Counted before the refresh resolves the file name, so taken from the assets
        names = {asset.name for asset in assets or []}
        if (filename := self._release_resource_filename(names)) and (
            archive_name := _archive_name(filename)
        ):
            for asset in assets or []:
                if asset.name == archive_name:
                    return asset
        return super()._find_target_asset(assets)

    @override
    async def _async_download_files(self, contents: list[FileInformation]) -> None:
        """Download the files, a ZIP of the resource instead of the release assets."""
        if (remaining := await self._async_try_resource_archive(contents)) is not None:
            await super()._async_download_files(remaining)

    async def _async_try_resource_archive(
        self, contents: list[FileInformation]
    ) -> list[FileInformation] | None:
        """Install the ZIP of the resource, return what is left to download if not."""
        archive_name = _archive_name(self.data.file_name or "")
        if self.content.path.remote != "release" or not archive_name:
            return contents

        for archive in contents:
            if archive.name != archive_name:
                continue
            remaining = [content for content in contents if content is not archive]
            try:
                await self._async_install_resource_archive(archive)
            except MarketplaceError as err:
                if not any(
                    content.name == self.data.file_name for content in remaining
                ):
                    raise
                self.logger.warning(
                    "%s %s is not usable, installing %s instead: %s",
                    self.string,
                    archive.name,
                    self.data.file_name,
                    err,
                )
                return remaining
            return None
        return contents

    async def _async_install_resource_archive(self, archive: FileInformation) -> None:
        """Download the ZIP of the resource and extract it."""
        if not (
            filecontent := await self.marketplace.async_download_file(
                archive.download_url, limit=MAX_DOWNLOAD_SIZE
            )
        ):
            raise MarketplaceError(
                translation_domain=DOMAIN,
                translation_key="file_not_downloaded",
                translation_placeholders={"file": archive.name},
            )
        await self._async_extract_resource_archive(archive.name, filecontent)

    async def _async_extract_resource_archive(
        self, name: str, filecontent: bytes
    ) -> None:
        """Extract the ZIP of the resource into the local path."""
        try:
            await async_run_to_completion(
                self.marketplace.hass,
                partial(self._extract_resource_archive, name, filecontent),
            )
        except zipfile.BadZipFile as err:
            raise MarketplaceError(
                translation_domain=DOMAIN,
                translation_key="resource_archive_unusable",
                translation_placeholders={"file": name},
            ) from err
        self.logger.info("%s Download of %s completed", self.string, name)

    def _extract_resource_archive(self, name: str, filecontent: bytes) -> None:
        """Extract the ZIP of the resource into the local path, this does I/O."""
        with zipfile.ZipFile(io.BytesIO(filecontent)) as archive:
            _check_archive_size(archive)
            if self.data.file_name not in archive.namelist():
                raise MarketplaceError(
                    translation_domain=DOMAIN,
                    translation_key="resource_archive_without_resource",
                    translation_placeholders={
                        "file": name,
                        "resource": self.data.file_name,
                    },
                )
            # Read first, a broken member must not leave half an extraction behind
            try:
                bad_member = archive.testzip()
            except (NotImplementedError, RuntimeError, zlib.error) as err:
                # Unsupported compression, encrypted members, damaged compressed data
                raise zipfile.BadZipFile(str(err)) from err
            if bad_member:
                raise zipfile.BadZipFile(f"Bad CRC-32 for {bad_member}")
            for member in archive.namelist():
                resolve_in_directory(self.content.path.local, member)
            archive.extractall(self.content.path.local)

    @override
    def gather_tree_files_to_download(self) -> list[FileInformation]:
        """Return the dashboard resource files, from the root or the dist folder."""
        if not self.content.single and (files := self._dashboard_resource_files()):
            return files

        return super().gather_tree_files_to_download()

    def _dashboard_resource_files(self) -> list[FileInformation]:
        """Return the files in the root or the dist folder that make the resource."""
        remote = self.content.path.remote
        files: list[FileInformation] = []
        for entry in self.tree:
            directory = tree_entry_directory(entry)
            filename = tree_entry_filename(entry)
            if directory not in ("", "dist") or tree_entry_is_directory(entry):
                continue
            if remote == "dist" and not filename.startswith("dist"):
                continue
            if not remote and (not filename.endswith(".js") or directory != ""):
                continue

            files.append(self._tree_file_information(entry))
        return files

    @override
    async def async_pre_install(self) -> None:
        """Run pre install steps."""
        # Refreshing only notes a missing resource, installing needs one
        self._check_resolved_content()

        # The directory leaves out the owner, so two owners can share a name
        for repository in self.marketplace.repositories.list_installed:
            if (
                repository is not self
                and repository.data.category == RepositoryCategory.PLUGIN
                and repository.localpath.lower() == self.localpath.lower()
            ):
                raise MarketplaceError(
                    translation_domain=DOMAIN,
                    translation_key="plugin_owned",
                    translation_placeholders={
                        "directory": self.localpath.rsplit("/", 1)[-1],
                        "owner": repository.data.full_name,
                    },
                )

    @override
    async def async_check_written_content(self) -> None:
        """Refuse an install without the dashboard resource it is used by."""
        if not self.data.file_name:
            return

        resource = Path(self.content.path.local, self.data.file_name)
        if not await self.marketplace.hass.async_add_executor_job(resource.is_file):
            raise MarketplaceError(
                translation_domain=DOMAIN,
                translation_key="installed_resource_missing",
                translation_placeholders={"file": self.data.file_name},
            )

    @override
    async def async_post_installation(self) -> None:
        """Run post installation steps."""
        self.data.directory = self.directory
        await self.update_dashboard_resources()

        # The frontend only registers /local when www/ existed at startup, so a
        # resource installed into a www/ this session created is served after
        # a restart, not before.
        if self.marketplace.status.created_www_directory:
            async_create_issue(
                hass=self.marketplace.hass,
                domain=DOMAIN,
                issue_id=f"{RESTART_ISSUE_PREFIX}{self.data.id}_{self.ref}",
                is_fixable=True,
                severity=IssueSeverity.WARNING,
                translation_key="restart_required",
                translation_placeholders={"name": self.display_name},
            )

    @override
    async def async_post_uninstall(self) -> None:
        """Run post uninstall steps."""
        await self.remove_dashboard_resources()
        # Installed again, the card goes to the folder of its current name
        self.data.directory = None

    @override
    @concurrent(concurrenttasks=10)
    async def update_repository(
        self, ignore_issues: bool = False, force: bool = False
    ) -> None:
        """Refresh the repository from GitHub."""
        if not await self.common_update(ignore_issues, force) and not force:
            return

        self.update_filenames()

        if self.content.path.remote is None:
            self.validate.errors.append(
                MarketplaceError(
                    translation_domain=DOMAIN,
                    translation_key="structure_not_compliant",
                    translation_placeholders={
                        "repository": self.data.full_name,
                        "version": str(ref_version(self.ref)),
                    },
                )
            )

        if self.content.path.remote == "release":
            self.content.single = True

        if self.data.installed:
            self.async_dispatch_changed("update")

    @override
    def try_resolve_content(self) -> bool:
        """Return if the tree holds a dashboard resource, which is a JavaScript module.

        The filename of hacs.json alone would also match the template it names.
        """
        return super().try_resolve_content() and self.data.file_name.endswith(".js")

    @override
    def resolve_content(self) -> None:
        """Point the content at the dashboard resource of the repository."""
        self.update_filenames()
        self._check_resolved_content()

    @override
    def resolve_archive_content(self) -> None:
        """Point the content at the dashboard resource in the archive."""
        # The release assets were probed already, the archive only has the tree
        self._update_filenames_from_tree()
        self._check_resolved_content()

    def _check_resolved_content(self) -> None:
        """Refuse a repository without a dashboard resource to serve."""
        if self.content.path.remote is None:
            raise MarketplaceError(
                translation_domain=DOMAIN,
                translation_key="structure_not_compliant",
                translation_placeholders={
                    "repository": self.data.full_name,
                    "version": str(ref_version(self.ref)),
                },
            )

        if self.content.path.remote == "release":
            self.content.single = True

    @override
    async def _async_resolve_catalog_content(
        self, version: str, *, commit: bool
    ) -> Callable[[], Awaitable[None]]:
        """Resolve the dashboard resource of a catalog version."""
        if not commit and not self.repository_manifest.content_in_root:
            # Without the prefix to strip, the first two names are the same
            filenames = dict.fromkeys(self._valid_filenames())
            for filename in filenames:
                if filecontent := await self._async_probe_release_asset(
                    version, filename
                ):
                    return await self._async_resolve_release_assets(
                        version, filename, filecontent
                    )
            for filename in filenames:
                if (archive_name := _archive_name(filename)) and (
                    filecontent := await self._async_probe_release_asset(
                        version, archive_name
                    )
                ):
                    self.data.file_name = filename
                    self.content.path.remote = "release"
                    self.content.single = True
                    return partial(
                        self._async_extract_resource_archive,
                        archive_name,
                        filecontent,
                    )

        return await super()._async_resolve_catalog_content(version, commit=commit)

    async def _async_probe_release_asset(
        self, version: str, filename: str
    ) -> bytes | None:
        """Download a release asset without the API, if the release has it."""
        return await self.marketplace.async_download_file(
            github_release_asset(
                repository=self.data.full_name, version=version, filename=filename
            ),
            nolog=True,
            limit=MAX_DOWNLOAD_SIZE,
        )

    async def _async_resolve_release_assets(
        self, version: str, filename: str, filecontent: bytes
    ) -> Callable[[], Awaitable[None]]:
        """Resolve a dashboard resource shipped as a release asset.

        Every asset of the release is downloaded, and only the API lists them.
        """
        if not (contents := await self.release_contents(version)):
            raise CatalogContentUnresolvedError(
                translation_domain=DOMAIN,
                translation_key="catalog_version_without_assets",
                translation_placeholders={"version": version},
            )

        self.data.file_name = filename
        self.content.path.remote = "release"
        self.content.single = True
        return partial(
            self._async_download_release_assets, contents, filename, filecontent
        )

    async def _async_download_release_assets(
        self, contents: list[FileInformation], filename: str, filecontent: bytes
    ) -> None:
        """Download the release assets, the resource itself came with the probe."""
        # Before the probe is written, its .gz would outlive the resource from the ZIP
        if (remaining := await self._async_try_resource_archive(contents)) is None:
            return

        other_assets: list[FileInformation] = []
        for content in remaining:
            if content.name == filename:
                await self._async_write_file(content, filecontent)
            else:
                other_assets.append(content)

        if other_assets:
            await self._async_download_files(other_assets)

    def _valid_filenames(self) -> tuple[str, ...]:
        """Return the file names the dashboard resource can have."""
        if specific_filename := self.repository_manifest.filename:
            return (specific_filename,)

        name = self.data.name or ""
        return (
            f"{name.replace('lovelace-', '')}.js",
            f"{name}.js",
            f"{name}.umd.js",
            f"{name}-bundle.js",
        )

    @override
    async def release_contents(
        self, version: str | None = None
    ) -> list[FileInformation] | None:
        """Gather the assets of a release, and take its file name from them.

        What a refresh found came from the newest release, an older one can
        name its file otherwise.
        """
        contents = await super().release_contents(version)
        if filename := self._release_resource_filename(
            {content.name for content in contents or []}
        ):
            self.data.file_name = filename
        return contents

    def _release_resource_filename(self, asset_names: set[str]) -> str | None:
        """Return the resource the release assets have, as a file or a ZIP."""
        for filename in self._valid_filenames():
            if filename in asset_names or _archive_name(filename) in asset_names:
                return filename
        return None

    @override
    def update_filenames(self) -> None:
        """Get the filename to target."""
        if not self._update_filenames_from_release():
            self._update_filenames_from_tree()

    def _update_filenames_from_release(self) -> bool:
        """Target an asset of the latest release, return if there is one."""
        if self.repository_manifest.content_in_root or not self.releases.objects:
            return False

        release = self.releases.objects[0]
        if filename := self._release_resource_filename(
            {asset.name for asset in release.assets or []}
        ):
            self.data.file_name = filename
            self.content.path.remote = "release"
            return True

        return False

    def _update_filenames_from_tree(self) -> None:
        """Target a file in the root or the dist directory of the tree."""
        content_in_root = self.repository_manifest.content_in_root
        all_paths = {entry.path for entry in self.tree}
        for filename in self._valid_filenames():
            if filename in all_paths:
                self.data.file_name = filename
                self.content.path.remote = ""
                return
            if not content_in_root and f"dist/{filename}" in all_paths:
                self.data.file_name = filename.rsplit("/", maxsplit=1)[-1]
                self.content.path.remote = "dist"
                return

    def generate_dashboard_resource_tag(self) -> str:
        """Get the cache busting tag used by dashboard resources."""
        version = (
            self.display_installed_version
            or self.data.selected_tag
            or self.display_available_version
        )
        # Encoded whole, digits alone make 1.2.3 and 12.3 or a beta and an rc
        # share the address browsers cache the card under
        return f"{self.data.id}-{quote(version, safe='')}"

    def generate_dashboard_resource_namespace(self) -> str:
        """Get the dashboard resource namespace."""
        return f"{DASHBOARD_RESOURCE_BASE}/{self.directory}"

    def _loaded_as_extra_module(self) -> bool:
        """Return if the frontend configuration loads this plugin already.

        Some plugins, like icon sets, are meant for `frontend: extra_module_url`,
        a dashboard resource next to that would load them twice.
        """
        if (
            extra_modules := self.marketplace.hass.data.get(DATA_EXTRA_MODULE_URL)
        ) is None:
            return False

        namespaces = (
            f"{DASHBOARD_RESOURCE_BASE}/{self.directory}/",
            f"{LEGACY_DASHBOARD_RESOURCE_BASE}/{self.directory}/",
        )
        return any(url.startswith(namespaces) for url in extra_modules.urls)

    def generate_dashboard_resource_url(self) -> str:
        """Get the dashboard resource URL."""
        filename = self.data.file_name
        if "/" in filename:
            self.logger.warning(
                "%s have defined an invalid file name %s", self.string, filename
            )
            filename = filename.split("/")[-1]
        # Quoted, a character like # would cut the rest of the name off the path
        return (
            f"{self.generate_dashboard_resource_namespace()}/{quote(filename)}"
            f"?v={self.generate_dashboard_resource_tag()}"
        )

    def _get_resource_handler(
        self,
    ) -> lovelace.resources.ResourceStorageCollection | None:
        """Get the resource handler."""
        if (
            lovelace_data := self.marketplace.hass.data.get(lovelace.LOVELACE_DATA)
        ) is None:
            self.logger.warning(
                "%s Can not access the lovelace integration data", self.string
            )
            return None

        resources = lovelace_data.resources

        # Only the storage resource mode has a store to update
        if (
            not isinstance(resources, lovelace.resources.ResourceStorageCollection)
            or resources.store is None
        ):
            self.logger.info(
                "%s YAML mode detected, can not update resources", self.string
            )
            return None

        if resources.store.key != "lovelace_resources" or resources.store.version != 1:
            self.logger.warning("%s Can not use the dashboard resources", self.string)
            return None

        return resources

    async def update_dashboard_resources(self) -> None:
        """Update dashboard resources."""
        if self._loaded_as_extra_module():
            self.logger.debug(
                "%s Loaded through extra_module_url, no dashboard resource needed",
                self.string,
            )
            return

        if not (resources := self._get_resource_handler()):
            return

        if not resources.loaded:
            await resources.async_load()
            resources.loaded = True

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
            resources.loaded = True

        # The trailing slash matters, without it the namespace of
        # for example 'button' would also match 'button-card'.
        namespace = f"{self.generate_dashboard_resource_namespace()}/"

        # A copy, deleting changes the items
        for entry in list(resources.async_items()):
            if entry["url"].startswith(namespace):
                self.logger.info(
                    "%s Removing dashboard resource %s", self.string, entry["url"]
                )
                await resources.async_delete_item(entry["id"])

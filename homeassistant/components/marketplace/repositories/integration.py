"""Class for integration repositories."""

from collections.abc import Awaitable, Callable
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any, override

from homeassistant import components
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.loader import (
    async_clear_custom_components_cache,
    async_get_custom_components,
)

from ..const import DOMAIN
from ..enums import MarketplaceSignal, RepositoryCategory, RepositoryFile
from ..exceptions import (
    AppRepositoryError,
    CatalogContentUnresolvedError,
    MarketplaceError,
)
from ..utils.decode import decode_content
from ..utils.decorator import concurrent
from ..utils.filters import get_first_directory_in_directory
from ..utils.json import json_loads_object
from ..utils.logger import LOGGER
from ..utils.url import github_raw_file, ref_version
from ..utils.validate import VALID_DOMAIN
from .base import Repository

if TYPE_CHECKING:
    from ..base import MarketplaceManager


def _validated_domain(domain: Any) -> str:
    """Return the domain of a remote manifest, rejecting anything but a slug.

    The domain names the directory below custom_components/ the download is
    written to, so anything else would let a repository pick its own target.
    """
    if not isinstance(domain, str) or not VALID_DOMAIN.match(domain):
        raise MarketplaceError(f"'{domain}' is not a valid integration domain")

    return domain


class IntegrationRepository(Repository):
    """Integration repository."""

    remote_path = "custom_components"

    def __init__(self, marketplace: MarketplaceManager, full_name: str) -> None:
        """Initialize."""
        super().__init__(marketplace=marketplace)
        self.data.full_name = full_name
        self.data.category = RepositoryCategory.INTEGRATION
        self.content.path.local = self.localpath

    @property
    @override
    def localpath(self) -> str:
        """Return localpath."""
        return (
            f"{self.marketplace.core.config_path}/custom_components/{self.data.domain}"
        )

    @override
    async def async_pre_install(self) -> None:
        """Run pre install steps."""
        if not self.data.domain:
            return

        for repository in self.marketplace.repositories.list_downloaded:
            if (
                repository is not self
                and repository.data.category == RepositoryCategory.INTEGRATION
                and repository.data.domain == self.data.domain
            ):
                raise MarketplaceError(
                    f"The '{self.data.domain}' directory is owned by "
                    f"{repository.data.full_name}"
                )

    @override
    async def async_post_installation(self) -> None:
        """Run post installation steps."""
        self.pending_restart = True
        if self.data.config_flow:
            await self.reload_custom_components()
            if self.data.first_install:
                self.pending_restart = False

        if self.pending_restart:
            self.logger.debug("%s Creating restart_required issue", self.string)
            async_create_issue(
                hass=self.marketplace.hass,
                domain=DOMAIN,
                issue_id=f"restart_required_{self.data.id}_{self.ref}",
                is_fixable=True,
                issue_domain=self.data.domain or DOMAIN,
                severity=IssueSeverity.WARNING,
                translation_key="restart_required",
                translation_placeholders={
                    "name": self.display_name,
                },
            )

    @override
    async def async_replaces_built_in(self) -> bool:
        """Return if the domain belongs to an integration of Home Assistant."""
        if not self.data.domain:
            return False

        # The same check the loader makes before loading a custom integration
        manifest = Path(components.__file__).parent / self.data.domain / "manifest.json"
        return await self.marketplace.hass.async_add_executor_job(manifest.is_file)

    @override
    async def async_post_uninstall(self) -> None:
        """Run post uninstall steps."""
        if self.data.config_flow:
            await self.reload_custom_components()
        else:
            self.pending_restart = True

    @override
    async def validate_repository(self) -> bool:
        """Validate."""
        await self.common_validate()

        # Custom step 1: Validate content.
        self.resolve_content()

        # Get the content of manifest.json
        if manifest := await self.async_get_integration_manifest():
            self._use_integration_manifest(manifest)

        # Set local path
        self.content.path.local = self.localpath

        # Handle potential errors
        if self.validate.errors:
            for error in self.validate.errors:
                if not self.marketplace.status.startup:
                    self.logger.error("%s %s", self.string, error)
        return self.validate.success

    @override
    @concurrent(concurrenttasks=10)
    async def update_repository(
        self, ignore_issues: bool = False, force: bool = False
    ) -> None:
        """Update."""
        if not await self.common_update(ignore_issues, force) and not force:
            return

        if self.repository_manifest.content_in_root:
            self.content.path.remote = ""

        if self.content.path.remote == "custom_components":
            name = get_first_directory_in_directory(self.tree, "custom_components")
            self.content.path.remote = f"custom_components/{name}"

        # Get the content of manifest.json
        if manifest := await self.async_get_integration_manifest():
            self._use_integration_manifest(manifest)

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

    @override
    def resolve_content(self) -> None:
        """Point the content at the integration directory in the tree."""
        if self.repository_manifest.content_in_root:
            self.content.path.remote = ""

        if self.content.path.remote == "custom_components":
            name = get_first_directory_in_directory(self.tree, "custom_components")
            if name is None:
                if (
                    "repository.json" in self.treefiles
                    or "repository.yaml" in self.treefiles
                    or "repository.yml" in self.treefiles
                ):
                    raise AppRepositoryError
                raise MarketplaceError(
                    f"{self.string} Repository structure for {ref_version(self.ref)} is not compliant"
                )
            self.content.path.remote = f"custom_components/{name}"

    def _use_integration_manifest(self, manifest: dict[str, Any]) -> None:
        """Take the details of the integration from its manifest.json."""
        try:
            domain = _validated_domain(manifest["domain"])
            # The files of a download stay where they are, removal needs to find them
            if self.data.installed and self.data.domain not in (None, domain):
                raise MarketplaceError(
                    f"{self.data.full_name} changed its domain from "
                    f"'{self.data.domain}' to '{domain}', remove it and download "
                    "it again"
                )

            self.integration_manifest = manifest
            self.data.authors = manifest.get("codeowners", [])
            self.data.domain = domain
            self.data.manifest_name = manifest.get("name")
            self.data.config_flow = manifest.get("config_flow", False)

        except KeyError as exception:
            self.validate.errors.append(
                f"Missing expected key '{exception}' in {RepositoryFile.MAINIFEST_JSON}"
            )
            LOGGER.error(
                "Missing expected key '%s' in '%s'",
                exception,
                RepositoryFile.MAINIFEST_JSON,
            )

    @override
    async def _async_resolve_catalog_content(
        self, version: str, *, commit: bool
    ) -> Callable[[], Awaitable[None]]:
        """Resolve the content of a catalog version, and read its manifest.json."""
        download: Callable[[], Awaitable[None]]
        if self.repository_manifest.zip_release and self.repository_manifest.filename:
            # Without the tree, the catalog domain names the directory
            if self.data.domain is None:
                raise CatalogContentUnresolvedError("The catalog names no domain")
            if self.repository_manifest.content_in_root:
                self.content.path.remote = ""
            else:
                self.content.path.remote = f"custom_components/{self.data.domain}"
            download = partial(self.download_zip_files, self.validate)
        else:
            download = await super()._async_resolve_catalog_content(
                version, commit=commit
            )

        manifest_path = self._integration_manifest_path()
        manifest = await self._async_download_integration_manifest(
            version, manifest_path
        )
        if manifest is None or "domain" not in manifest:
            raise CatalogContentUnresolvedError(f"No usable {manifest_path}")

        self._use_integration_manifest(manifest)
        self.content.path.local = self.localpath
        return download

    async def reload_custom_components(self) -> None:
        """Reload custom_components (and config flows)in HA."""
        self.logger.info("Reloading custom_component cache")
        async_clear_custom_components_cache(self.marketplace.hass)
        await async_get_custom_components(self.marketplace.hass)
        self.logger.info("Custom_component cache reloaded")

    def _integration_manifest_path(self) -> str:
        """Return the path of the manifest.json in the repository."""
        if self.repository_manifest.content_in_root:
            return RepositoryFile.MAINIFEST_JSON
        return f"{self.content.path.remote}/{RepositoryFile.MAINIFEST_JSON}"

    async def async_get_integration_manifest(
        self, ref: str | None = None
    ) -> dict[str, Any] | None:
        """Get the content of the manifest.json file."""
        manifest_path = self._integration_manifest_path()

        if manifest_path not in (entry.path for entry in self.tree):
            raise MarketplaceError(
                f"No {RepositoryFile.MAINIFEST_JSON} file found '{manifest_path}'"
            )

        target_ref = ref or self.version_to_download()
        self.logger.debug(
            "%s Getting %s for ref=%s", self.string, manifest_path, target_ref
        )

        response = await self.marketplace.async_github_api_method(
            method=self.marketplace.githubapi.repos.contents.get,
            repository=self.data.full_name,
            path=manifest_path,
            params={"ref": target_ref},
        )
        if response:
            return json_loads_object(decode_content(response.data.content))
        return None

    async def get_integration_manifest(
        self, *, version: str | None, **kwargs: Any
    ) -> dict[str, Any] | None:
        """Get the content of the manifest.json file."""
        manifest_path = self._integration_manifest_path()

        if manifest_path not in (entry.path for entry in self.tree):
            raise MarketplaceError(
                f"No {RepositoryFile.MAINIFEST_JSON} file found '{manifest_path}'"
            )

        return await self._async_download_integration_manifest(version, manifest_path)

    async def _async_download_integration_manifest(
        self, version: str | None, manifest_path: str
    ) -> dict[str, Any] | None:
        """Download the manifest.json of a version, None when it is not there."""
        self.logger.debug(
            "%s Getting manifest.json for version=%s", self.string, version
        )
        try:
            result = await self.marketplace.async_download_file(
                github_raw_file(
                    repository=self.data.full_name, ref=version, path=manifest_path
                ),
                nolog=True,
            )
            if result is None:
                return None
            return json_loads_object(result)
        except ValueError:
            return None

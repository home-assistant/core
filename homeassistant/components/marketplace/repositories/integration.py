"""Class for integration repositories."""

from collections.abc import Awaitable, Callable
from functools import partial
from pathlib import Path
import sys
from typing import TYPE_CHECKING, Any, override

from awesomeversion import AwesomeVersion, AwesomeVersionStrategy
from awesomeversion.exceptions import AwesomeVersionException
import probatio

from homeassistant import components
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.loader import (
    PACKAGE_CUSTOM_COMPONENTS,
    IntegrationNotLoaded,
    async_clear_custom_components_cache,
    async_get_custom_components,
    async_get_loaded_integration,
    async_mount_config_dir,
)
from homeassistant.util.json import json_loads_object

from ..const import DOMAIN, RESTART_ISSUE_PREFIX
from ..enums import RepositoryCategory, RepositoryFile
from ..exceptions import (
    AppRepositoryError,
    CatalogContentUnresolvedError,
    MarketplaceError,
)
from ..utils.decode import decode_content
from ..utils.decorator import concurrent
from ..utils.filters import get_first_directory_in_directory
from ..utils.logger import LOGGER
from ..utils.url import github_raw_file, ref_version
from ..utils.validate import INTEGRATION_MANIFEST_VALUES, VALID_DOMAIN
from .base import Repository

if TYPE_CHECKING:
    from ..base import MarketplaceManager


def _validated_domain(domain: Any) -> str:
    """Return the domain of a remote manifest, rejecting anything but a slug.

    The domain names the directory below custom_components/ the install is
    written to, so anything else would let a repository pick its own target.
    """
    if not isinstance(domain, str) or not VALID_DOMAIN.match(domain):
        raise MarketplaceError(
            translation_domain=DOMAIN,
            translation_key="invalid_domain",
            translation_placeholders={"domain": str(domain)},
        )

    return domain


def _manifest_value(manifest: dict[str, Any], key: str, default: Any) -> Any:
    """Return a value of manifest.json, the default when it has the wrong type."""
    if key not in manifest:
        return default

    try:
        return INTEGRATION_MANIFEST_VALUES[key](manifest[key])
    except probatio.Invalid:
        LOGGER.warning(
            "Ignoring %s in manifest.json, %r is not valid", key, manifest[key]
        )
        return default


# The version formats the loader accepts for a custom integration
LOADABLE_VERSION_STRATEGIES = [
    AwesomeVersionStrategy.CALVER,
    AwesomeVersionStrategy.SEMVER,
    AwesomeVersionStrategy.SIMPLEVER,
    AwesomeVersionStrategy.BUILDVER,
    AwesomeVersionStrategy.PEP440,
]


def _is_loadable_version(version: Any) -> bool:
    """Return if the loader accepts this as the version of a custom integration."""
    if not isinstance(version, str):
        return False

    try:
        AwesomeVersion(version, ensure_strategy=LOADABLE_VERSION_STRATEGIES)
    except AwesomeVersionException:
        return False
    return True


def _check_loadable_manifest(directory: Path, domain: str | None) -> None:
    """Refuse an installed manifest.json the loader would not load."""
    try:
        manifest = json_loads_object(
            (directory / RepositoryFile.MANIFEST_JSON).read_text(encoding="utf-8")
        )
    except (OSError, ValueError) as exception:
        raise MarketplaceError(
            translation_domain=DOMAIN,
            translation_key="installed_manifest_unusable",
            translation_placeholders={"error": str(exception)},
        ) from exception

    if manifest.get("domain") != domain:
        raise MarketplaceError(
            translation_domain=DOMAIN,
            translation_key="installed_manifest_other_domain",
            translation_placeholders={
                "found": str(manifest.get("domain")),
                "domain": str(domain),
            },
        )

    if not _is_loadable_version(manifest.get("version")):
        raise MarketplaceError(
            translation_domain=DOMAIN,
            translation_key="installed_manifest_without_version",
        )


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
    def _content_name(self) -> str | None:
        """Return the name in the manifest.json of the integration."""
        if self.data.manifest_name is not None:
            return self.data.manifest_name
        if "name" in self.integration_manifest:
            return str(self.integration_manifest["name"])
        return None

    @override
    def _category_directory(self) -> str | None:
        """Return the custom_components folder."""
        return f"{self.marketplace.core.config_path}/custom_components"

    @override
    async def remove_local_directory(self) -> bool:
        """Remove the integration, its folder is named by its domain."""
        if not self.data.domain:
            self.logger.error("%s Missing domain", self.string)
            return False

        return await super().remove_local_directory()

    @override
    async def async_pre_install(self) -> None:
        """Run pre install steps."""
        if not self.data.domain:
            return

        for repository in self.marketplace.repositories.list_installed:
            if (
                repository is not self
                and repository.data.category == RepositoryCategory.INTEGRATION
                and repository.data.domain == self.data.domain
            ):
                raise MarketplaceError(
                    translation_domain=DOMAIN,
                    translation_key="integration_owned",
                    translation_placeholders={
                        "domain": str(self.data.domain),
                        "owner": repository.data.full_name,
                    },
                )

    @override
    async def async_post_installation(self) -> None:
        """Run post installation steps."""
        self.pending_restart = True
        if self.data.config_flow:
            found = await self.reload_custom_components()
            # Code new to this run is found like any other integration, code
            # the loader already knows keeps running until a restart.
            self.pending_restart = (
                self._known_to_the_loader() or self.data.domain not in found
            )

        if self.pending_restart:
            self.logger.debug("%s Creating restart_required issue", self.string)
            async_create_issue(
                hass=self.marketplace.hass,
                domain=DOMAIN,
                issue_id=f"{RESTART_ISSUE_PREFIX}{self.data.id}_{self.ref}",
                is_fixable=True,
                issue_domain=self.data.domain or DOMAIN,
                severity=IssueSeverity.WARNING,
                translation_key="restart_required",
                translation_placeholders={
                    "name": self.display_name,
                },
            )

    def _known_to_the_loader(self) -> bool:
        """Return if this run already resolved the domain, its own or a built-in."""
        try:
            async_get_loaded_integration(self.marketplace.hass, str(self.data.domain))
        except IntegrationNotLoaded:
            return False
        return True

    @override
    async def async_check_written_content(self) -> None:
        """Refuse an integration the loader would not load."""
        await self.marketplace.hass.async_add_executor_job(
            _check_loadable_manifest, Path(self.content.path.local), self.data.domain
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
        # Code this run loaded keeps running until a restart, and so does
        # an integration only set up from YAML
        loaded = self._known_to_the_loader()
        if self.data.config_flow:
            await self.reload_custom_components()
        self.pending_restart = loaded or not self.data.config_flow

        if self.pending_restart:
            async_create_issue(
                hass=self.marketplace.hass,
                domain=DOMAIN,
                issue_id=f"{RESTART_ISSUE_PREFIX}{self.data.id}_uninstall",
                is_fixable=True,
                issue_domain=self.data.domain or DOMAIN,
                severity=IssueSeverity.WARNING,
                translation_key="restart_required_uninstall",
                translation_placeholders={"name": self.display_name},
            )

    @override
    async def async_read_content_details(self) -> None:
        """Take the domain and the name from the manifest.json of the integration."""
        if manifest := await self.async_get_integration_manifest():
            self._use_integration_manifest(manifest)

        self.content.path.local = self.localpath

    @override
    @concurrent(concurrenttasks=10)
    async def update_repository(
        self, ignore_issues: bool = False, force: bool = False
    ) -> None:
        """Refresh the repository from GitHub."""
        if not await self.common_update(ignore_issues, force) and not force:
            return

        # Resolved again for every version, the last one may have had it elsewhere
        self.content.path.remote = self.remote_path
        if self.repository_manifest.content_in_root:
            self.content.path.remote = ""

        if self.content.path.remote == "custom_components":
            name = get_first_directory_in_directory(self.tree, "custom_components")
            self.content.path.remote = f"custom_components/{name}"

        await self.async_read_content_details()

        if self.data.installed:
            self.async_dispatch_changed("update")

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
                    raise AppRepositoryError(self.data.full_name)
                raise MarketplaceError(
                    translation_domain=DOMAIN,
                    translation_key="structure_not_compliant",
                    translation_placeholders={
                        "repository": self.data.full_name,
                        "version": str(ref_version(self.ref)),
                    },
                )
            self.content.path.remote = f"custom_components/{name}"

    def _use_integration_manifest(self, manifest: dict[str, Any]) -> None:
        """Take the details of the integration from its manifest.json."""
        try:
            domain = _validated_domain(manifest["domain"])
            # The files of an install stay where they are, removal needs to find them
            if self.data.installed and self.data.domain not in (None, domain):
                raise MarketplaceError(
                    translation_domain=DOMAIN,
                    translation_key="domain_changed",
                    translation_placeholders={
                        "repository": self.data.full_name,
                        "old_domain": self.data.domain,
                        "domain": domain,
                    },
                )

            self.integration_manifest = manifest
            self.data.authors = _manifest_value(manifest, "codeowners", [])
            self.data.domain = domain
            self.data.manifest_name = _manifest_value(manifest, "name", None)
            self.data.config_flow = _manifest_value(manifest, "config_flow", False)

        except KeyError as exception:
            self.validate.errors.append(
                MarketplaceError(
                    translation_domain=DOMAIN,
                    translation_key="integration_manifest_key_missing",
                    translation_placeholders={"key": str(exception)},
                )
            )
            LOGGER.error(
                "Missing expected key '%s' in '%s'",
                exception,
                RepositoryFile.MANIFEST_JSON,
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

    async def reload_custom_components(self) -> set[str]:
        """Scan custom_components again, return the domains the loader found."""
        self.logger.info("Reloading custom_component cache")
        # The loader mounts custom_components at startup, a first install
        # creates the folder after that
        if PACKAGE_CUSTOM_COMPONENTS not in sys.modules:
            async_mount_config_dir(self.marketplace.hass)
        async_clear_custom_components_cache(self.marketplace.hass)
        found = await async_get_custom_components(self.marketplace.hass)
        self.logger.info("Custom_component cache reloaded")
        return set(found)

    def _integration_manifest_path(self) -> str:
        """Return the path of the manifest.json in the repository."""
        if self.repository_manifest.content_in_root:
            return RepositoryFile.MANIFEST_JSON
        return f"{self.content.path.remote}/{RepositoryFile.MANIFEST_JSON}"

    async def async_get_integration_manifest(self) -> dict[str, Any] | None:
        """Get manifest.json through the GitHub API."""
        manifest_path = self._integration_manifest_path()

        if manifest_path not in (entry.path for entry in self.tree):
            raise MarketplaceError(
                translation_domain=DOMAIN,
                translation_key="integration_manifest_missing",
                translation_placeholders={"path": manifest_path},
            )

        target_ref = self.version_to_install()
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

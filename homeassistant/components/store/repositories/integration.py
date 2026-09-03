"""Class for integrations in HACS."""

import re
from typing import TYPE_CHECKING, Any, override

from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.loader import (
    async_clear_custom_components_cache,
    async_get_custom_components,
)

from ..const import DOMAIN
from ..enums import RepositoryCategory, RepositoryFile, StoreSignal
from ..exceptions import AppRepositoryError, StoreError
from ..utils.decode import decode_content
from ..utils.decorator import concurrent
from ..utils.filters import get_first_directory_in_directory
from ..utils.json import json_loads_object
from .base import HacsRepository

if TYPE_CHECKING:
    from ..base import HacsBase

VALID_DOMAIN = re.compile(r"^[a-z0-9_]+$")


def _validated_domain(domain: Any) -> str:
    """Return the domain of a remote manifest, rejecting anything but a slug.

    The domain names the directory below custom_components/ the download is
    written to, so anything else would let a repository pick its own target.
    """
    if not isinstance(domain, str) or not VALID_DOMAIN.match(domain):
        raise StoreError(f"'{domain}' is not a valid integration domain")

    return domain


class HacsIntegrationRepository(HacsRepository):
    """Integrations in HACS."""

    def __init__(self, hacs: HacsBase, full_name: str) -> None:
        """Initialize."""
        super().__init__(hacs=hacs)
        self.data.full_name = full_name
        self.data.full_name_lower = full_name.lower()
        self.data.category = RepositoryCategory.INTEGRATION
        self.content.path.remote = "custom_components"
        self.content.path.local = self.localpath

    @property
    @override
    def localpath(self) -> str:
        """Return localpath."""
        return f"{self.hacs.core.config_path}/custom_components/{self.data.domain}"

    @override
    async def async_pre_install(self) -> None:
        """Run pre install steps."""
        if not self.data.domain:
            return

        for repository in self.hacs.repositories.list_downloaded:
            if (
                repository is not self
                and repository.data.category == RepositoryCategory.INTEGRATION
                and repository.data.domain == self.data.domain
            ):
                raise StoreError(
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
                hass=self.hacs.hass,
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
                raise StoreError(
                    f"{self.string} Repository structure for {f'{self.ref}'.replace('tags/', '')} is not compliant"
                )
            self.content.path.remote = f"custom_components/{name}"

        # Get the content of manifest.json
        if manifest := await self.async_get_integration_manifest():
            try:
                self.integration_manifest = manifest
                self.data.authors = manifest.get("codeowners", [])
                self.data.domain = _validated_domain(manifest["domain"])
                self.data.manifest_name = manifest.get("name")
                self.data.config_flow = manifest.get("config_flow", False)

            except KeyError as exception:
                self.validate.errors.append(
                    f"Missing expected key '{exception}' in {RepositoryFile.MAINIFEST_JSON}"
                )
                self.hacs.log.error(
                    "Missing expected key '%s' in '%s'",
                    exception,
                    RepositoryFile.MAINIFEST_JSON,
                )

        # Set local path
        self.content.path.local = self.localpath

        # Handle potential errors
        if self.validate.errors:
            for error in self.validate.errors:
                if not self.hacs.status.startup:
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

        if self.repository_manifest.content_in_root:
            self.content.path.remote = ""

        if self.content.path.remote == "custom_components":
            name = get_first_directory_in_directory(self.tree, "custom_components")
            self.content.path.remote = f"custom_components/{name}"

        # Get the content of manifest.json
        if manifest := await self.async_get_integration_manifest():
            try:
                self.integration_manifest = manifest
                self.data.authors = manifest.get("codeowners", [])
                self.data.domain = _validated_domain(manifest["domain"])
                self.data.manifest_name = manifest.get("name")
                self.data.config_flow = manifest.get("config_flow", False)

            except KeyError as exception:
                self.validate.errors.append(
                    f"Missing expected key '{exception}' in {RepositoryFile.MAINIFEST_JSON}"
                )
                self.hacs.log.error(
                    "Missing expected key '%s' in '%s'",
                    exception,
                    RepositoryFile.MAINIFEST_JSON,
                )

        # Set local path
        self.content.path.local = self.localpath

        # Signal frontend to refresh
        if self.data.installed:
            self.hacs.async_dispatch(
                StoreSignal.REPOSITORY,
                {
                    "id": 1337,
                    "action": "update",
                    "repository": self.data.full_name,
                    "repository_id": self.data.id,
                },
            )

    async def reload_custom_components(self) -> None:
        """Reload custom_components (and config flows)in HA."""
        self.logger.info("Reloading custom_component cache")
        async_clear_custom_components_cache(self.hacs.hass)
        await async_get_custom_components(self.hacs.hass)
        self.logger.info("Custom_component cache reloaded")

    async def async_get_integration_manifest(
        self, ref: str | None = None
    ) -> dict[str, Any] | None:
        """Get the content of the manifest.json file."""
        manifest_path = (
            "manifest.json"
            if self.repository_manifest.content_in_root
            else f"{self.content.path.remote}/{RepositoryFile.MAINIFEST_JSON}"
        )

        if manifest_path not in (x.full_path for x in self.tree):
            raise StoreError(
                f"No {RepositoryFile.MAINIFEST_JSON} file found '{manifest_path}'"
            )

        target_ref = ref or self.version_to_download()
        self.logger.debug(
            "%s Getting %s for ref=%s", self.string, manifest_path, target_ref
        )

        response = await self.hacs.async_github_api_method(
            method=self.hacs.githubapi.repos.contents.get,
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
        manifest_path = (
            "manifest.json"
            if self.repository_manifest.content_in_root
            else f"{self.content.path.remote}/{RepositoryFile.MAINIFEST_JSON}"
        )

        if manifest_path not in (x.full_path for x in self.tree):
            raise StoreError(
                f"No {RepositoryFile.MAINIFEST_JSON} file found '{manifest_path}'"
            )

        self.logger.debug(
            "%s Getting manifest.json for version=%s", self.string, version
        )
        try:
            result = await self.hacs.async_download_file(
                f"https://raw.githubusercontent.com/{self.data.full_name}/{version}/{manifest_path}",
                nolog=True,
            )
            if result is None:
                return None
            return json_loads_object(result)
        except ValueError:
            return None

"""Class for template repositories."""

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, override

from homeassistant.exceptions import HomeAssistantError

from ..enums import MarketplaceSignal, RepositoryCategory
from ..exceptions import MarketplaceError
from ..utils.decorator import concurrent
from ..utils.file_system import async_remove
from ..utils.path import resolve_in_directory
from ..utils.url import ref_version
from .base import FileInformation, Repository

if TYPE_CHECKING:
    from ..base import MarketplaceManager


class TemplateRepository(Repository):
    """Template repository.

    The file name of the data is the installed file, removal deletes that one.
    The file a version names comes from its hacs.json, and only replaces the
    installed one when that version is written.
    """

    remote_path = ""
    single_file = True

    def __init__(self, marketplace: MarketplaceManager, full_name: str) -> None:
        """Initialize."""
        super().__init__(marketplace=marketplace)
        self.data.full_name = full_name
        self.data.category = RepositoryCategory.TEMPLATE
        self.content.path.local = self.localpath

    @property
    @override
    def localpath(self) -> str:
        """Return localpath."""
        return f"{self.marketplace.core.config_path}/custom_templates"

    @property
    def _file_name_to_write(self) -> str:
        """Return the template file the version being handled names."""
        return self.repository_manifest.filename or self.data.file_name

    def _use_file_name(self) -> None:
        """Take the file name of the version, unless another one is installed."""
        if not self.data.installed:
            self.data.file_name = self._file_name_to_write

    def _check_file_name(self, file_name: str) -> None:
        """Refuse a file name that is not a template in the root of the folder."""
        if not file_name or "/" in file_name or not file_name.endswith(".jinja"):
            raise MarketplaceError(
                f"{self.string} Repository structure for {ref_version(self.ref)} is not compliant"
            )

    @override
    async def async_pre_install(self) -> None:
        """Run pre install steps."""
        # hacs.json of the version being written names it, not the one validated
        self._check_file_name(self._file_name_to_write)

        # The folder is shared, a template file belongs to one repository
        for repository in self.marketplace.repositories.list_installed:
            if (
                repository is not self
                and repository.data.category == RepositoryCategory.TEMPLATE
                and repository.data.file_name == self._file_name_to_write
            ):
                raise MarketplaceError(
                    f"The '{self._file_name_to_write}' template is owned by"
                    f" {repository.data.full_name}"
                )

    @override
    def _backup_path(self) -> str | None:
        """Return the template file, the folder is shared with other templates."""
        if not self._file_name_to_write:
            return None
        return f"{self.localpath}/{self._file_name_to_write}"

    @override
    def _installs_a_directory(self) -> bool:
        """Return False, a template is always the one file hacs.json names."""
        return False

    @override
    def gather_tree_files_to_download(self) -> list[FileInformation]:
        """Return the template file, the one in the root that validation found."""
        return [
            self._tree_file_information(entry)
            for entry in self.tree
            if entry.path == self._file_name_to_write
        ]

    @override
    async def _async_write_content(
        self, download: Callable[[], Awaitable[None]]
    ) -> None:
        """Write the template, and remove the one it replaces under another name."""
        installed = self.data.file_name if self.data.installed else None
        await super()._async_write_content(download)

        self.data.file_name = self._file_name_to_write
        if installed and installed != self.data.file_name:
            await async_remove(
                self.marketplace.hass,
                str(resolve_in_directory(self.localpath, installed)),
                missing_ok=True,
            )

    @override
    async def async_check_written_content(self) -> None:
        """Refuse a template Home Assistant can not read.

        Home Assistant reads every template at startup, one it can not decode
        stops it from starting.
        """

        def _check() -> None:
            path = resolve_in_directory(self.localpath, self._file_name_to_write)
            try:
                path.read_bytes().decode("utf-8")
            except UnicodeDecodeError as exception:
                raise MarketplaceError(
                    f"{path.name} is not UTF-8 encoded: {exception}"
                ) from exception

        await self.marketplace.hass.async_add_executor_job(_check)

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
        self.resolve_content()

        # Handle potential errors
        if self.validate.errors:
            for error in self.validate.errors:
                if not self.marketplace.status.startup:
                    self.logger.error("%s %s", self.string, error)
        return self.validate.success

    @override
    def resolve_content(self) -> None:
        """Point the content at the template hacs.json names."""
        file_name = self.repository_manifest.filename or ""
        self._check_file_name(file_name)
        if file_name not in self.treefiles:
            raise MarketplaceError(
                f"{self.string} Repository structure for {ref_version(self.ref)} is not compliant"
            )
        self._use_file_name()

    @override
    async def async_post_registration(self) -> None:
        """Registration."""
        self._use_file_name()
        self.content.path.local = self.localpath

    @override
    async def async_post_uninstall(self) -> None:
        """Run post uninstall steps."""
        await self._reload_custom_templates()

    async def _reload_custom_templates(self) -> None:
        """Reload custom templates."""
        self.logger.debug("%s Reloading custom templates", self.string)
        try:
            await self.marketplace.hass.services.async_call(
                "homeassistant", "reload_custom_templates", {}
            )
        except HomeAssistantError:
            self.logger.exception("%s Reloading custom templates failed", self.string)

    @override
    @concurrent(concurrenttasks=10)
    async def update_repository(
        self, ignore_issues: bool = False, force: bool = False
    ) -> None:
        """Update."""
        if not await self.common_update(ignore_issues, force) and not force:
            return

        self._use_file_name()
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

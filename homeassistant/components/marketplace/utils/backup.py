"""Backups of downloaded content, kept while a download replaces it."""

from pathlib import Path
import shutil
from typing import TYPE_CHECKING

from homeassistant.helpers.storage import STORAGE_DIR
from homeassistant.util.ulid import ulid_now

from ..exceptions import MarketplaceError
from .logger import LOGGER
from .path import is_safe, resolve_in_directory

if TYPE_CHECKING:
    from ..base import MarketplaceManager

# Next to the downloaded content on the same file system, so a backup is a
# move instead of a copy, and it survives a restart in the middle of a download.
BACKUP_DIRECTORY = "marketplace_backups"

# Holds the path the backed up content belongs to, for restoring after a restart.
TARGET_FILE = "target"
CONTENT_NAME = "content"


def _backup_root(marketplace: MarketplaceManager) -> Path:
    """Return the directory that holds all backups."""
    return Path(marketplace.core.config_path, STORAGE_DIR, BACKUP_DIRECTORY)


class Backup:
    """Move content aside while a download replaces it."""

    def __init__(
        self,
        marketplace: MarketplaceManager,
        local_path: str | Path,
        backup_path: Path | None = None,
    ) -> None:
        """Initialize."""
        self.marketplace = marketplace
        self.local_path = Path(local_path)
        self.backup_path = backup_path or _backup_root(marketplace) / ulid_now()

    @property
    def content_path(self) -> Path:
        """Return where the backed up content is kept."""
        return self.backup_path / CONTENT_NAME

    def create(self) -> None:
        """Move the content into the backup."""
        if not self.local_path.exists():
            return

        if not is_safe(self.marketplace, self.local_path):
            return

        try:
            self.backup_path.mkdir(parents=True)
            # The target goes first, a restart before the move leaves an empty
            # backup behind, never content nobody knows the place of.
            (self.backup_path / TARGET_FILE).write_text(
                self._target(), encoding="utf-8"
            )
            shutil.move(self.local_path, self.content_path)
        except OSError as exception:
            LOGGER.warning("Could not create backup: %s", exception)
            return

        LOGGER.debug("Backup for %s created in %s", self.local_path, self.backup_path)

    def _target(self) -> str:
        """Return the content path, relative to the configuration directory."""
        config_path = Path(self.marketplace.core.config_path).resolve()
        local_path = self.local_path.resolve()
        if local_path.is_relative_to(config_path):
            return local_path.relative_to(config_path).as_posix()
        return local_path.as_posix()

    def restore(self) -> None:
        """Put the backed up content back, replacing what is there now."""
        if not self.content_path.exists():
            return

        if self.local_path.is_dir() and not self.local_path.is_symlink():
            shutil.rmtree(self.local_path)
        elif self.local_path.exists() or self.local_path.is_symlink():
            self.local_path.unlink()

        shutil.move(self.content_path, self.local_path)
        LOGGER.debug("Restored %s from backup %s", self.local_path, self.backup_path)

    def cleanup(self) -> None:
        """Remove the backup."""
        if not self.backup_path.exists():
            return

        shutil.rmtree(self.backup_path)
        LOGGER.debug("Backup %s removed", self.backup_path)


def restore_interrupted_backups(marketplace: MarketplaceManager) -> bool:
    """Put back what a download that never finished moved aside.

    Returns whether anything was put back.
    """
    root = _backup_root(marketplace)
    if not root.is_dir():
        return False

    backups: list[Backup] = []
    for backup_path in root.iterdir():
        try:
            target = (backup_path / TARGET_FILE).read_text(encoding="utf-8")
        except OSError:
            # Without a target nothing was moved into it yet
            shutil.rmtree(backup_path, ignore_errors=True)
            continue

        try:
            local_path = resolve_in_directory(marketplace.core.config_path, target)
        except MarketplaceError:
            local_path = None

        if local_path is None or not is_safe(marketplace, local_path):
            LOGGER.warning(
                "Leaving backup %s alone, %s is not a place to restore to",
                backup_path,
                target,
            )
            continue

        backups.append(Backup(marketplace, local_path, backup_path))

    # A persistent directory is moved out of the content it lives in, so the
    # content has to be back in place before the persistent directory is.
    backups.sort(key=lambda backup: len(backup.local_path.parts))

    restored = False
    for backup in backups:
        try:
            if backup.content_path.exists():
                backup.restore()
                restored = True
                LOGGER.warning(
                    "Restored %s, a download replacing it did not finish",
                    backup.local_path,
                )
            backup.cleanup()
        except OSError as exception:
            LOGGER.warning(
                "Could not restore backup %s: %s", backup.backup_path, exception
            )

    return restored

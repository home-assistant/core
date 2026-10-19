"""Backups of installed content, kept while an install replaces it."""

import contextlib
import errno
import os
from pathlib import Path
import shutil
from typing import TYPE_CHECKING

from homeassistant.helpers.storage import STORAGE_DIR
from homeassistant.util.file import WriteError, write_utf8_file_atomic
from homeassistant.util.ulid import ulid_now

from ..const import DOMAIN
from ..exceptions import MarketplaceError
from .logger import LOGGER
from .path import is_safe, resolve_in_directory

if TYPE_CHECKING:
    from ..base import MarketplaceManager

# In .storage of the configuration directory, so it survives a restart in the
# middle of an install. On another file system than the content, a backup is
# copied instead of moved.
BACKUP_DIRECTORY = "marketplace_backups"
# Backed up content that was put back, on its way out
DISCARDED_NAME = "discarded"

# Holds the path the backed up content belongs to, for restoring after a restart.
TARGET_FILE = "target"
CONTENT_NAME = "content"
# Marks a first install, there was nothing to keep, only what it writes to remove
ABSENT_FILE = "absent"


def _backup_root(marketplace: MarketplaceManager) -> Path:
    """Return the directory that holds all backups."""
    return Path(marketplace.core.config_path, STORAGE_DIR, BACKUP_DIRECTORY)


def _remove(path: Path) -> None:
    """Remove a file, a directory or a symlink to one."""
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()


def _move(source: Path, destination: Path) -> bool:
    """Move source to destination, return False when it is on another file system.

    Then nothing is moved and the caller copies, it decides when the source goes.
    """
    try:
        os.rename(source, destination)
    except OSError as exception:
        if exception.errno != errno.EXDEV:
            raise
        return False
    return True


def _copy(source: Path, destination: Path) -> None:
    """Copy source to destination, which only shows up once the copy is complete.

    A restart halfway leaves the copy under a name that is never read as content.
    """
    partial = destination.with_name(f".{destination.name}.partial")
    if os.path.lexists(partial):
        _remove(partial)

    if source.is_dir() and not source.is_symlink():
        shutil.copytree(source, partial, symlinks=True)
    else:
        shutil.copy2(source, partial, follow_symlinks=False)
    os.rename(partial, destination)


class Backup:
    """Move content aside while an install replaces it."""

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
        """Move the content into the backup.

        Raises when that fails, the content must not be replaced without one.
        """
        absent = not self.local_path.exists() and not self.local_path.is_symlink()

        if not is_safe(self.marketplace, self.local_path):
            raise MarketplaceError(
                translation_domain=DOMAIN,
                translation_key="backup_protected",
                translation_placeholders={"path": str(self.local_path)},
            )

        try:
            self.backup_path.mkdir(parents=True)
            # The target goes first, a restart before the move leaves an empty
            # backup behind, never content nobody knows the place of. Written
            # whole or not at all, half a path would restore to the wrong place.
            write_utf8_file_atomic(str(self.backup_path / TARGET_FILE), self._target())
            if absent:
                (self.backup_path / ABSENT_FILE).touch()
            elif not _move(self.local_path, self.content_path):
                self._copy_in()
        except (OSError, WriteError) as exception:
            # A complete backup can be the only copy left, the next start restores it
            if not self.has_content:
                shutil.rmtree(self.backup_path, ignore_errors=True)
            raise MarketplaceError(
                translation_domain=DOMAIN,
                translation_key="backup_failed",
                translation_placeholders={
                    "path": str(self.local_path),
                    "error": str(exception),
                },
            ) from exception

        LOGGER.debug("Backup for %s created in %s", self.local_path, self.backup_path)

    def _copy_in(self) -> None:
        """Copy the content into the backup, then remove it."""
        _copy(self.local_path, self.content_path)
        try:
            _remove(self.local_path)
        except OSError:
            # Partly removed, the complete copy puts it back as it was
            self.restore()
            raise

    def _target(self) -> str:
        """Return the content path, relative to the configuration directory.

        Symlinks are not followed, restoring puts a symlink back where it was
        instead of replacing what it points at.
        """
        config_path = Path(os.path.abspath(self.marketplace.core.config_path))
        local_path = Path(os.path.abspath(self.local_path))
        if local_path.is_relative_to(config_path):
            return local_path.relative_to(config_path).as_posix()
        return local_path.as_posix()

    def restore(self) -> None:
        """Put the backed up content back, replacing what is there now."""
        if not self.has_content:
            return

        if os.path.lexists(self.local_path):
            _remove(self.local_path)
        else:
            self.local_path.parent.mkdir(parents=True, exist_ok=True)

        if not _move(self.content_path, self.local_path):
            _copy(self.content_path, self.local_path)
            # Out of the way first, a restart while it is removed must not
            # restore what is left of it
            discarded = self.backup_path / DISCARDED_NAME
            os.rename(self.content_path, discarded)
            _remove(discarded)
        LOGGER.debug("Restored %s from backup %s", self.local_path, self.backup_path)

    @property
    def is_first_install(self) -> bool:
        """Return if nothing was there to back up, the install was a first one."""
        return (self.backup_path / ABSENT_FILE).exists()

    def remove_first_install(self) -> bool:
        """Remove what a first install wrote, return if there was anything."""
        if not os.path.lexists(self.local_path):
            return False

        _remove(self.local_path)
        return True

    @property
    def has_content(self) -> bool:
        """Return if content was moved in, a relative symlink does not resolve here."""
        return self.content_path.exists() or self.content_path.is_symlink()

    def cleanup(self) -> None:
        """Remove the backup.

        Raises when the target stays, a restart would restore the backup.
        """
        if not self.backup_path.exists():
            return

        # Without its target, what is left is removed at the next start
        with contextlib.suppress(FileNotFoundError):
            os.remove(self.backup_path / TARGET_FILE)

        try:
            shutil.rmtree(self.backup_path)
        except OSError as exception:
            LOGGER.warning(
                "Could not remove backup %s, it goes at the next start: %s",
                self.backup_path,
                exception,
            )
            return
        LOGGER.debug("Backup %s removed", self.backup_path)


def backed_up_paths(marketplace: MarketplaceManager) -> set[Path]:
    """Return the paths with a backup that is still waiting to be put back."""
    root = _backup_root(marketplace)
    if not root.is_dir():
        return set()

    paths: set[Path] = set()
    for backup_path in root.iterdir():
        try:
            target = (backup_path / TARGET_FILE).read_text(encoding="utf-8")
        except OSError:
            continue
        paths.add(Path(os.path.abspath(Path(marketplace.core.config_path, target))))
    return paths


def restore_interrupted_backups(marketplace: MarketplaceManager) -> bool:
    """Put back what an install that never finished moved aside.

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

        local_path: Path | None = Path(marketplace.core.config_path, target)
        try:
            # Checks the resolved path, the backup is restored to the literal one
            resolve_in_directory(marketplace.core.config_path, target)
        except MarketplaceError:
            local_path = None
        if Path(target).is_absolute() or ".." in Path(target).parts:
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

    # Moved into the new content already, the old content coming back would
    # remove the only copy of it
    left_for_next_start: list[Backup] = []
    for persistent in backups:
        if persistent.has_content or not persistent.local_path.exists():
            continue
        containing = [
            content
            for content in backups
            if content is not persistent
            and content.has_content
            and persistent.local_path.is_relative_to(content.local_path)
        ]
        if not containing:
            continue
        try:
            shutil.move(persistent.local_path, persistent.content_path)
        except OSError as exception:
            LOGGER.warning(
                "Could not move %s back into backup %s, both stay for the next"
                " start: %s",
                persistent.local_path,
                persistent.backup_path,
                exception,
            )
            left_for_next_start.extend([persistent, *containing])

    restored = False
    for backup in backups:
        if backup in left_for_next_start:
            continue
        try:
            if backup.has_content:
                backup.restore()
                restored = True
                LOGGER.warning(
                    "Restored %s, an install replacing it did not finish",
                    backup.local_path,
                )
            elif backup.is_first_install and backup.remove_first_install():
                LOGGER.warning(
                    "Removed %s, a first install of it did not finish",
                    backup.local_path,
                )
            backup.cleanup()
        except OSError as exception:
            LOGGER.warning(
                "Could not restore backup %s: %s", backup.backup_path, exception
            )

    return restored

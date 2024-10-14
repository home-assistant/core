"""Home Assistant module to handle restoring backups."""

from dataclasses import dataclass
import json
import logging
import os
from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory

import securetar

RESTORE_BACKUP_FILE = ".HA_RESTORE"
KEEP_PATHS = ("backups", ".HA_RESTORE")

_LOGGER = logging.getLogger(__name__)


@dataclass
class RestoreBackupFileContent:
    """Definition for restore backup file content."""

    backup_file_path: Path


def restore_backup_file_content(config_dir: Path) -> RestoreBackupFileContent | None:
    """Return the contents of the restore backup file."""
    instruction_path = config_dir.joinpath(RESTORE_BACKUP_FILE)
    if instruction_path.exists():
        instruction_content = instruction_path.read_text(encoding="utf-8")
        return RestoreBackupFileContent(
            backup_file_path=Path(instruction_content.split(";")[0])
        )
    return None


def _clear_configuration_directory(config_dir: Path) -> None:
    """Delete all files and directories in the config directory except for the backups directory."""
    config_contents = sorted(
        [entry for entry in os.listdir(config_dir) if entry not in KEEP_PATHS]
    )

    for entry in config_contents:
        entrypath = config_dir.joinpath(entry)
        if entrypath.is_file():
            entrypath.unlink()
        elif entrypath.is_dir():
            shutil.rmtree(entrypath)


def _extract_backup(config_dir: Path, backup_file_path: Path) -> None:
    """Extract the backup file to the config directory."""
    with (
        TemporaryDirectory() as tempdir,
        securetar.SecureTarFile(
            backup_file_path,
            gzip=False,
            mode="r",
        ) as ostf,
    ):
        ostf.extractall(Path(tempdir, "extracted"))
        with open(
            Path(tempdir, "extracted", "backup.json"),
            encoding="utf8",
        ) as backup_meta_file:
            backup_meta = json.load(backup_meta_file)

        with securetar.SecureTarFile(
            Path(
                tempdir,
                "extracted",
                f"homeassistant.tar{'.gz' if backup_meta["compressed"] else ''}",
            ),
            gzip=backup_meta["compressed"],
            mode="r",
        ) as istf:
            for member in istf.getmembers():
                if member.name == "data":
                    continue
                member.name = member.name.replace("data/", "")
            _clear_configuration_directory(config_dir)
            istf.extractall(config_dir)


def restore_backup(config_dir_path: str) -> bool:
    """Restore the backup file if any.

    Returns True if a restore backup file was found and restored, False otherwise.
    """
    config_dir = Path(config_dir_path)
    if not (restore_content := restore_backup_file_content(config_dir)):
        return False

    if (
        not restore_content.backup_file_path.exists()
        or not restore_content.backup_file_path.is_file()
    ):
        _LOGGER.error("Backup file %s does not exist", restore_content.backup_file_path)
        return False

    logging.basicConfig(stream=sys.stdout, level=logging.INFO)
    backup_file_path = restore_content.backup_file_path
    _LOGGER.info("Restoring %s", backup_file_path)
    _extract_backup(config_dir, backup_file_path)
    _LOGGER.info("Restore complete, restarting")
    return True

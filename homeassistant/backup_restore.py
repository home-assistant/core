"""Home Assistant module to handle restoring backups."""

import json
import logging
import os
import shutil
import sys
from tempfile import TemporaryDirectory
from typing import TypedDict

import securetar

RESTORE_BACKUP_FILE = ".HA_RESTORE"
KEEP_PATHS = ("backups", ".HA_RESTORE")

_LOGGER = logging.getLogger(__name__)


class RestoreBackupFileContent(TypedDict):
    """Type definition for restore backup file content."""

    backup_file_path: str


def restore_backup_file_content(config_dir: str) -> RestoreBackupFileContent | None:
    """Return the contents of the restore backup file."""
    instruction_path = os.path.join(config_dir, RESTORE_BACKUP_FILE)
    if os.path.exists(instruction_path):
        with open(instruction_path, encoding="utf-8") as file:
            [backup_file_path, *_] = file.readline().split(";")
            return RestoreBackupFileContent(backup_file_path=backup_file_path)
    return None


def _clear_configuration_directory(config_dir: str) -> None:
    """Delete all files and directories in the config directory except for the backups directory."""
    config_contents = sorted(
        [entry for entry in os.listdir(config_dir) if entry not in KEEP_PATHS]
    )

    for entry in config_contents:
        entrypath = os.path.join(config_dir, entry)
        if os.path.isfile(entrypath):
            os.remove(entrypath)
        elif os.path.isdir(entrypath):
            shutil.rmtree(entrypath)


def _extract_backup(config_dir: str, backup_file_path: str) -> None:
    """Extract the backup file to the config directory."""
    with (
        TemporaryDirectory() as tempdir,
        securetar.SecureTarFile(
            backup_file_path,
            gzip=False,
            mode="r",
        ) as ostf,
    ):
        ostf.extractall(os.path.join(tempdir, "extracted"))
        with open(
            os.path.join(tempdir, "extracted", "backup.json"),
            encoding="utf8",
        ) as backup_meta_file:
            backup_meta = json.load(backup_meta_file)

        with securetar.SecureTarFile(
            os.path.join(
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


def restore_backup(config_dir: str) -> bool:
    """Restore the backup file if any.

    Returns True if a restore backup file was found and restored, False otherwise.
    """
    logging.basicConfig(stream=sys.stdout, level=logging.INFO)
    if not (restore_content := restore_backup_file_content(config_dir)):
        return False
    backup_file_path = restore_content["backup_file_path"]
    _LOGGER.info("Restoring %s", backup_file_path)
    _extract_backup(config_dir, backup_file_path)
    _LOGGER.info("Restore complete, restarting")
    return True

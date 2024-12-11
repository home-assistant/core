"""Home Assistant module to handle restoring backups."""

from dataclasses import dataclass
import hashlib
import json
import logging
from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory

from awesomeversion import AwesomeVersion
import securetar

from .const import __version__ as HA_VERSION

RESTORE_BACKUP_FILE = ".HA_RESTORE"
KEEP_PATHS = ("backups",)

_LOGGER = logging.getLogger(__name__)


@dataclass
class RestoreBackupFileContent:
    """Definition for restore backup file content."""

    backup_file_path: Path
    password: str | None = None


def password_to_key(password: str) -> bytes:
    """Generate a AES Key from password.

    Matches the implementation in supervisor.backups.utils.password_to_key.
    """
    key: bytes = password.encode()
    for _ in range(100):
        key = hashlib.sha256(key).digest()
    return key[:16]


def restore_backup_file_content(config_dir: Path) -> RestoreBackupFileContent | None:
    """Return the contents of the restore backup file."""
    instruction_path = config_dir.joinpath(RESTORE_BACKUP_FILE)
    try:
        instruction_content = json.loads(instruction_path.read_text(encoding="utf-8"))
        return RestoreBackupFileContent(
            backup_file_path=Path(instruction_content["path"]),
            password=instruction_content.get("password"),
        )
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _clear_configuration_directory(config_dir: Path) -> None:
    """Delete all files and directories in the config directory except for the backups directory."""
    keep_paths = [config_dir.joinpath(path) for path in KEEP_PATHS]
    config_contents = sorted(
        [entry for entry in config_dir.iterdir() if entry not in keep_paths]
    )

    for entry in config_contents:
        entrypath = config_dir.joinpath(entry)

        if entrypath.is_file():
            entrypath.unlink()
        elif entrypath.is_dir():
            shutil.rmtree(entrypath)


def _extract_backup(
    config_dir: Path,
    backup_file_path: Path,
    password: str | None = None,
) -> None:
    """Extract the backup file to the config directory."""
    with (
        TemporaryDirectory() as tempdir,
        securetar.SecureTarFile(
            backup_file_path,
            gzip=False,
            mode="r",
        ) as ostf,
    ):
        ostf.extractall(
            path=Path(tempdir, "extracted"),
            members=securetar.secure_path(ostf),
            filter="fully_trusted",
        )
        backup_meta_file = Path(tempdir, "extracted", "backup.json")
        backup_meta = json.loads(backup_meta_file.read_text(encoding="utf8"))

        if (
            backup_meta_version := AwesomeVersion(
                backup_meta["homeassistant"]["version"]
            )
        ) > HA_VERSION:
            raise ValueError(
                f"You need at least Home Assistant version {backup_meta_version} to restore this backup"
            )

        with securetar.SecureTarFile(
            Path(
                tempdir,
                "extracted",
                f"homeassistant.tar{'.gz' if backup_meta["compressed"] else ''}",
            ),
            gzip=backup_meta["compressed"],
            key=password_to_key(password) if password is not None else None,
            mode="r",
        ) as istf:
            istf.extractall(
                path=Path(
                    tempdir,
                    "homeassistant",
                ),
                members=securetar.secure_path(istf),
                filter="fully_trusted",
            )
            _clear_configuration_directory(config_dir)
            shutil.copytree(
                Path(
                    tempdir,
                    "homeassistant",
                    "data",
                ),
                config_dir,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns(*(KEEP_PATHS)),
            )


def restore_backup(config_dir_path: str) -> bool:
    """Restore the backup file if any.

    Returns True if a restore backup file was found and restored, False otherwise.
    """
    config_dir = Path(config_dir_path)
    if not (restore_content := restore_backup_file_content(config_dir)):
        return False

    logging.basicConfig(stream=sys.stdout, level=logging.INFO)
    backup_file_path = restore_content.backup_file_path
    _LOGGER.info("Restoring %s", backup_file_path)
    try:
        _extract_backup(
            config_dir=config_dir,
            backup_file_path=backup_file_path,
            password=restore_content.password,
        )
    except FileNotFoundError as err:
        raise ValueError(f"Backup file {backup_file_path} does not exist") from err
    _LOGGER.info("Restore complete, restarting")
    return True

"""Local backup support for Core and Container installations."""

from __future__ import annotations

from pathlib import Path
import tarfile
from typing import cast

from homeassistant.util.json import json_loads_object

from .const import BUF_SIZE
from .models import BaseBackup


def read_backup(backup_path: Path) -> BaseBackup:
    """Read a backup from disk."""

    with tarfile.open(backup_path, "r:", bufsize=BUF_SIZE) as backup_file:
        if not (data_file := backup_file.extractfile("./backup.json")):
            raise KeyError("backup.json not found in tar file")
        data = json_loads_object(data_file.read())
        return BaseBackup(
            slug=cast(str, data["slug"]),
            name=cast(str, data["name"]),
            date=cast(str, data["date"]),
            size=round(backup_path.stat().st_size / 1_048_576, 2),
            protected=cast(bool, data.get("protected", False)),
        )

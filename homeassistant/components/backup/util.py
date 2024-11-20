"""Local backup support for Core and Container installations."""

from __future__ import annotations

from pathlib import Path
import tarfile
from typing import cast

from homeassistant.util.json import json_loads_object

from .const import BUF_SIZE
from .models import AgentBackup


def read_backup(backup_path: Path) -> AgentBackup:
    """Read a backup from disk."""

    with tarfile.open(backup_path, "r:", bufsize=BUF_SIZE) as backup_file:
        if not (data_file := backup_file.extractfile("./backup.json")):
            raise KeyError("backup.json not found in tar file")
        data = json_loads_object(data_file.read())
        return AgentBackup(
            backup_id=cast(str, data["slug"]),
            date=cast(str, data["date"]),
            name=cast(str, data["name"]),
            protected=cast(bool, data.get("protected", False)),
            size=backup_path.stat().st_size,
        )

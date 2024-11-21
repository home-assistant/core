"""Local backup support for Core and Container installations."""

from __future__ import annotations

from pathlib import Path
import tarfile
from typing import cast

from homeassistant.util.json import JsonObjectType, json_loads_object

from .const import BUF_SIZE
from .models import AddonInfo, AgentBackup


def read_backup(backup_path: Path) -> AgentBackup:
    """Read a backup from disk."""

    with tarfile.open(backup_path, "r:", bufsize=BUF_SIZE) as backup_file:
        if not (data_file := backup_file.extractfile("./backup.json")):
            raise KeyError("backup.json not found in tar file")
        data = json_loads_object(data_file.read())
        addons = [
            AddonInfo(
                name=cast(str, addon["name"]),
                slug=cast(str, addon["slug"]),
                version=cast(str, addon["version"]),
            )
            for addon in cast(list[JsonObjectType], data.get("addons", []))
        ]

        folders = [
            folder
            for folder in cast(list[str], data.get("folders", []))
            if folder != "homeassistant"
        ]

        homeassistant_included = False
        homeassistant_version: str | None = None
        database_included = False
        if (
            homeassistant := cast(JsonObjectType, data.get("homeassistant"))
        ) and "version" in homeassistant:
            homeassistant_version = cast(str, homeassistant["version"])
            database_included = not cast(
                bool, homeassistant.get("exclude_database", False)
            )

        return AgentBackup(
            addons=addons,
            backup_id=cast(str, data["slug"]),
            database_included=database_included,
            date=cast(str, data["date"]),
            folders=folders,
            homeassistant_included=homeassistant_included,
            homeassistant_version=homeassistant_version,
            name=cast(str, data["name"]),
            protected=cast(bool, data.get("protected", False)),
            size=backup_path.stat().st_size,
        )

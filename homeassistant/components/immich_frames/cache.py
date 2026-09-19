"""Atomic on-disk cache for the last successfully rendered frame."""

import base64
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from aioimmich.assets.models import AssetType, ExifInfo, ImmichAsset

from .const import CONF_INTERVAL
from .rendering import image_size

CACHE_VERSION = 2
RENDER_VERSION = 1


def _asset_from_state(values: dict[str, Any]) -> ImmichAsset:
    """Rebuild an Immich asset from its stable Python representation."""
    values = dict(values)
    values["asset_type"] = AssetType(values["asset_type"])
    for key in ("file_created_at", "file_modified_at", "local_datetime", "updated_at"):
        values[key] = datetime.fromisoformat(values[key])
    if values.get("exif_info") is not None:
        exif = dict(values["exif_info"])
        if exif.get("date_time_original") is not None:
            exif["date_time_original"] = datetime.fromisoformat(
                exif["date_time_original"]
            )
        values["exif_info"] = ExifInfo(**exif)
    return ImmichAsset(**values)


def cache_signature(
    options: dict[str, Any], parent_entry_id: str, parent_identity: str
) -> str:
    """Return a settings/account-sensitive cache signature."""
    data = {
        "parent_entry_id": parent_entry_id,
        "parent_identity": parent_identity,
        "render_version": RENDER_VERSION,
        "options": {
            key: value for key, value in options.items() if key != CONF_INTERVAL
        },
    }
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


class FrameCache:
    """Read and write one verified frame snapshot."""

    def __init__(self, path: Path) -> None:
        """Initialize the cache path."""
        self.path = path

    def read(
        self, options: dict[str, Any], parent_entry_id: str, parent_identity: str
    ) -> tuple[ImmichAsset, bytes, datetime] | None:
        """Read a valid cached asset and rendered image."""
        try:
            state = json.loads(self.path.read_text())
            image = base64.b64decode(state["image"], validate=True)
            if (
                state["cache_version"] != CACHE_VERSION
                or state["signature"]
                != cache_signature(options, parent_entry_id, parent_identity)
                or state["sha256"] != hashlib.sha256(image).hexdigest()
            ):
                return None
            return (
                _asset_from_state(state["asset"]),
                image,
                datetime.fromisoformat(state["rendered_at"]),
            )
        except OSError, KeyError, TypeError, ValueError:
            return None

    def write(
        self,
        asset: ImmichAsset,
        image: bytes,
        options: dict[str, Any],
        parent_entry_id: str,
        parent_identity: str,
        rendered_at: datetime,
    ) -> None:
        """Atomically write a verified cached frame."""
        if image_size(image) not in {
            (1280, 800),
            (800, 1280),
            (720, 720),
        }:
            raise ValueError("Rendered image has an unsupported output size")
        state = {
            "cache_version": CACHE_VERSION,
            "signature": cache_signature(options, parent_entry_id, parent_identity),
            "asset": asset.to_dict(),
            "image": base64.b64encode(image).decode("ascii"),
            "sha256": hashlib.sha256(image).hexdigest(),
            "rendered_at": rendered_at.isoformat(),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                delete=False,
            ) as stream:
                temporary = stream.name
                json.dump(state, stream, separators=(",", ":"))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary is not None:
                Path(temporary).unlink(missing_ok=True)

    def clear(self) -> None:
        """Remove the cache if it exists."""
        self.path.unlink(missing_ok=True)

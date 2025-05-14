"""Utility functions for Home Assistant Yellow integration."""

from __future__ import annotations

from collections.abc import Iterable

from ha_silabs_firmware_client import FirmwareManifest, FirmwareMetadata


def get_supported_firmwares(manifest: FirmwareManifest) -> Iterable[FirmwareMetadata]:
    """Get a list of supported firmwares from a firmware update manifest."""
    return [fw for fw in manifest.firmwares if fw.filename.startswith("yellow_")]

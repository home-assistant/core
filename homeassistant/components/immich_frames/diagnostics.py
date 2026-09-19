"""Diagnostics support for Immich Frames."""

from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import ImmichFramesConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ImmichFramesConfigEntry
) -> dict[str, Any]:
    """Return safe diagnostics without including image bytes or credentials."""
    data = entry.runtime_data.data
    asset = data.asset
    return {
        "entry": entry.as_dict(),
        "frame": {
            "asset_type": asset.asset_type.value,
            "is_offline": asset.is_offline,
            "is_trashed": asset.is_trashed,
            "updated_at": data.updated_at.isoformat(),
            "image_bytes": len(data.image),
        },
    }

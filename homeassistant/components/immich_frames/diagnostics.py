"""Diagnostics support for Immich Frames."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    CONF_SSL,
    CONF_URL,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant

from .const import (
    CONF_ALBUM_IDS,
    CONF_FRAME_ID,
    CONF_FRAME_NAME,
    CONF_IMMICH_ENTRY_ID,
    CONF_SMART_QUERY,
)
from .coordinator import ImmichFramesConfigEntry

TO_REDACT = {
    CONF_ALBUM_IDS,
    CONF_FRAME_ID,
    CONF_FRAME_NAME,
    CONF_IMMICH_ENTRY_ID,
    CONF_SMART_QUERY,
    "entry_id",
    "title",
    "unique_id",
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    CONF_SSL,
    CONF_URL,
    CONF_VERIFY_SSL,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ImmichFramesConfigEntry
) -> dict[str, Any]:
    """Return safe diagnostics without including image bytes or credentials."""
    coordinator = entry.runtime_data
    data = coordinator.current_data
    if data is None:
        return {
            "entry": async_redact_data(entry.as_dict(), TO_REDACT),
            "frame": {"status": "unavailable"},
        }
    asset = data.asset
    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "frame": {
            "asset_type": asset.asset_type.value,
            "is_offline": asset.is_offline,
            "is_trashed": asset.is_trashed,
            "updated_at": data.updated_at.isoformat(),
            "image_bytes": len(data.image),
        },
    }

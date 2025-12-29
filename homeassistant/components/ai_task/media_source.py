"""Expose images as media sources."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components.media_source import MediaSource, local_source
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import DATA_MEDIA_SOURCE, DOMAIN, IMAGE_DIR


async def async_get_media_source(hass: HomeAssistant) -> MediaSource:
    """Set up local media source."""
    media_dirs = list(hass.config.media_dirs.values())

    if not media_dirs:
        raise HomeAssistantError(
            "AI Task media source requires at least one media directory configured"
        )

    media_dir = Path(media_dirs[0]) / DOMAIN / IMAGE_DIR

    hass.data[DATA_MEDIA_SOURCE] = source = local_source.LocalSource(
        hass,
        DOMAIN,
        "AI Generated Images",
        {IMAGE_DIR: str(media_dir)},
        f"/{DOMAIN}",
    )
    return source

"""Expose images as media sources."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components.media_source import MediaSource, local_source
from homeassistant.core import HomeAssistant

from .const import DATA_MEDIA_SOURCE, DOMAIN, IMAGE_DIR


async def async_get_media_source(hass: HomeAssistant) -> MediaSource:
    """Set up local media source."""
    media_dir = hass.config.path(f"{DOMAIN}/{IMAGE_DIR}")
    Path(media_dir).mkdir(parents=True, exist_ok=True)
    hass.data[DATA_MEDIA_SOURCE] = source = local_source.LocalSource(
        hass,
        DOMAIN,
        "AI Generated Images",
        {IMAGE_DIR: media_dir},
        f"/{DOMAIN}",
    )
    return source

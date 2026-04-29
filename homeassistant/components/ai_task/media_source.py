"""Expose images as media sources."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components.media_source import MediaSource, local_source
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import DATA_MEDIA_SOURCE, DOMAIN, IMAGE_DIR


async def async_get_media_source(hass: HomeAssistant) -> MediaSource | None:
    """Set up local media source.

    The source is only exposed once an image has been generated. The local
    source object is always created so that image generation can use it to
    upload, and ``async_generate_image`` registers the source with media_source
    after the first upload via :func:`media_source.async_register_media_source`.
    """
    media_dirs = list(hass.config.media_dirs.values())

    if not media_dirs:
        raise HomeAssistantError(
            "AI Task media source requires at least one media directory configured"
        )

    media_dir = Path(media_dirs[0]) / DOMAIN / IMAGE_DIR

    hass.data[DATA_MEDIA_SOURCE] = source = local_source.LocalSource(
        hass,
        DOMAIN,
        "AI generated images",
        {IMAGE_DIR: str(media_dir)},
        f"/{DOMAIN}",
    )

    if not await hass.async_add_executor_job(media_dir.exists):
        return None

    return source

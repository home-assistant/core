"""Expose images as media sources."""

from pathlib import Path

from homeassistant.components.media_source import local_source
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.singleton import singleton

from .const import DATA_MEDIA_SOURCE, DOMAIN, IMAGE_DIR


@singleton(DATA_MEDIA_SOURCE, async_=True)
async def async_get_media_source(hass: HomeAssistant) -> local_source.LocalSource:
    """Set up local media source."""
    media_dirs = list(hass.config.media_dirs.values())

    if not media_dirs:
        raise HomeAssistantError(
            "AI Task media source requires at least one media directory configured"
        )

    media_dir = Path(media_dirs[0]) / DOMAIN / IMAGE_DIR

    return local_source.LocalSource(
        hass,
        DOMAIN,
        "AI generated images",
        {IMAGE_DIR: str(media_dir)},
        f"/{DOMAIN}",
    )
